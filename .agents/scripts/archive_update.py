from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, cast

REPOSITORY = "byteplus-sa/seed-cinema-studio"
SOURCE_PATH = ".agents/contracts/update-source.json"
STATE_PATH = ".agents/local/update-state.json"
LOCK_PATH = ".agents/local/update.lock"
MAX_ZIP_BYTES = 128 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 20000
MAX_RATIO = 200
MAX_PATH_DEPTH = 64
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
REVISION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")
PROTECTED_DIRECTORIES = {
    ".git",
    ".agents-local",
    ".vscode",
    ".idea",
    ".trae",
    ".cursor",
    ".zed",
    ".windsurf",
    ".trae-html-share-packages",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".cache",
    "cache",
    "caches",
    ".npm",
    ".yarn",
    ".pnpm-store",
    ".next",
    ".nuxt",
    ".turbo",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".artifacts",
    "dist",
    "build",
    "preferences",
}
PROTECTED_ROOTS = {"projects", "library", "docs", "plans", "specs"}
Descriptor = dict[str, Any]
Inventory = dict[str, Descriptor]


class UpdateError(ValueError):
    backup: Path | None = None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise UpdateError("Duplicate JSON key")
        result[key] = value
    return result


def invalid_constant(value: str) -> Any:
    raise UpdateError("Non-finite JSON value")


