from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

MAX_BYTES = 32768
DESCRIPTOR_APIS = {os.open, os.stat, os.mkdir, os.unlink, os.rename}
REPLACE_API = os.replace
STAT_API = os.stat
PROJECT_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
CUSTOM_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}")
SENSITIVE_PATTERN = re.compile(
    r"bearer\s|(?:api[_ -]?key|access[_ -]?key|secret|password|credential|token|"
    r"account[_ -]?number|x-amz-signature|x-goog-signature)\b",
    re.IGNORECASE,
)
CHOICES = {
    "execution_mode": {"prompt_only", "agent"},
    "generation_priority": {"fast", "balanced", "quality"},
    "model_policy": {"workspace_default", "allow_verified_alternatives"},
    "review_mode": {"default", "strict"},
    "approval_mode": {"approve_for_me", "ask_for_approval"},
    "output_detail": {"concise", "detailed"},
    "default_aspect": {"9:16", "16:9", "1:1", "4:5", "3:4", "4:3"},
}
TEXT_FIELDS = {"language", "tone", "visual_style"}
DEFAULTS: dict[str, Any] = {
    "execution_mode": "agent",
    "generation_priority": "balanced",
    "model_policy": "workspace_default",
    "review_mode": "default",
    "approval_mode": "approve_for_me",
    "output_detail": "concise",
    "custom": {},
}


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate preference key")
        result[key] = value
    return result


def invalid_constant(value: str) -> Any:
    raise ValueError("Non-finite preference value")


