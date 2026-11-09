from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

MAX_BYTES = 32768
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


def safe_path(root: Path, relative: str) -> Path:
    current = root
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Workspace must be a real directory")
    parts = Path(relative).parts
    for index, part in enumerate(parts):
        current = current / part
        if current.is_symlink():
            raise ValueError("Preference paths cannot contain symlinks")
        if current.exists():
            mode = current.stat().st_mode
            if index < len(parts) - 1 and not stat.S_ISDIR(mode):
                raise ValueError("Preference parent must be a directory")
            if index == len(parts) - 1 and not stat.S_ISREG(mode):
                raise ValueError("Preference state must be a regular file")
    return current


def preference_path(root: Path, project: str | None = None) -> Path:
    if project is None:
        return safe_path(root, ".agents/local/preferences.json")
    if len(project) > 100 or not PROJECT_PATTERN.fullmatch(project):
        raise ValueError("Project must be a lowercase kebab-case identifier")
    return safe_path(root, f".agents/local/projects/{project}/preferences.json")


def read_state(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "absent"
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Preferences exceed size limit")
    data = path.read_bytes()
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


def show(root: Path, project: str | None = None) -> dict[str, Any]:
    workspace, workspace_revision = read_state(preference_path(root))
    overrides, revision = (
        read_state(preference_path(root, project))
        if project is not None
        else (workspace, workspace_revision)
    )
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


def atomic_write(root: Path, path: Path, contents: bytes) -> None:
    relative = str(path.relative_to(root))
    safe_path(root, relative)
    descriptor, temporary = tempfile.mkstemp(prefix=".preferences-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(root, relative)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


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
    path = preference_path(root, project)
    current, revision = read_state(path)
    if revision != expected_revision:
        raise ValueError("Preference revision changed; re-read before saving")
    proposed = validate_preferences(merge_preferences(current, patch))
    contents = (
        json.dumps({"schema_version": 1, "preferences": proposed}, indent=2) + "\n"
    ).encode("utf-8")
    if len(contents) > MAX_BYTES:
        raise ValueError("Preferences exceed size limit")
    local = root / ".agents/local"
    local.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = safe_path(root, ".agents/local/preferences.lock")
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError("Preference writer lock exists; do not steal it") from error
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"pid": os.getpid()}, stream)
        if read_state(preference_path(root, project))[1] != expected_revision:
            raise ValueError("Preference revision changed; re-read before saving")
        ignore = safe_path(root, ".agents/local/.gitignore")
        if not ignore.exists():
            atomic_write(root, ignore, b"*\n")
        else:
            ignore_text = ignore.read_text(encoding="utf-8")
            if not ignore_text.splitlines() or ignore_text.splitlines()[-1] != "*":
                atomic_write(
                    root, ignore, (ignore_text.rstrip("\n") + "\n*\n").encode("utf-8")
                )
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        atomic_write(root, path, contents)
    finally:
        lock.unlink()
    return show(root, project)


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