def decode_json(data: bytes) -> Any:
    if len(data) > MAX_JSON_BYTES:
        raise UpdateError("JSON exceeds size bound")
    try:
        return json.loads(
            data, object_pairs_hook=unique_object, parse_constant=invalid_constant
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise UpdateError("Malformed JSON") from error


def validate_path(name: str) -> str:
    if not isinstance(name, str) or not name or len(name) > 1024:
        raise UpdateError("Empty or oversized archive path")
    parts = name.split("/")
    if len(parts) > MAX_PATH_DEPTH:
        raise UpdateError("Archive path depth exceeds bound")
    for part in parts:
        if (
            not part
            or len(part) > 255
            or part in {".", ".."}
            or part.endswith((".", " "))
            or any(ord(character) < 32 or ord(character) > 126 for character in part)
            or any(character in '<>:"|?*\\' for character in part)
            or part.split(".")[0].casefold()
            in {
                "con",
                "prn",
                "aux",
                "nul",
                *(f"com{number}" for number in range(1, 10)),
                *(f"lpt{number}" for number in range(1, 10)),
            }
        ):
            raise UpdateError(f"Malformed path: {name!r}")
    return name


def protected(name: str) -> bool:
    parts = tuple(part.casefold() for part in name.split("/"))
    if parts[0] in PROTECTED_ROOTS:
        return True
    if parts[:2] == (".agents", "local"):
        return True
    if parts[0] == ".claude" and expected_alias(name) is None:
        return True
    return any(
        part in PROTECTED_DIRECTORIES
        or part.startswith((".env", "preferences.", "local-preferences."))
        or part.endswith(
            ("_cache", ".log", ".pyc", ".swp", ".swo", ".local.json", ".code-workspace")
        )
        or part
        in {
            ".ds_store",
            "thumbs.db",
            "settings.json",
            ".mcp.json",
            ".claude.json",
            "claude.local.md",
            "agents.local.md",
        }
        for part in parts
    )


def expected_alias(name: str) -> str | None:
    fixed = {
        "CLAUDE.md": "AGENTS.md",
        ".claude": ".agents",
        ".claude/catalog": "../.agents/catalog",
        ".claude/contracts": "../.agents/contracts",
        ".claude/scripts": "../.agents/scripts",
        ".claude/skills": "../.agents/skills",
    }
    if name in fixed:
        return fixed[name]
    parts = name.split("/")
    if len(parts) == 3 and parts[:2] == [".claude", "skills"]:
        return f"../../.agents/skills/{parts[2]}"
    return None


def validate_revision(revision: str) -> str:
    if (
        not isinstance(revision, str)
        or not REVISION_PATTERN.fullmatch(revision)
        or any(part in {"", ".", ".."} for part in revision.split("/"))
    ):
        raise UpdateError("Supply an explicit valid source revision")
    return revision


def validate_source(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "repository", "ref"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["repository"] != REPOSITORY
    ):
        raise UpdateError("Invalid authoritative update-source.json")
    validate_revision(value["ref"])
    return cast(dict[str, Any], value)


def check_parents(root: Path, name: str) -> None:
    current = root
    if root.is_symlink() or not root.is_dir():
        raise UpdateError("Workspace or staging root must be a real directory")
    for part in name.split("/")[:-1]:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            raise UpdateError(f"Unsafe parent for {name}")


@contextmanager
def directory_handle(
    root: Path, relative: str = "", created: list[Path] | None = None
) -> Iterator[int]:
    if os.name != "posix":
        raise UpdateError("POSIX directory-handle support is required")
    parts = relative.split("/") if relative else []
    if any(part in {"", ".", ".."} for part in parts):
        raise UpdateError("Unsafe relative directory path")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    handle = os.open(root, flags)
    prefix = root
    try:
        for part in parts:
            prefix = prefix / part
            try:
                child = os.open(part, flags, dir_fd=handle)
            except FileNotFoundError:
                if created is None:
                    raise
                os.mkdir(part, dir_fd=handle)
                created.append(prefix)
                child = os.open(part, flags, dir_fd=handle)
            os.close(handle)
            handle = child
        yield handle
    finally:
        os.close(handle)


def read_regular(root: Path, name: str, limit: int = MAX_FILE_BYTES) -> bytes:
    parent, _, leaf = name.rpartition("/")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with directory_handle(root, parent) as handle:
        if not stat.S_ISREG(
            os.stat(leaf, dir_fd=handle, follow_symlinks=False).st_mode
        ):
            raise UpdateError(f"Not a regular file: {name}")
        number = os.open(leaf, flags, dir_fd=handle)
        try:
            if not stat.S_ISREG(os.fstat(number).st_mode):
                raise UpdateError(f"Not a regular file: {name}")
            with os.fdopen(number, "rb", closefd=False) as stream:
                data = stream.read(limit + 1)
        finally:
            os.close(number)
    if len(data) > limit:
        raise UpdateError(f"File exceeds size bound: {name}")
    return data


def read_source(root: Path) -> dict[str, Any]:
    try:
        return validate_source(
            decode_json(read_regular(root, SOURCE_PATH, MAX_JSON_BYTES))
        )
    except OSError as error:
        raise UpdateError(
            "Missing or unreadable authoritative update-source.json"
        ) from error


def descriptor(snapshot: Descriptor | None) -> Descriptor | None:
    if snapshot is None:
        return None
    return {key: value for key, value in snapshot.items() if key != "identity"}


def stable_stat(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
        value.st_mode,
    )


def snapshot_entry(root: Path, name: str) -> Descriptor | None:
    parent, _, leaf = name.rpartition("/")
    try:
        check_parents(root, name)
        if not (root / name).exists() and not (root / name).is_symlink():
            return None
        with directory_handle(root, parent) as handle:
            before = os.stat(leaf, dir_fd=handle, follow_symlinks=False)
            mode = stat.S_IMODE(before.st_mode)
            identity = [
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ]
            if stat.S_ISLNK(before.st_mode):
                result: Descriptor = {
                    "kind": "alias",
                    "target": os.readlink(leaf, dir_fd=handle),
                }
            elif stat.S_ISDIR(before.st_mode):
                return {
                    "kind": "directory",
                    "mode": mode,
                    "identity": [before.st_dev, before.st_ino],
                }
            elif stat.S_ISREG(before.st_mode):
                hasher = hashlib.sha256()
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                with os.fdopen(os.open(leaf, flags, dir_fd=handle), "rb") as stream:
                    if stable_stat(os.fstat(stream.fileno())) != stable_stat(before):
                        raise UpdateError("File changed while opening snapshot")
                    while chunk := stream.read(1024 * 1024):
                        hasher.update(chunk)
                result = {"kind": "file", "sha256": hasher.hexdigest(), "mode": mode}
            else:
                return {"kind": "special", "identity": identity}
            after = os.stat(leaf, dir_fd=handle, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if stable_stat(before) != stable_stat(after):
        raise UpdateError(f"File changed during snapshot: {name}")
    result["identity"] = identity
    return result


def inventory(
    root: Path, exclusions: set[str] | None = None, protect_local: bool = True
) -> Inventory:
    result: Inventory = {}
    excluded = exclusions or set()

    def visit(relative: str) -> None:
        with directory_handle(root, relative) as handle, os.scandir(handle) as children:
            for child in sorted(children, key=lambda item: item.name):
                name = f"{relative}/{child.name}" if relative else child.name
                if name in excluded:
                    continue
                if protect_local and protected(name):
                    mode = child.stat(follow_symlinks=False).st_mode
                    if stat.S_ISDIR(mode):
                        kind = "directory"
                    elif stat.S_ISLNK(mode):
                        kind = "alias"
                    elif stat.S_ISREG(mode):
                        kind = "file"
                    else:
                        kind = "special"
                    result[name] = {"kind": kind}
                    continue
                entry = snapshot_entry(root, name)
                if entry is None:
                    raise UpdateError("Workspace changed during inventory")
                result[name] = entry
                if entry["kind"] == "directory":
                    visit(name)

    visit("")
    return result


def validate_descriptor(
    name: str, entry: Any, allow_protected: bool = False
) -> Descriptor:
    validate_path(name)
    if (protected(name) and not allow_protected) or not isinstance(entry, dict):
        raise UpdateError("Invalid managed base inventory")
    if entry.get("kind") == "file":
        if (
            set(entry) != {"kind", "sha256", "mode"}
            or not isinstance(entry["sha256"], str)
            or not HASH_PATTERN.fullmatch(entry["sha256"])
            or type(entry["mode"]) is not int
            or entry["mode"] not in {0o644, 0o755}
        ):
            raise UpdateError("Invalid base file hash or mode")
    elif entry.get("kind") == "alias":
        if (
            set(entry) != {"kind", "target"}
            or expected_alias(name) is None
            or entry["target"] != expected_alias(name)
        ):
            raise UpdateError("Invalid base alias")
    else:
        raise UpdateError("Invalid base entry kind")
    return cast(Descriptor, entry)


def read_state(root: Path) -> tuple[dict[str, Any], Descriptor | None]:
    snapshot = snapshot_entry(root, STATE_PATH)
    if snapshot is None:
        return {"hashes": {}}, None
    if snapshot["kind"] != "file":
        raise UpdateError("Update state must be a regular file")
    state = decode_json(read_regular(root, STATE_PATH, MAX_JSON_BYTES))
    if (
        not isinstance(state, dict)
        or set(state)
        != {"schema_version", "repository", "revision", "hashes", "transaction"}
        or type(state["schema_version"]) is not int
        or state["schema_version"] != 1
        or state["repository"] != REPOSITORY
        or not isinstance(state["hashes"], dict)
        or not isinstance(state["transaction"], str)
        or len(state["hashes"]) > MAX_ENTRIES
    ):
        raise UpdateError("Malformed installed update state")
    validate_revision(state["revision"])
    for name, entry in state["hashes"].items():
        validate_descriptor(name, entry)
    validate_tree({name: False for name in state["hashes"]})
    if snapshot_entry(root, STATE_PATH) != snapshot:
        raise UpdateError("Base changed while reading")
    return state, snapshot


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise UpdateError("HTTP redirects are not allowed; use a user-provided ZIP")


def open_url(url: str) -> BinaryIO:
    parsed = urllib.parse.urlsplit(url)
    api_path = f"/repos/{REPOSITORY}/commits/"
    codeload_path = rf"/{re.escape(REPOSITORY)}/zip/[0-9a-f]{{40}}"
    if (
        parsed.scheme != "https"
        or parsed.netloc not in {"api.github.com", "codeload.github.com"}
        or parsed.query
        or parsed.fragment
        or (parsed.netloc == "api.github.com" and not parsed.path.startswith(api_path))
        or (
            parsed.netloc == "codeload.github.com"
            and not re.fullmatch(codeload_path, parsed.path)
        )
    ):
        raise UpdateError("Only fixed GitHub API and codeload HTTPS URLs are allowed")
    headers = {
        "User-Agent": "seed-cinema-studio-update",
        "Accept": "application/vnd.github+json"
        if parsed.netloc == "api.github.com"
        else "application/zip",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", token):
            raise UpdateError("Invalid GITHUB_TOKEN format")
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    return cast(
        BinaryIO, urllib.request.build_opener(NoRedirect()).open(request, timeout=30)
    )


def network_error(error: BaseException) -> UpdateError:
    if isinstance(error, urllib.error.HTTPError):
        if error.code in {401, 403}:
            return UpdateError(
                "GitHub authentication/permission or rate-limit failure; use a local ZIP"
            )
        if error.code == 429:
            return UpdateError(
                "GitHub rate limit reached; retry later or use a local ZIP"
            )
        return UpdateError(f"GitHub HTTP {error.code}; use a local ZIP")
    return UpdateError("GitHub network failure; retry explicitly or use a local ZIP")


def discover(root: Path) -> dict[str, Any]:
    source = read_source(root)
    url = f"https://api.github.com/repos/{REPOSITORY}/commits/{urllib.parse.quote(source['ref'], safe='')}"
    try:
        with open_url(url) as response:
            body = decode_json(response.read(MAX_JSON_BYTES + 1))
    except (OSError, urllib.error.URLError) as error:
        raise network_error(error) from error
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("sha"), str)
        or not SHA_PATTERN.fullmatch(body["sha"])
    ):
        raise UpdateError("GitHub returned no valid pinned commit SHA")
    return {
        "repository": REPOSITORY,
        "ref": source["ref"],
        "revision": body["sha"],
        "url": f"https://codeload.github.com/{REPOSITORY}/zip/{body['sha']}",
        "downloaded": False,
        "max_download_bytes": MAX_ZIP_BYTES,
        "estimated_bytes": None,
    }


def external_directory(root: Path, prefix: str = "seed-update-stage-") -> Path:
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if temporary_root.is_relative_to(root):
        raise UpdateError("System temporary directory must be outside the workspace")
    return Path(tempfile.mkdtemp(prefix=prefix, dir=temporary_root))


def remove_staging(path: Path) -> None:
    if not path.name.startswith(("seed-update-stage-", "seed-update-backup-")):
        raise UpdateError("Refusing to remove an unowned temporary directory")
    shutil.rmtree(path)


def validate_tree(paths: dict[str, bool]) -> None:
    folded: dict[str, str] = {}
    for name in paths:
        validate_path(name)
        parts = name.split("/")
        for length in range(1, len(parts) + 1):
            prefix = "/".join(parts[:length])
            previous = folded.setdefault(prefix.casefold(), prefix)
            if previous != prefix:
                raise UpdateError("Case-insensitive archive path collision")
            if length < len(parts) and prefix in paths and not paths[prefix]:
                raise UpdateError("Archive file or alias is also a parent")


def archive_members(bundle: zipfile.ZipFile) -> list[tuple[str, zipfile.ZipInfo]]:
    members = bundle.infolist()
    if not members or len(members) > MAX_ENTRIES:
        raise UpdateError("Empty archive or archive entry count exceeds bound")
    raw: dict[str, bool] = {}
    total = 0
    for member in members:
        if member.filename != member.orig_filename:
            raise UpdateError("NUL or malformed ZIP filename")
        name = member.filename[:-1] if member.is_dir() else member.filename
        validate_path(name)
        if name in raw:
            raise UpdateError("Duplicate archive path")
        raw[name] = member.is_dir()
        if ".git" in (part.casefold() for part in name.split("/")):
            raise UpdateError("Archives cannot contain Git control paths")
        mode = member.external_attr >> 16
        if (
            member.flag_bits & 1
            or member.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK}
            or member.file_size > MAX_FILE_BYTES
            or member.file_size > max(1, member.compress_size) * MAX_RATIO
        ):
            raise UpdateError("Unsupported ZIP entry or ZIP bomb size/ratio bound")
        total += member.file_size
        if total > MAX_TOTAL_BYTES:
            raise UpdateError("Archive expanded size exceeds bound")
    validate_tree(raw)
    roots = {name.split("/")[0] for name in raw}
    prefix = ""
    if len(roots) == 1:
        candidate = next(iter(roots))
        if re.fullmatch(r"seed-cinema-studio-[A-Za-z0-9._-]+", candidate):
            prefix = candidate + "/"
    result = []
    for member in members:
        name = member.filename.rstrip("/")
        if prefix and name == prefix[:-1]:
            continue
        if prefix:
            name = name.removeprefix(prefix)
        result.append((name, member))
    if not any(not member.is_dir() for _, member in result):
        raise UpdateError("Archive has no file inventory")
    return result