def decode_json(contents: str) -> dict[str, Any]:
    if len(contents.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Preferences exceed size limit")
    try:
        result = json.loads(
            contents, object_pairs_hook=unique_object, parse_constant=invalid_constant
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Invalid preference JSON") from error
    if not isinstance(result, dict):
        raise TypeError("Preferences must be an object")
    return result


def validate_text(value: Any) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 1000
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("Preference text must be nonempty and at most 1000 characters")
    if SENSITIVE_PATTERN.search(value):
        raise ValueError("Potentially sensitive preference rejected")


def validate_preferences(value: Any, patch: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("Preferences must be an object")
    for key, entry in value.items():
        if key not in CHOICES and key not in TEXT_FIELDS and key != "custom":
            raise ValueError("Unknown preference field")
        if entry is None and patch:
            continue
        if key == "custom":
            if not isinstance(entry, dict) or len(entry) > 20:
                raise ValueError(
                    "Custom preferences must contain at most 20 text fields"
                )
            for custom_key, custom_value in entry.items():
                if not CUSTOM_PATTERN.fullmatch(custom_key) or SENSITIVE_PATTERN.search(
                    custom_key
                ):
                    raise ValueError(
                        "Invalid or potentially sensitive custom preference"
                    )
                if custom_value is not None or not patch:
                    validate_text(custom_value)
        elif key in CHOICES:
            if not isinstance(entry, str) or entry not in CHOICES[key]:
                raise ValueError("Unsupported preference choice")
        else:
            validate_text(entry)
    return value


def require_descriptor_runtime() -> None:
    if (
        os.name != "posix"
        or not all(
            getattr(os, flag, 0) for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")
        )
        or not DESCRIPTOR_APIS.issubset(os.supports_dir_fd)
        or STAT_API not in os.supports_follow_symlinks
        or not {"src_dir_fd", "dst_dir_fd"}.issubset(
            inspect.signature(REPLACE_API).parameters
        )
    ):
        raise ValueError(
            "Required no-follow descriptor APIs unavailable; use a safe native "
            "file-tool fallback or supported POSIX runtime; otherwise remain chat-only"
        )


def identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


def file_version(info: os.stat_result | None) -> tuple[int, ...] | None:
    if info is None:
        return None
    return (*identity(info), info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class PinnedWorkspace:
    def __init__(self, root: Path) -> None:
        require_descriptor_runtime()
        self.root = root.absolute()
        self.root_info = self.root.lstat()
        if not stat.S_ISDIR(self.root_info.st_mode):
            raise ValueError("Workspace must be a real directory")
        self.descriptors: list[int] = []
        self.bindings: list[tuple[int, str, int]] = []
        self.directories: dict[tuple[str, ...], int] = {}

    @contextmanager
    def opened(self) -> Iterator[PinnedWorkspace]:
        try:
            canonical = self.root.resolve(strict=True)
            descriptor = os.open(
                canonical.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            self.descriptors.append(descriptor)
            for part in canonical.parts[1:]:
                descriptor = self.open_child(descriptor, part)
            self.directories[()] = descriptor
            self.validate()
            yield self
        finally:
            for descriptor in reversed(self.descriptors):
                os.close(descriptor)

    def open_child(self, parent: int, name: str) -> int:
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISDIR(before.st_mode):
            raise ValueError("Preference parents must be real directories")
        descriptor = os.open(
            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
        )
        self.descriptors.append(descriptor)
        if identity(before) != identity(os.fstat(descriptor)):
            raise ValueError("Preference directory identity changed")
        self.bindings.append((parent, name, descriptor))
        return descriptor

    def validate(self) -> None:
        root_descriptor = self.directories.get(())
        if root_descriptor is not None and (
            identity(self.root.lstat()) != identity(self.root_info)
            or identity(os.fstat(root_descriptor)) != identity(self.root_info)
        ):
            raise ValueError("Workspace identity changed")
        for parent, name, descriptor in self.bindings:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode) or identity(info) != identity(
                os.fstat(descriptor)
            ):
                raise ValueError("Preference directory identity changed")

    def parent(self, path: Path, create: bool = False) -> int | None:
        parts = path.absolute().relative_to(self.root).parts
        if not parts or ".." in parts:
            raise ValueError("Preference path must remain inside the workspace")
        descriptor = self.directories[()]
        for index, part in enumerate(parts[:-1]):
            self.validate()
            key = parts[: index + 1]
            if key not in self.directories:
                try:
                    child = self.open_child(descriptor, part)
                except FileNotFoundError:
                    self.validate()
                    if not create:
                        return None
                    try:
                        os.mkdir(part, 0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    self.validate()
                    child = self.open_child(descriptor, part)
                self.directories[key] = child
            descriptor = self.directories[key]
        self.validate()
        return descriptor

    def file_info(self, parent: int, name: str) -> os.stat_result | None:
        try:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Preference state must be a regular non-symlink file")
        return info

    def read(self, path: Path) -> bytes | None:
        parent = self.parent(path)
        if parent is None:
            return None
        before = self.file_info(parent, path.name)
        self.validate()
        if before is None:
            return None
        if before.st_size > MAX_BYTES:
            raise ValueError("Preferences exceed size limit")
        descriptor = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or file_version(opened) != file_version(
                before
            ):
                raise ValueError("Preference file identity changed")
            self.validate()
            data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("Preferences exceed size limit")
            if file_version(os.fstat(stream.fileno())) != file_version(before):
                raise ValueError("Preference file changed during read")
            if file_version(self.file_info(parent, path.name)) != file_version(before):
                raise ValueError("Preference file identity changed")
            self.validate()
        return data


def unlink_owned(parent: int, name: str, owned: os.stat_result) -> None:
    try:
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    if identity(current) != identity(owned):
        raise ValueError("Preference cleanup identity changed; file left untouched")
    os.unlink(name, dir_fd=parent)


@contextmanager
def writer_lock(files: PinnedWorkspace) -> Iterator[None]:
    parent = files.parent(files.root / ".agents/local/preferences.lock", create=True)
    assert parent is not None
    files.validate()
    try:
        descriptor = os.open(
            "preferences.lock",
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
    except FileExistsError as error:
        raise ValueError("Preference writer lock exists; do not steal it") from error
    owned = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "w") as stream:
            files.validate()
            json.dump({"pid": os.getpid()}, stream)
        files.validate()
        yield
    finally:
        unlink_owned(parent, "preferences.lock", owned)


def preference_path(root: Path, project: str | None = None) -> Path:
    if project is None:
        return root / ".agents/local/preferences.json"
    if len(project) > 100 or not PROJECT_PATTERN.fullmatch(project):
        raise ValueError("Project must be a lowercase kebab-case identifier")
    return root / f".agents/local/projects/{project}/preferences.json"


def read_state(files: PinnedWorkspace, path: Path) -> tuple[dict[str, Any], str]:
    data = files.read(path)
    if data is None:
        return {}, "absent"
    try:
        document = decode_json(data.decode("utf-8"))
    except UnicodeError as error:
        raise ValueError("Invalid preference encoding") from error
    if (
        set(document) != {"schema_version", "preferences"}
        or type(document["schema_version"]) is not int
        or document["schema_version"] != 1
    ):
        raise ValueError("Invalid preference document")
    return (
        validate_preferences(document["preferences"]),
        hashlib.sha256(data).hexdigest(),
    )


def merge_preferences(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = dict(current)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif key == "custom":
            custom = dict(result.get("custom", {}))
            for custom_key, custom_value in value.items():
                if custom_value is None:
                    custom.pop(custom_key, None)
                else:
                    custom[custom_key] = custom_value
            result["custom"] = custom
        else:
            result[key] = value
    return result


def preference_result(
    workspace: dict[str, Any],
    workspace_revision: str,
    overrides: dict[str, Any],
    revision: str,
    project: str | None,
) -> dict[str, Any]:
    effective = merge_preferences(DEFAULTS, workspace)
    if project is not None:
        effective = merge_preferences(effective, overrides)
    return {
        "scope": project or "workspace",
        "configured": workspace_revision != "absent" or revision != "absent",
        "revision": revision,
        "workspace_revision": workspace_revision,
        "stored_preferences": overrides,
        "preferences": effective,
    }


def show(root: Path, project: str | None = None) -> dict[str, Any]:
    with PinnedWorkspace(root).opened() as files:
        workspace, workspace_revision = read_state(files, preference_path(root))
        overrides, revision = (
            read_state(files, preference_path(root, project))
            if project is not None
            else (workspace, workspace_revision)
        )
        files.validate()
        return preference_result(
            workspace, workspace_revision, overrides, revision, project
        )


def atomic_write(
    root: Path, path: Path, contents: bytes, files: PinnedWorkspace | None = None
) -> None:
    if files is None:
        with PinnedWorkspace(root).opened() as pinned:
            atomic_write(root, path, contents, pinned)
        return
    parent = files.parent(path)
    if parent is None:
        raise ValueError("Preference parent does not exist")
    before = files.file_info(parent, path.name)
    files.validate()
    temporary = ".preferences-" + secrets.token_hex(16)
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
        dir_fd=parent,
    )
    owned = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            files.validate()
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
            written = os.fstat(stream.fileno())
        files.validate()
        if file_version(files.file_info(parent, path.name)) != file_version(before):
            raise ValueError("Preference destination changed before replacement")
        if file_version(files.file_info(parent, temporary)) != file_version(written):
            raise ValueError("Preference temporary identity changed")
        os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
        files.validate()
    finally:
        unlink_owned(parent, temporary, owned)


def proposed_state(
    current: dict[str, Any],
    patch: dict[str, Any],
    revision: str,
    expected_revision: str,
) -> tuple[dict[str, Any], bytes]:
    if revision != expected_revision:
        raise ValueError("Preference revision changed; re-read before saving")
    proposed = validate_preferences(merge_preferences(current, patch))
    contents = (
        json.dumps({"schema_version": 1, "preferences": proposed}, indent=2) + "\n"
    ).encode("utf-8")
    if len(contents) > MAX_BYTES:
        raise ValueError("Preferences exceed size limit")
    return proposed, contents


def save(
    root: Path,
    patch: dict[str, Any],
    expected_revision: str,
    project: str | None = None,
) -> dict[str, Any]:
    validate_preferences(patch, patch=True)
    if expected_revision != "absent" and not re.fullmatch(
        r"[0-9a-f]{64}", expected_revision
    ):
        raise ValueError("Invalid expected preference revision")
    with PinnedWorkspace(root).opened() as files:
        path = preference_path(root, project)
        read_state(files, preference_path(root))
        current, revision = read_state(files, path)
        proposed_state(current, patch, revision, expected_revision)
        with writer_lock(files):
            workspace, workspace_revision = read_state(files, preference_path(root))
            current, revision = (
                read_state(files, path)
                if project is not None
                else (workspace, workspace_revision)
            )
            proposed, contents = proposed_state(
                current, patch, revision, expected_revision
            )
            ignore = root / ".agents/local/.gitignore"
            ignore_data = files.read(ignore)
            ignore_text = "" if ignore_data is None else ignore_data.decode("utf-8")
            if not ignore_text.splitlines() or ignore_text.splitlines()[-1] != "*":
                ignore_contents = (
                    b"*\n"
                    if ignore_data is None
                    else (ignore_text.rstrip("\n") + "\n*\n").encode("utf-8")
                )
                if len(ignore_contents) > MAX_BYTES:
                    raise ValueError("Local ignore rules exceed size limit")
                atomic_write(root, ignore, ignore_contents, files)
            files.parent(path, create=True)
            atomic_write(root, path, contents, files)
            saved_revision = hashlib.sha256(contents).hexdigest()
            return preference_result(
                workspace if project is not None else proposed,
                workspace_revision if project is not None else saved_revision,
                proposed,
                saved_revision,
                project,
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read or explicitly save local Studio preferences"
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("show", "set"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--project")
        if command == "set":
            subparser.add_argument("--patch", required=True)
            subparser.add_argument("--expected-revision", required=True)
            subparser.add_argument("--confirm", action="store_true", required=True)
    arguments = parser.parse_args()
    try:
        root = arguments.root.absolute()
        result = (
            show(root, arguments.project)
            if arguments.command == "show"
            else save(
                root,
                decode_json(arguments.patch),
                arguments.expected_revision,
                arguments.project,
            )
        )
        print(json.dumps(result, indent=2))
        return 0
    except ValueError as error:
        print(json.dumps({"error": str(error)}))
        return 2
    except (OSError, TypeError, RecursionError):
        print(
            json.dumps(
                {"error": "Cannot read or save preference state; inspect local paths"}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
