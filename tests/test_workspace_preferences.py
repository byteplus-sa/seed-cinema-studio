import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch as mock_patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/scripts/workspace_preferences.py"
SPEC = importlib.util.spec_from_file_location("workspace_preferences", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
preferences = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preferences)


class WorkspacePreferenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / ".agents").mkdir()

    def run_preferences(self, *arguments, success=True):
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--root", str(self.root), *arguments],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def save(self, patch, revision="absent", project=None):
        arguments = [
            "set",
            "--patch",
            json.dumps(patch),
            "--expected-revision",
            revision,
            "--confirm",
        ]
        if project is not None:
            arguments.extend(["--project", project])
        return self.run_preferences(*arguments)

    def test_fresh_workspace_show_is_read_only_and_keeps_existing_policy(self):
        result = self.run_preferences("show")
        self.assertFalse(result["configured"])
        self.assertEqual(result["revision"], "absent")
        self.assertEqual(result["preferences"]["execution_mode"], "agent")
        self.assertFalse((self.root / ".agents/local").exists())

    def test_preferences_survive_fresh_process_and_merge_partial_updates(self):
        first = self.save(
            {
                "execution_mode": "prompt_only",
                "generation_priority": "fast",
                "language": "English",
            }
        )
        self.save({"output_detail": "concise"}, first["revision"])
        result = self.run_preferences("show")
        self.assertTrue(result["configured"])
        self.assertEqual(result["preferences"]["execution_mode"], "prompt_only")
        self.assertEqual(result["preferences"]["generation_priority"], "fast")
        self.assertEqual(result["preferences"]["language"], "English")
        self.assertEqual(result["preferences"]["output_detail"], "concise")
        self.assertFalse((self.root / "projects").exists())

    def test_project_overrides_do_not_change_workspace_or_other_projects(self):
        self.save({"execution_mode": "prompt_only", "language": "English"})
        self.save(
            {"language": "Japanese", "generation_priority": "quality"},
            project="short-film",
        )
        scoped = self.run_preferences("show", "--project", "short-film")
        other = self.run_preferences("show", "--project", "another-film")
        self.assertEqual(scoped["preferences"]["language"], "Japanese")
        self.assertEqual(scoped["preferences"]["execution_mode"], "prompt_only")
        self.assertEqual(other["preferences"]["language"], "English")
        self.assertEqual(
            self.run_preferences("show")["preferences"]["language"], "English"
        )

    def test_null_patch_removes_override_and_inherits_workspace_again(self):
        self.save({"language": "English"})
        first = self.save({"language": "Japanese"}, project="short-film")
        self.save({"language": None}, first["revision"], project="short-film")
        self.assertEqual(
            self.run_preferences("show", "--project", "short-film")["preferences"][
                "language"
            ],
            "English",
        )

    def test_custom_preferences_merge_without_dropping_unrelated_choices(self):
        first = self.save(
            {"custom": {"caption_style": "Sentence case", "music_style": "Ambient"}}
        )
        self.save({"custom": {"caption_style": "Title case"}}, first["revision"])
        result = self.run_preferences("show")
        self.assertEqual(
            result["preferences"]["custom"],
            {"caption_style": "Title case", "music_style": "Ambient"},
        )

    def test_project_custom_preferences_inherit_workspace_custom_preferences(self):
        self.save(
            {"custom": {"caption_style": "Sentence case", "music_style": "Ambient"}}
        )
        self.save({"custom": {"caption_style": "Title case"}}, project="short-film")
        result = self.run_preferences("show", "--project", "short-film")
        self.assertEqual(
            result["preferences"]["custom"],
            {"caption_style": "Title case", "music_style": "Ambient"},
        )

    def test_write_requires_confirmation_and_expected_revision(self):
        for arguments in (
            ["set", "--patch", "{}", "--expected-revision", "absent"],
            ["set", "--patch", "{}", "--confirm"],
        ):
            with self.subTest(arguments=arguments):
                process = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(SCRIPT),
                        "--root",
                        str(self.root),
                        *arguments,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertNotEqual(process.returncode, 0)
                self.assertFalse((self.root / ".agents/local").exists())

    def test_stale_revision_does_not_overwrite_newer_preferences(self):
        first = self.save({"language": "English"})
        self.save({"language": "Japanese"}, first["revision"])
        result = self.run_preferences(
            "set",
            "--patch",
            '{"language":"French"}',
            "--expected-revision",
            first["revision"],
            "--confirm",
            success=False,
        )
        self.assertIn("revision", result["error"].lower())
        self.assertEqual(
            self.run_preferences("show")["preferences"]["language"], "Japanese"
        )

    def test_invalid_patch_is_rejected_without_creating_state(self):
        patches = (
            "null",
            "[]",
            '{"execution_mode":"automatic"}',
            '{"review_mode":null,"language":""}',
            '{"unknown":true}',
            '{"generation_priority":false}',
            '{"language":123}',
            '{"language":"English","language":"Japanese"}',
            '{"custom":{"sample":NaN}}',
            '{"custom":{"caption_style":["Title case"]}}',
            json.dumps({"visual_style": "x" * 1001}),
        )
        for patch in patches:
            with self.subTest(patch=patch[:100]):
                self.run_preferences(
                    "set",
                    "--patch",
                    patch,
                    "--expected-revision",
                    "absent",
                    "--confirm",
                    success=False,
                )
                self.assertFalse((self.root / ".agents/local").exists())

    def test_obvious_sensitive_preferences_are_rejected_without_echoing_values(self):
        for patch in (
            {"custom": {"api_key": "dummy-sensitive-value"}},
            {"language": "Bearer dummy-sensitive-value"},
            {"custom": {"reference": "https://example.test/?X-Amz-Signature=dummy"}},
        ):
            with self.subTest(patch=patch):
                result = self.run_preferences(
                    "set",
                    "--patch",
                    json.dumps(patch),
                    "--expected-revision",
                    "absent",
                    "--confirm",
                    success=False,
                )
                self.assertNotIn("dummy", result["error"])
                self.assertFalse((self.root / ".agents/local").exists())

    def test_corrupted_preferences_are_not_silently_reset(self):
        path = self.root / ".agents/local/preferences.json"
        path.parent.mkdir()
        documents = (
            "null",
            '{"schema_version":true,"preferences":{}}',
            '{"schema_version":2,"preferences":{}}',
            '{"schema_version":1,"preferences":{"review_mode":"unknown"}}',
            '{"schema_version":1,"preferences":{},"unexpected":true}',
            '{"schema_version":1,"schema_version":1,"preferences":{}}',
        )
        for document in documents:
            with self.subTest(document=document):
                path.write_text(document)
                self.run_preferences("show", success=False)
                self.assertEqual(path.read_text(), document)

    def test_unsafe_project_identifiers_are_rejected(self):
        for project in ("../outside", "/tmp/outside", "UPPERCASE", "a/b", ".", ""):
            with self.subTest(project=project):
                self.run_preferences("show", "--project", project, success=False)

    def test_symlinked_local_state_and_preference_files_are_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        local = self.root / ".agents/local"
        local.symlink_to(outside, target_is_directory=True)
        self.run_preferences("show", success=False)
        local.unlink()
        local.mkdir()
        file = outside / "preferences.json"
        file.write_text('{"schema_version":1,"preferences":{}}')
        (local / "preferences.json").symlink_to(file)
        self.run_preferences("show", success=False)
        self.assertEqual(file.read_text(), '{"schema_version":1,"preferences":{}}')

    def test_existing_writer_lock_is_not_stolen(self):
        local = self.root / ".agents/local"
        local.mkdir()
        lock = local / "preferences.lock"
        lock.write_text("another writer")
        self.run_preferences(
            "set",
            "--patch",
            '{"language":"English"}',
            "--expected-revision",
            "absent",
            "--confirm",
            success=False,
        )
        self.assertEqual(lock.read_text(), "another writer")
        self.assertFalse((local / "preferences.json").exists())

    def test_saved_preferences_have_private_permissions_and_local_ignore_rules(self):
        self.save({"language": "English"})
        local = self.root / ".agents/local"
        self.assertIn("*", (local / ".gitignore").read_text().splitlines())
        if sys.platform != "win32":
            self.assertEqual((local / "preferences.json").stat().st_mode & 0o777, 0o600)

    def test_setup_after_zip_update_preserves_existing_local_ignore_rules(self):
        local = self.root / ".agents/local"
        local.mkdir()
        ignore = local / ".gitignore"
        ignore.write_text("update-state.json\nupdate.lock\n.gitignore\n")
        self.save({"execution_mode": "prompt_only"})
        self.assertTrue(
            ignore.read_text().startswith("update-state.json\nupdate.lock\n")
        )
        self.assertEqual(ignore.read_text().splitlines()[-1], "*")

    def test_oversized_ignore_append_rejects_without_changing_saved_state(self):
        workspace = self.save({"language": "English"})
        project = self.save({"language": "Japanese"}, project="existing-film")
        ignore = self.root / ".agents/local/.gitignore"
        for contents in (b"#" + b"x" * 32766, b"#" + b"\xc3\xa9" * 16383):
            for scope, revision in (
                (None, workspace["revision"]),
                ("new-film", "absent"),
                ("existing-film", project["revision"]),
            ):
                with self.subTest(scope=scope, multibyte=b"\xc3" in contents):
                    ignore.write_bytes(contents)
                    before = self.snapshot(self.root)
                    arguments = [
                        "set",
                        "--patch",
                        '{"generation_priority":"quality"}',
                        "--expected-revision",
                        revision,
                        "--confirm",
                    ]
                    if scope is not None:
                        arguments.extend(["--project", scope])
                    result = self.run_preferences(*arguments, success=False)
                    self.assertIn("size limit", result["error"])
                    self.assertEqual(self.snapshot(self.root), before)
                    self.assertFalse(
                        (self.root / ".agents/local/projects/new-film").exists()
                    )

    def test_ignore_append_at_size_limit_remains_usable_on_later_saves(self):
        local = self.root / ".agents/local"
        local.mkdir()
        ignore = local / ".gitignore"
        original = b"#" + b"x" * 32764
        ignore.write_bytes(original)
        first = self.save({"language": "English"})
        expected = original + b"\n*\n"
        self.assertEqual(len(expected), 32768)
        self.assertEqual(ignore.read_bytes(), expected)
        self.save({"generation_priority": "fast"}, first["revision"])
        self.save({"language": "Japanese"}, project="short-film")
        self.assertEqual(ignore.read_bytes(), expected)
        self.assertEqual(
            self.run_preferences("show")["preferences"]["generation_priority"], "fast"
        )
        self.assertEqual(
            self.run_preferences("show", "--project", "short-film")["preferences"][
                "language"
            ],
            "Japanese",
        )

    def snapshot(self, directory):
        return {
            str(path.relative_to(directory)): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in directory.rglob("*")
            if path.is_file()
        }

    def test_atomic_replace_parent_swap_cannot_redirect_writes(self):
        local = self.root / ".agents/local"
        local.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "preferences.json").write_bytes(b"outside state")
        relocated = self.root / "relocated"
        replace = os.replace
        attacked = False
        outside_before = None

        def swap_before_replace(source, destination, **kwargs):
            nonlocal attacked, outside_before
            attacked = True
            (outside / Path(source).name).write_bytes(b"outside temporary sentinel")
            outside_before = self.snapshot(outside)
            local.rename(relocated)
            local.symlink_to(outside, target_is_directory=True)
            return replace(source, destination, **kwargs)

        with mock_patch.object(
            preferences.os, "replace", side_effect=swap_before_replace
        ):
            try:
                preferences.atomic_write(
                    self.root, local / "preferences.json", b"new private state"
                )
            except (OSError, ValueError):
                pass
        self.assertTrue(attacked)
        self.assertEqual(self.snapshot(outside), outside_before)
        self.assertFalse(list(relocated.glob(".preferences-*")))

    def test_failed_write_cleanup_uses_original_directory_after_parent_swap(self):
        local = self.root / ".agents/local"
        local.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        relocated = self.root / "relocated"
        outside_before = None

        def swap_and_fail(descriptor):
            nonlocal outside_before
            temporary = next(local.glob(".preferences-*"))
            (outside / temporary.name).write_bytes(b"outside cleanup sentinel")
            outside_before = self.snapshot(outside)
            local.rename(relocated)
            local.symlink_to(outside, target_is_directory=True)
            raise OSError("injected flush failure")

        with (
            mock_patch.object(preferences.os, "fsync", side_effect=swap_and_fail),
            self.assertRaises(OSError),
        ):
            preferences.atomic_write(
                self.root, local / "preferences.json", b"new private state"
            )
        self.assertEqual(self.snapshot(outside), outside_before)
        self.assertFalse(list(relocated.glob(".preferences-*")))
        self.assertFalse((relocated / "preferences.json").exists())

    def test_save_failure_cleans_original_lock_not_outside_lock(self):
        self.save({"language": "English"})
        local = self.root / ".agents/local"
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "preferences.lock").write_bytes(b"outside lock sentinel")
        relocated = self.root / "relocated"
        original = (local / "preferences.json").read_bytes()
        outside_before = None

        def swap_and_fail(source, destination, **kwargs):
            nonlocal outside_before
            (outside / Path(source).name).write_bytes(b"outside cleanup sentinel")
            outside_before = self.snapshot(outside)
            local.rename(relocated)
            local.symlink_to(outside, target_is_directory=True)
            raise OSError("injected replacement failure")

        revision = preferences.show(self.root)["revision"]
        with (
            mock_patch.object(preferences.os, "replace", side_effect=swap_and_fail),
            self.assertRaises(OSError),
        ):
            preferences.save(self.root, {"language": "Japanese"}, revision)
        self.assertEqual(self.snapshot(outside), outside_before)
        self.assertEqual((relocated / "preferences.json").read_bytes(), original)
        self.assertFalse((relocated / "preferences.lock").exists())
        self.assertFalse(list(relocated.glob(".preferences-*")))

    def test_parent_creation_race_does_not_create_outside_local_state(self):
        agents = self.root / ".agents"
        outside = self.root / "outside"
        outside.mkdir()
        relocated = self.root / "relocated"
        mkdir = os.mkdir
        attacked = False

        def swap_before_mkdir(path, mode=0o777, **kwargs):
            nonlocal attacked
            if Path(path).name == "local" and not attacked:
                attacked = True
                agents.rename(relocated)
                agents.symlink_to(outside, target_is_directory=True)
            return mkdir(path, mode, **kwargs)

        with (
            mock_patch.object(preferences.os, "mkdir", side_effect=swap_before_mkdir),
            self.assertRaises((OSError, ValueError)),
        ):
            preferences.save(self.root, {"language": "English"}, "absent")
        self.assertTrue(attacked)
        self.assertEqual(list(outside.iterdir()), [])

    def test_lock_creation_race_does_not_write_outside_state(self):
        local = self.root / ".agents/local"
        local.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        relocated = self.root / "relocated"
        open_file = os.open
        attacked = False

        def swap_before_open(path, flags, mode=0o777, **kwargs):
            nonlocal attacked
            if Path(path).name == "preferences.lock" and not attacked:
                attacked = True
                local.rename(relocated)
                local.symlink_to(outside, target_is_directory=True)
            return open_file(path, flags, mode, **kwargs)

        with (
            mock_patch.object(preferences.os, "open", side_effect=swap_before_open),
            self.assertRaises((OSError, ValueError)),
        ):
            preferences.save(self.root, {"language": "English"}, "absent")
        self.assertTrue(attacked)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((relocated / "preferences.lock").exists())

    def test_project_save_rejects_invalid_inheritance_without_mutating_scope(self):
        for existing in (False, True):
            for document in (
                b"null",
                b'{"schema_version":1,"preferences":{"review_mode":"invalid"}}',
                b"\xff",
                b"x" * (preferences.MAX_BYTES + 1),
            ):
                with (
                    self.subTest(existing=existing, document=document[:80]),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory)
                    (root / ".agents").mkdir()
                    revision = "absent"
                    if existing:
                        revision = preferences.save(
                            root, {"language": "Japanese"}, "absent", "short-film"
                        )["revision"]
                    local = root / ".agents/local"
                    local.mkdir(exist_ok=True)
                    (local / "preferences.json").write_bytes(document)
                    before = self.snapshot(local)
                    directories = sorted(
                        str(path.relative_to(local))
                        for path in local.rglob("*")
                        if path.is_dir()
                    )
                    with self.assertRaises((ValueError, TypeError)):
                        preferences.save(
                            root, {"language": "French"}, revision, "short-film"
                        )
                    self.assertEqual(self.snapshot(local), before)
                    self.assertEqual(
                        sorted(
                            str(path.relative_to(local))
                            for path in local.rglob("*")
                            if path.is_dir()
                        ),
                        directories,
                    )

    def test_inheritance_is_validated_after_shared_writer_lock_acquisition(self):
        for existing in (False, True):
            with (
                self.subTest(existing=existing),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / ".agents").mkdir()
                preferences.save(root, {"language": "English"}, "absent")
                revision = "absent"
                if existing:
                    revision = preferences.save(
                        root, {"tone": "Quiet"}, "absent", "short-film"
                    )["revision"]
                local = root / ".agents/local"
                project = local / "projects/short-film/preferences.json"
                before = project.read_bytes() if existing else None
                ignore_before = (local / ".gitignore").read_bytes()
                open_file = os.open

                def corrupt_after_lock_open(
                    path, flags, mode=0o777, open_file=open_file, local=local, **kwargs
                ):
                    descriptor = open_file(path, flags, mode, **kwargs)
                    if Path(path).name == "preferences.lock":
                        (local / "preferences.json").write_bytes(b"null")
                    return descriptor

                with (
                    mock_patch.object(
                        preferences.os, "open", side_effect=corrupt_after_lock_open
                    ),
                    self.assertRaises((ValueError, TypeError)),
                ):
                    preferences.save(root, {"tone": "Bright"}, revision, "short-film")
                self.assertEqual(
                    project.read_bytes() if project.exists() else None, before
                )
                self.assertEqual((local / ".gitignore").read_bytes(), ignore_before)
                self.assertFalse((local / "preferences.lock").exists())
                if not existing:
                    self.assertFalse((local / "projects").exists())

    def test_save_result_is_locked_snapshot_not_unlocked_readback(self):
        first = self.save({"language": "English"})
        local = self.root / ".agents/local"
        unlink = os.unlink

        def change_workspace_after_unlock(path, **kwargs):
            result = unlink(path, **kwargs)
            if Path(path).name == "preferences.lock":
                (local / "preferences.json").write_text(
                    '{"schema_version":1,"preferences":{"language":"Japanese"}}'
                )
            return result

        with mock_patch.object(
            preferences.os, "unlink", side_effect=change_workspace_after_unlock
        ):
            result = preferences.save(
                self.root, {"tone": "Quiet"}, "absent", "short-film"
            )
        self.assertEqual(result["preferences"]["language"], "English")
        self.assertEqual(result["workspace_revision"], first["revision"])
        self.assertEqual(result["stored_preferences"], {"tone": "Quiet"})
        self.assertEqual(
            preferences.show(self.root, "short-film")["revision"], result["revision"]
        )

    def test_unsupported_descriptor_runtime_fails_before_any_mutation(self):
        with (
            mock_patch.object(preferences.os, "supports_dir_fd", set()),
            self.assertRaisesRegex(ValueError, "native|runtime|descriptor"),
        ):
            preferences.save(self.root, {"language": "English"}, "absent")
        self.assertFalse((self.root / ".agents/local").exists())

    def test_show_and_writes_fail_closed_for_missing_native_capabilities(self):
        for existing in (False, True):
            with (
                self.subTest(existing=existing),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / ".agents").mkdir()
                revision = "absent"
                if existing:
                    revision = preferences.save(
                        root, {"language": "English"}, "absent"
                    )["revision"]
                before = self.snapshot(root)
                directories = list(root.rglob("*"))
                for target, attribute, value in (
                    (preferences.os, "name", "nt"),
                    (preferences.os, "supports_dir_fd", set()),
                    (preferences.os, "supports_follow_symlinks", set()),
                    (preferences.os, "O_NOFOLLOW", 0),
                    (preferences.os, "O_DIRECTORY", 0),
                    (preferences.os, "O_NONBLOCK", 0),
                    (preferences, "REPLACE_API", lambda source, destination: None),
                ):
                    with (
                        self.subTest(attribute=attribute),
                        mock_patch.object(target, attribute, value),
                    ):
                        with self.assertRaisesRegex(ValueError, "native"):
                            preferences.show(root)
                        with self.assertRaisesRegex(ValueError, "native"):
                            preferences.save(root, {"tone": "Quiet"}, revision)
                        with self.assertRaisesRegex(ValueError, "native"):
                            preferences.atomic_write(
                                root, root / ".agents/local/.gitignore", b"*\n"
                            )
                self.assertEqual(self.snapshot(root), before)
                self.assertEqual(list(root.rglob("*")), directories)

    def test_show_rejects_parent_or_file_swap_at_read_open(self):
        for swap_parent in (False, True):
            with (
                self.subTest(swap_parent=swap_parent),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / ".agents").mkdir()
                preferences.save(root, {"language": "English"}, "absent")
                local = root / ".agents/local"
                outside = root / "outside"
                outside.mkdir()
                (outside / "preferences.json").write_text(
                    '{"schema_version":1,"preferences":{"language":"Japanese"}}'
                )
                before = self.snapshot(outside)
                open_file = os.open
                attacked = False

                def swap_before_read(
                    path,
                    flags,
                    mode=0o777,
                    root=root,
                    local=local,
                    outside=outside,
                    open_file=open_file,
                    swap_parent=swap_parent,
                    **kwargs,
                ):
                    nonlocal attacked
                    if Path(path).name == "preferences.json" and not attacked:
                        attacked = True
                        if swap_parent:
                            local.rename(root / "relocated")
                            local.symlink_to(outside, target_is_directory=True)
                        else:
                            (local / "preferences.json").unlink()
                            (local / "preferences.json").symlink_to(
                                outside / "preferences.json"
                            )
                    return open_file(path, flags, mode, **kwargs)

                with (
                    mock_patch.object(
                        preferences.os, "open", side_effect=swap_before_read
                    ),
                    self.assertRaises((ValueError, OSError)),
                ):
                    preferences.show(root)
                self.assertTrue(attacked)
                self.assertEqual(self.snapshot(outside), before)

    def test_project_directory_identity_swap_is_rejected_before_write(self):
        first = self.save({"language": "English"}, project="short-film")
        local = self.root / ".agents/local"
        project = local / "projects/short-film"
        relocated = self.root / "relocated"
        open_file = os.open
        attacked = False
        replacement = b'{"schema_version":1,"preferences":{"language":"Japanese"}}'

        def replace_directory_before_open(path, flags, mode=0o777, **kwargs):
            nonlocal attacked
            if Path(path).name == "short-film" and not attacked:
                attacked = True
                project.rename(relocated)
                project.mkdir()
                (project / "preferences.json").write_bytes(replacement)
            return open_file(path, flags, mode, **kwargs)

        with (
            mock_patch.object(
                preferences.os, "open", side_effect=replace_directory_before_open
            ),
            self.assertRaises(ValueError),
        ):
            preferences.save(
                self.root, {"tone": "Quiet"}, first["revision"], "short-film"
            )
        self.assertTrue(attacked)
        self.assertEqual((project / "preferences.json").read_bytes(), replacement)
        self.assertFalse((local / "preferences.lock").exists())

    def test_atomic_temp_creation_race_cleans_only_original_directory(self):
        local = self.root / ".agents/local"
        local.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        relocated = self.root / "relocated"
        open_file = os.open
        attacked = False

        def swap_before_temp_open(path, flags, mode=0o777, **kwargs):
            nonlocal attacked
            if Path(path).name.startswith(".preferences-") and not attacked:
                attacked = True
                local.rename(relocated)
                local.symlink_to(outside, target_is_directory=True)
            return open_file(path, flags, mode, **kwargs)

        with (
            mock_patch.object(
                preferences.os, "open", side_effect=swap_before_temp_open
            ),
            self.assertRaises((OSError, ValueError)),
        ):
            preferences.atomic_write(
                self.root, local / "preferences.json", b"private state"
            )
        self.assertTrue(attacked)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(list(relocated.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