def extract_archive(archive: Path, stage: Path) -> Inventory:
    archive_data = read_regular(
        archive.parent.resolve(strict=True), archive.name, MAX_ZIP_BYTES
    )
    entries: Inventory = {}
    try:
        with zipfile.ZipFile(io.BytesIO(archive_data)) as bundle:
            members = archive_members(bundle)
            for name, member in members:
                if member.is_dir():
                    continue
                with bundle.open(member) as stream:
                    data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) != member.file_size or len(data) > MAX_FILE_BYTES:
                    raise UpdateError(
                        "ZIP entry size does not match validated inventory"
                    )
                alias = expected_alias(name)
                if alias is not None:
                    if data != alias.encode("ascii"):
                        raise UpdateError(f"Unexpected repository alias target: {name}")
                    entry: Descriptor = {"kind": "alias", "target": alias}
                elif stat.S_ISLNK(member.external_attr >> 16):
                    raise UpdateError(f"Arbitrary symlink rejected: {name}")
                else:
                    entry = {
                        "kind": "file",
                        "sha256": digest(data),
                        "mode": 0o755
                        if (member.external_attr >> 16) & 0o111
                        else 0o644,
                    }
                entries[name] = entry
                destination = stage / "files" / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        RuntimeError,
        OSError,
        EOFError,
        zlib.error,
    ) as error:
        raise UpdateError("Malformed or unreadable ZIP archive") from error
    validate_alias_targets(entries)
    manifest = stage / "files" / SOURCE_PATH
    if manifest.exists():
        validate_source(
            decode_json(read_regular(stage / "files", SOURCE_PATH, MAX_JSON_BYTES))
        )
    return entries


def validate_alias_targets(entries: Inventory) -> None:
    managed = {name for name in entries if not protected(name)}
    for name, entry in entries.items():
        if entry["kind"] != "alias":
            continue
        target = str(PurePosixPath(name).parent / entry["target"])
        normalized = os.path.normpath(target).replace(os.sep, "/")
        if (
            normalized.startswith(("../", "/"))
            or protected(normalized)
            or not any(
                path == normalized or path.startswith(normalized + "/")
                for path in managed
            )
        ):
            raise UpdateError(
                f"Repository alias lacks an inventoried safe target: {name}"
            )
        if normalized in entries and entries[normalized]["kind"] == "alias":
            raise UpdateError("Alias chains are not allowed")


def blocked_path(name: str, workspace: Inventory, folded: dict[str, list[str]]) -> bool:
    parts = name.split("/")
    for length in range(1, len(parts) + 1):
        prefix = "/".join(parts[:length])
        matching = folded.get(prefix.casefold(), [])
        if not matching:
            continue
        if len(matching) != 1 or matching[0] != prefix:
            return True
        local_name = matching[0]
        if local_name != name and workspace[local_name]["kind"] != "directory":
            return True
    current = workspace.get(name)
    if current is None:
        return False
    if current["kind"] not in {"file", "alias"}:
        return True
    return current["kind"] == "alias" and (
        expected_alias(name) is None or current["target"] != expected_alias(name)
    )


def classify(
    name: str,
    entry: Descriptor,
    workspace: Inventory,
    base: Inventory,
    folded: dict[str, list[str]],
) -> str:
    if protected(name):
        return "protected"
    if blocked_path(name, workspace, folded):
        return "blocked"
    local = descriptor(workspace.get(name))
    previous = base.get(name)
    if local == entry:
        return "unchanged"
    if (
        entry["kind"] == "alias"
        and local is not None
        and local.get("kind") == "file"
        and local["sha256"] == digest(entry["target"].encode("ascii"))
        and previous is None
    ):
        return "alias-rebuild"
    if previous is None:
        return "upstream-only" if local is None else "conflict"
    if local == previous:
        return "upstream-only"
    if entry == previous:
        return "local-only"
    return "conflict"


def preview_paths(
    entries: Inventory, workspace: Inventory, base: Inventory
) -> list[dict[str, str]]:
    folded: dict[str, list[str]] = {}
    for name in workspace:
        folded.setdefault(name.casefold(), []).append(name)
    rows = [
        {"path": name, "classification": classify(name, entry, workspace, base, folded)}
        for name, entry in sorted(entries.items())
    ]
    for name in sorted(set(workspace) | set(base)):
        if (
            protected(name)
            or name in entries
            or workspace.get(name, {}).get("kind") == "directory"
        ):
            continue
        rows.append(
            {
                "path": name,
                "classification": "upstream-removed-preserved"
                if name in base
                else "local-only",
            }
        )
    return rows


def directory_identity(root: Path) -> list[int]:
    identity = root.stat()
    return [identity.st_dev, identity.st_ino, stat.S_IMODE(identity.st_mode)]


def preview(
    root: Path, archive: Path, source: str, revision: str, stage: Path | None = None
) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if source != REPOSITORY:
        raise UpdateError(f"User-provided source must identify {REPOSITORY}")
    validate_revision(revision)
    if (root / SOURCE_PATH).exists() or (root / SOURCE_PATH).is_symlink():
        read_source(root)
    state, base_snapshot = read_state(root)
    stage = stage or external_directory(root)
    if stage.is_relative_to(root) or stage.is_symlink():
        raise UpdateError("Staging must be a real directory outside the workspace")
    try:
        entries = extract_archive(archive, stage)
        workspace = inventory(root)
        paths = preview_paths(entries, workspace, state["hashes"])
        plan = {
            "schema_version": 1,
            "workspace": str(root),
            "repository": source,
            "revision": revision,
            "transaction": uuid.uuid4().hex,
            "entries": entries,
            "workspace_snapshot": workspace,
            "base_snapshot": base_snapshot,
            "base": state,
            "staging_snapshot": inventory(stage, protect_local=False),
            "paths": paths,
            "workspace_identity": directory_identity(root),
            "staging_identity": directory_identity(stage),
        }
        data = encode_json(plan)
        if len(data) > MAX_JSON_BYTES:
            raise UpdateError("Preview plan exceeds size bound")
        plan_path = stage / "plan.json"
        plan_path.write_bytes(data)
        return {
            "status": "preview",
            "repository": source,
            "revision": revision,
            "plan": str(plan_path),
            "plan_sha256": digest(data),
            "paths": paths,
            "downloaded": False,
        }
    except BaseException:
        remove_staging(stage)
        raise


def download_preview(root: Path, revision: str) -> dict[str, Any]:
    root = root.resolve(strict=True)
    read_source(root)
    if not SHA_PATTERN.fullmatch(revision):
        raise UpdateError("Codeload download requires a full pinned commit SHA")
    stage = external_directory(root)
    archive = stage / "source.zip"
    url = f"https://codeload.github.com/{REPOSITORY}/zip/{revision}"
    try:
        with open_url(url) as response, archive.open("xb") as stream:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_ZIP_BYTES:
                    raise UpdateError("ZIP download exceeds size bound")
                stream.write(chunk)
    except BaseException as error:
        remove_staging(stage)
        if isinstance(error, (OSError, urllib.error.URLError)):
            raise network_error(error) from error
        raise
    result = preview(root, archive, REPOSITORY, revision, stage)
    result["downloaded"] = True
    result["url"] = url
    return result


def verify_plan(plan_path: Path, expected_hash: str) -> tuple[dict[str, Any], Path]:
    if not HASH_PATTERN.fullmatch(expected_hash):
        raise UpdateError("Apply requires the SHA-256 printed by preview")
    if plan_path.is_symlink() or plan_path.parent.is_symlink():
        raise UpdateError("Preview plan cannot be a symlink")
    data = read_regular(plan_path.parent, plan_path.name, MAX_JSON_BYTES)
    if digest(data) != expected_hash:
        raise UpdateError("Preview plan changed; preview again")
    plan = decode_json(data)
    if (
        not isinstance(plan, dict)
        or set(plan)
        != {
            "schema_version",
            "workspace",
            "repository",
            "revision",
            "transaction",
            "entries",
            "workspace_snapshot",
            "base_snapshot",
            "base",
            "staging_snapshot",
            "paths",
            "workspace_identity",
            "staging_identity",
        }
        or type(plan["schema_version"]) is not int
        or plan["schema_version"] != 1
        or not isinstance(plan["entries"], dict)
        or not plan["entries"]
        or len(plan["entries"]) > MAX_ENTRIES
        or not isinstance(plan["workspace_snapshot"], dict)
        or not isinstance(plan["base"], dict)
        or not isinstance(plan["base"].get("hashes"), dict)
    ):
        raise UpdateError("Malformed preview plan")
    root = Path(plan["workspace"])
    if root != root.resolve(strict=True) or plan_path.resolve().is_relative_to(root):
        raise UpdateError("Workspace or staging location changed")
    if plan["repository"] != REPOSITORY:
        raise UpdateError("Preview repository identity changed")
    validate_revision(plan["revision"])
    for name, entry in plan["entries"].items():
        validate_descriptor(name, entry, allow_protected=True)
    validate_tree({name: False for name in plan["entries"]})
    validate_alias_targets(plan["entries"])
    if plan["paths"] != preview_paths(
        plan["entries"], plan["workspace_snapshot"], plan["base"]["hashes"]
    ):
        raise UpdateError("Preview classifications changed")
    return cast(dict[str, Any], plan), root


def verify_workspace(root: Path, expected: Inventory, entries: Inventory) -> None:
    workspace = inventory(root)
    managed = {name: entry for name, entry in workspace.items() if not protected(name)}
    expected_managed = {
        name: entry for name, entry in expected.items() if not protected(name)
    }
    if managed != expected_managed:
        raise UpdateError("Stale workspace snapshot; preview again")
    folded: dict[str, list[str]] = {}
    for name in workspace:
        folded.setdefault(name.casefold(), []).append(name)
    for name in entries:
        if not protected(name) and blocked_path(name, workspace, folded):
            raise UpdateError(f"Structurally blocked path: {name}; preview again")


def verify_snapshots(root: Path, stage: Path, plan: dict[str, Any]) -> None:
    if (
        directory_identity(root) != plan["workspace_identity"]
        or directory_identity(stage) != plan["staging_identity"]
    ):
        raise UpdateError("Workspace or staging root changed; preview again")
    verify_workspace(root, plan["workspace_snapshot"], plan["entries"])
    state, snapshot = read_state(root)
    if snapshot != plan["base_snapshot"] or state != plan["base"]:
        raise UpdateError("Stale installed base snapshot; preview again")
    if inventory(stage, {"plan.json"}, protect_local=False) != plan["staging_snapshot"]:
        raise UpdateError("Stale staging snapshot; preview again")


def selected_changes(plan: dict[str, Any], resolutions: dict[str, str]) -> list[str]:
    rows = {row["path"]: row["classification"] for row in plan["paths"]}
    for name, choice in resolutions.items():
        validate_path(name)
        if name not in plan["entries"] or choice not in {"local", "upstream"}:
            raise UpdateError(
                "Resolution must be an inventoried path=local or path=upstream"
            )
        if protected(name) or rows[name] in {"protected", "blocked"}:
            raise UpdateError(
                f"Cannot resolve a protected or structurally blocked path: {name}"
            )
    changes = []
    for name in plan["entries"]:
        if protected(name):
            continue
        classification = rows[name]
        if classification == "blocked":
            raise UpdateError(f"Structurally blocked path: {name}")
        if classification == "conflict" and name not in resolutions:
            raise UpdateError(f"Unresolved conflict: {name}")
        if resolutions.get(name) == "local":
            continue
        if classification in {"upstream-only", "alias-rebuild"} or (
            resolutions.get(name) == "upstream" and classification != "unchanged"
        ):
            changes.append(name)
    return sorted(changes)


def verify_prospective_aliases(plan: dict[str, Any], changes: list[str]) -> None:
    prospective = {
        name: cast(Descriptor, descriptor(entry))
        for name, entry in plan["workspace_snapshot"].items()
    }
    for name in changes:
        prospective[name] = plan["entries"][name]
        for parent in PurePosixPath(name).parents:
            if str(parent) != ".":
                prospective.setdefault(str(parent), {"kind": "directory"})
    for name in changes:
        entry = plan["entries"][name]
        if entry["kind"] != "alias":
            continue
        target = os.path.normpath(
            str(PurePosixPath(name).parent / entry["target"])
        ).replace(os.sep, "/")
        target_entry = prospective.get(target)
        if target_entry is None or target_entry["kind"] not in {"file", "directory"}:
            raise UpdateError(
                f"Approved resolutions leave a missing or unsafe alias target: {name}"
            )
        for parent in PurePosixPath(target).parents:
            if (
                str(parent) != "."
                and prospective.get(str(parent), {}).get("kind") != "directory"
            ):
                raise UpdateError(
                    f"Approved resolutions leave an unsafe alias parent: {name}"
                )


def ensure_local_area(root: Path) -> None:
    make_parents(root, STATE_PATH, [])
    local = root / ".agents/local"
    ignore_name = ".agents/local/.gitignore"
    ignore = local / ".gitignore"
    if not ignore.exists() and not ignore.is_symlink():
        with directory_handle(root, ".agents/local") as handle:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            with os.fdopen(
                os.open(".gitignore", flags, 0o600, dir_fd=handle), "wb"
            ) as stream:
                stream.write(b"update-state.json\nupdate.lock\n.gitignore\n")
    contents = read_regular(root, ignore_name).decode("utf-8").splitlines()
    patterns = [
        line.strip() for line in contents if line.strip() and not line.startswith("#")
    ]
    if any(line.startswith("!") for line in patterns) or not (
        "*" in patterns or {"update-state.json", "update.lock"}.issubset(patterns)
    ):
        raise UpdateError(
            "Local ignore rules must protect update-state.json and update.lock"
        )


def make_parents(root: Path, name: str, created: list[Path]) -> None:
    parent, _, _ = name.rpartition("/")
    with directory_handle(root, parent, created):
        pass


def atomic_file(path: Path, data: bytes, mode: int) -> None:
    descriptor_number, temporary = tempfile.mkstemp(
        prefix=".seed-update-", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor_number, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def install_entry(root: Path, name: str, entry: Descriptor, contents: bytes) -> None:
    parent, _, leaf = name.rpartition("/")
    with directory_handle(root, parent) as handle:
        temporary = f".seed-update-{uuid.uuid4().hex}"
        temporary_created = False
        try:
            if entry["kind"] == "alias":
                os.symlink(entry["target"], temporary, dir_fd=handle)
                temporary_created = True
            else:
                if digest(contents) != entry["sha256"]:
                    raise UpdateError("Staged replacement hash changed")
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                number = os.open(temporary, flags, entry["mode"], dir_fd=handle)
                temporary_created = True
                with os.fdopen(number, "wb") as stream:
                    stream.write(contents)
                    stream.flush()
                    os.fchmod(stream.fileno(), entry["mode"])
                    os.fsync(stream.fileno())
            os.replace(temporary, leaf, src_dir_fd=handle, dst_dir_fd=handle)
        finally:
            if temporary_created:
                try:
                    os.unlink(temporary, dir_fd=handle)
                except FileNotFoundError:
                    pass


def restore_entry(
    root: Path,
    name: str,
    previous: Descriptor | None,
    contents: bytes,
    installed: Descriptor,
) -> None:
    check_parents(root, name)
    current = descriptor(snapshot_entry(root, name))
    if current == descriptor(previous):
        return
    if current not in (descriptor(previous), installed):
        raise UpdateError(f"Concurrent change prevents rollback: {name}")
    if previous is None:
        if current is not None:
            parent, _, leaf = name.rpartition("/")
            with directory_handle(root, parent) as handle:
                os.unlink(leaf, dir_fd=handle)
    else:
        install_entry(root, name, cast(Descriptor, descriptor(previous)), contents)


def backup_changes(
    root: Path,
    stage: Path,
    changes: list[str],
    plan: dict[str, Any],
    backup: Path,
    state_entry: Descriptor,
) -> tuple[dict[str, bytes], dict[str, bytes], dict[str, Any]]:
    incoming: dict[str, bytes] = {}
    original: dict[str, bytes] = {}
    previous: dict[str, Any] = {}
    for name in [*changes, STATE_PATH]:
        snapshot = snapshot_entry(root, name)
        previous[name] = snapshot
        contents = b""
        if snapshot is not None and snapshot["kind"] == "file":
            contents = read_regular(
                root, name, MAX_JSON_BYTES if name == STATE_PATH else MAX_FILE_BYTES
            )
            if digest(contents) != snapshot["sha256"]:
                raise UpdateError("Replacement changed while backing up")
        original[name] = contents
        if snapshot is not None:
            destination = backup / "files" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            atomic_file(destination, contents, 0o600)
        if name != STATE_PATH:
            payload = read_regular(stage / "files", name)
            entry = plan["entries"][name]
            expected = (
                digest(entry["target"].encode("ascii"))
                if entry["kind"] == "alias"
                else entry["sha256"]
            )
            if digest(payload) != expected:
                raise UpdateError(
                    "Staged replacement changed while preparing transaction"
                )
            incoming[name] = payload
    journal = {
        "status": "prepared",
        "workspace": str(root),
        "plan": str(stage / "plan.json"),
        "transaction": plan["transaction"],
        "previous": previous,
        "replacements": {
            **{name: plan["entries"][name] for name in changes},
            STATE_PATH: state_entry,
        },
        "started": [],
        "created_directories": [],
    }
    atomic_file(backup / "journal.json", encode_json(journal), 0o600)
    return incoming, original, journal


def verify_review(stage: Path, plan: dict[str, Any], expected_hash: str) -> None:
    if digest(read_regular(stage, "plan.json", MAX_JSON_BYTES)) != expected_hash:
        raise UpdateError("Preview plan changed during apply")
    if inventory(stage, {"plan.json"}, protect_local=False) != plan["staging_snapshot"]:
        raise UpdateError("Staging changed during apply")


def transact(
    root: Path,
    stage: Path,
    changes: list[str],
    plan: dict[str, Any],
    backup: Path,
    expected_hash: str,
) -> None:
    created: list[Path] = []
    started: list[tuple[str, Descriptor]] = []
    expected_workspace = dict(plan["workspace_snapshot"])
    state = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "revision": plan["revision"],
        "transaction": plan["transaction"],
        "hashes": {
            name: entry
            for name, entry in plan["entries"].items()
            if not protected(name)
        },
    }
    state_data = encode_json(state)
    state_entry = {"kind": "file", "sha256": digest(state_data), "mode": 0o600}
    incoming, original, journal = backup_changes(
        root, stage, changes, plan, backup, state_entry
    )
    try:
        verify_snapshots(root, stage, plan)
        verify_review(stage, plan, expected_hash)
        for name in [*changes, STATE_PATH]:
            if name == STATE_PATH:
                verify_review(stage, plan, expected_hash)
                verify_workspace(root, expected_workspace, plan["entries"])
            if snapshot_entry(root, name) != journal["previous"][name]:
                raise UpdateError(f"Workspace changed before replacement: {name}")
            make_parents(root, name, created)
            entry = state_entry if name == STATE_PATH else plan["entries"][name]
            started.append((name, entry))
            journal["started"] = [path for path, _ in started]
            journal["created_directories"] = [
                directory.relative_to(root).as_posix() for directory in created
            ]
            atomic_file(backup / "journal.json", encode_json(journal), 0o600)
            install_entry(
                root, name, entry, state_data if name == STATE_PATH else incoming[name]
            )
            if name != STATE_PATH:
                expected_workspace[name] = cast(Descriptor, snapshot_entry(root, name))
                for directory in created:
                    directory_name = directory.relative_to(root).as_posix()
                    expected_workspace[directory_name] = cast(
                        Descriptor, snapshot_entry(root, directory_name)
                    )
        verify_review(stage, plan, expected_hash)
        verify_workspace(root, expected_workspace, plan["entries"])
        if descriptor(snapshot_entry(root, STATE_PATH)) != state_entry:
            raise UpdateError("Installed state changed during apply")
        journal["status"] = "applied"
        atomic_file(backup / "journal.json", encode_json(journal), 0o600)
    except BaseException as error:
        failures = []
        for name, entry in reversed(started):
            try:
                restore_entry(
                    root, name, journal["previous"][name], original[name], entry
                )
            except (OSError, UpdateError):
                failures.append(name)
        for directory in reversed(created):
            directory_name = directory.relative_to(root).as_posix()
            parent, _, leaf = directory_name.rpartition("/")
            try:
                with directory_handle(root, parent) as handle:
                    os.rmdir(leaf, dir_fd=handle)
            except OSError:
                failures.append(directory_name)
        journal["status"] = "recovery-required" if failures else "rolled-back"
        journal["recovery_paths"] = failures
        atomic_file(backup / "journal.json", encode_json(journal), 0o600)
        if failures:
            raise UpdateError("Manual recovery required") from error
        raise UpdateError("Apply failed and rolled back") from error


def apply(
    plan_path: Path, expected_hash: str, confirm: bool, resolutions: dict[str, str]
) -> dict[str, Any]:
    if not confirm:
        raise UpdateError(
            "Apply requires explicit --confirm after reviewing the preview"
        )
    plan, root = verify_plan(plan_path, expected_hash)
    stage = plan_path.parent
    changes = selected_changes(plan, resolutions)
    verify_prospective_aliases(plan, changes)
    verify_snapshots(root, stage, plan)
    ensure_local_area(root)
    if ".agents" not in plan["workspace_snapshot"]:
        plan["workspace_snapshot"][".agents"] = snapshot_entry(root, ".agents")
    try:
        with directory_handle(root, ".agents/local") as handle:
            lock_number = os.open(
                "update.lock",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=handle,
            )
    except FileExistsError as error:
        raise UpdateError(
            "Update lock exists; do not steal it; inspect recovery state"
        ) from error
    backup: Path | None = None
    try:
        with os.fdopen(lock_number, "wb") as stream:
            backup = external_directory(root, "seed-update-backup-")
            stream.write(
                encode_json(
                    {
                        "pid": os.getpid(),
                        "backup": str(backup),
                        "plan": str(plan_path),
                        "transaction": plan["transaction"],
                    }
                )
            )
            stream.flush()
            os.fsync(stream.fileno())
        transact(root, stage, changes, plan, backup, expected_hash)
    except BaseException as error:
        if isinstance(error, (OSError, UpdateError)):
            message = (
                str(error)
                if isinstance(error, UpdateError)
                else "Update filesystem operation failed"
            )
            failure = UpdateError(f"{message}; backup: {backup}")
            failure.backup = backup
            raise failure from error
        raise
    finally:
        recovery_required = False
        if backup is not None and (backup / "journal.json").is_file():
            journal = decode_json((backup / "journal.json").read_bytes())
            recovery_required = journal["status"] in {"prepared", "recovery-required"}
        if not recovery_required:
            with directory_handle(root, ".agents/local") as handle:
                os.unlink("update.lock", dir_fd=handle)
    return {
        "status": "applied",
        "repository": REPOSITORY,
        "revision": plan["revision"],
        "replaced": changes,
        "backup": str(backup),
        "state": str(root / STATE_PATH),
    }


def resolution_arguments(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        name, separator, choice = value.rpartition("=")
        if not separator or name in result or choice not in {"local", "upstream"}:
            raise UpdateError(
                "Use unique --resolve PATH=local or --resolve PATH=upstream"
            )
        validate_path(name)
        result[name] = choice
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Preview safe ZIP updates; never executes downloaded code or initializes Git."
    )
    commands = result.add_subparsers(dest="command", required=True)
    discovery = commands.add_parser(
        "discover", help="Resolve the authoritative ref via GitHub API; no ZIP download"
    )
    discovery.add_argument("--workspace", type=Path, default=Path.cwd())
    preview_command = commands.add_parser(
        "preview", help="Stage and classify only; workspace files remain untouched"
    )
    preview_command.add_argument("--workspace", type=Path, default=Path.cwd())
    inputs = preview_command.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--zip", type=Path, help="User-provided local ZIP")
    inputs.add_argument(
        "--download",
        action="store_true",
        help="Explicit permission to download a pinned codeload ZIP",
    )
    preview_command.add_argument(
        "--source", help="User-provided owner/repository for a local ZIP"
    )
    preview_command.add_argument(
        "--revision", help="User-provided revision label or full SHA for --download"
    )
    apply_command = commands.add_parser(
        "apply", help="Apply an approved unchanged preview with external backups"
    )
    apply_command.add_argument("--plan", type=Path, required=True)
    apply_command.add_argument("--plan-sha256", required=True)
    apply_command.add_argument("--confirm", action="store_true")
    apply_command.add_argument(
        "--resolve", action="append", default=[], metavar="PATH=local|upstream"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "discover":
            result = discover(arguments.workspace.resolve(strict=True))
        elif arguments.command == "apply":
            result = apply(
                arguments.plan,
                arguments.plan_sha256,
                arguments.confirm,
                resolution_arguments(arguments.resolve),
            )
        elif arguments.download:
            if arguments.source:
                raise UpdateError("--source is for local ZIP input only")
            revision = arguments.revision or discover(arguments.workspace)["revision"]
            result = download_preview(arguments.workspace, revision)
        else:
            if not arguments.source or not arguments.revision:
                raise UpdateError(
                    "Local ZIP input requires user-provided --source and --revision"
                )
            result = preview(
                arguments.workspace, arguments.zip, arguments.source, arguments.revision
            )
        sys.stdout.write(encode_json(result).decode("utf-8"))
        return 0
    except (
        UpdateError,
        OSError,
        UnicodeError,
        KeyError,
        TypeError,
        RecursionError,
    ) as error:
        message = (
            str(error)
            if isinstance(error, UpdateError)
            else "Invalid or unreadable update input"
        )
        sys.stderr.write(json.dumps({"status": "error", "error": message}) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
