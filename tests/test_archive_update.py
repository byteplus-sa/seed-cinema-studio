import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/scripts/archive_update.py"
SPEC = importlib.util.spec_from_file_location("archive_update", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
updater = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = updater
SPEC.loader.exec_module(updater)
REPOSITORY = "byteplus-sa/seed-cinema-studio"
SOURCE = {"schema_version": 1, "repository": REPOSITORY, "ref": "main"}


class ArchiveUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.root = self.area / "workspace"
        self.root.mkdir()
        self.write(".agents/contracts/update-source.json", json.dumps(SOURCE))
        self.write(".gitignore", ".agents/local/\n")
        self.directory_patch = patch.object(
            updater,
            "external_directory",
            side_effect=lambda root, prefix="seed-update-stage-": Path(
                tempfile.mkdtemp(prefix=prefix, dir=self.area)
            ),
        )
        self.directory_patch.start()
        self.addCleanup(self.directory_patch.stop)

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def archive(self, entries, name="source.zip"):
        archive = self.area / name
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path, content in entries.items():
                if isinstance(content, tuple):
                    info = zipfile.ZipInfo("seed-cinema-studio-sha/" + path)
                    info.create_system = 3
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    bundle.writestr(info, content[0])
                else:
                    bundle.writestr("seed-cinema-studio-sha/" + path, content)
        return archive

    def preview(self, entries, revision="revision-1"):
        result = updater.preview(self.root, self.archive(entries), REPOSITORY, revision)
        self.addCleanup(updater.remove_staging, Path(result["plan"]).parent)
        return result

    def apply(self, preview, resolutions=None):
        try:
            result = updater.apply(
                Path(preview["plan"]), preview["plan_sha256"], True, resolutions or {}
            )
        except updater.UpdateError as error:
            if error.backup is not None:
                self.addCleanup(updater.remove_staging, error.backup)
            raise
        self.addCleanup(updater.remove_staging, Path(result["backup"]))
        return result

    def classes(self, preview):
        return {row["path"]: row["classification"] for row in preview["paths"]}

    def test_first_preview_is_read_only_and_different_existing_file_conflicts(self):
        self.write("README.md", "local")
        result = self.preview({"README.md": "upstream", "new.txt": "new"})
        self.assertEqual(self.classes(result)["README.md"], "conflict")
        self.assertEqual(self.classes(result)["new.txt"], "upstream-only")
        self.assertFalse((self.root / "new.txt").exists())
        self.assertFalse((self.root / ".agents/local/update-state.json").exists())
        self.assertFalse(Path(result["plan"]).is_relative_to(self.root))
        with self.assertRaises(updater.UpdateError):
            self.apply(result)
        self.assertEqual((self.root / "README.md").read_text(), "local")

    def test_first_apply_repeat_and_three_way_updates_preserve_local_changes(self):
        initial = self.preview({"a.txt": "base", "b.txt": "base", "c.txt": "base"})
        self.apply(initial)
        self.assertFalse((self.root / ".git").exists())
        repeat = self.preview({"a.txt": "base", "b.txt": "base", "c.txt": "base"})
        self.assertEqual(self.classes(repeat)["a.txt"], "unchanged")
        self.apply(repeat)
        self.write("b.txt", "local")
        self.write("c.txt", "local")
        update = self.preview(
            {"a.txt": "upstream", "b.txt": "base", "c.txt": "upstream"},
            "revision-2",
        )
        classes = self.classes(update)
        self.assertEqual(classes["a.txt"], "upstream-only")
        self.assertEqual(classes["b.txt"], "local-only")
        self.assertEqual(classes["c.txt"], "conflict")
        report = self.apply(update, {"c.txt": "local"})
        self.assertEqual((self.root / "a.txt").read_text(), "upstream")
        self.assertEqual((self.root / "b.txt").read_text(), "local")
        self.assertEqual((self.root / "c.txt").read_text(), "local")
        backup = Path(report["backup"])
        self.assertEqual((backup / "files/a.txt").read_text(), "base")
        self.assertEqual(
            json.loads((self.root / ".agents/local/update-state.json").read_text())[
                "revision"
            ],
            "revision-2",
        )
        repeated = self.preview(
            {"a.txt": "upstream", "b.txt": "base", "c.txt": "upstream"},
            "revision-2",
        )
        self.assertEqual(self.classes(repeated)["c.txt"], "local-only")

    def test_explicit_upstream_resolution_backs_up_local_file(self):
        self.write("README.md", "local")
        result = self.preview({"README.md": "upstream"})
        report = self.apply(result, {"README.md": "upstream"})
        backup = Path(report["backup"])
        self.assertEqual((backup / "files/README.md").read_text(), "local")
        self.assertEqual((self.root / "README.md").read_text(), "upstream")

    def test_removed_upstream_and_unknown_local_files_are_never_deleted(self):
        self.apply(self.preview({"old.txt": "old"}))
        self.write("unknown.txt", "mine")
        result = self.preview({"new.txt": "new"}, "revision-2")
        self.assertEqual(self.classes(result)["old.txt"], "upstream-removed-preserved")
        self.assertEqual(self.classes(result)["unknown.txt"], "local-only")
        self.apply(result)
        self.assertEqual((self.root / "old.txt").read_text(), "old")
        self.assertEqual((self.root / "unknown.txt").read_text(), "mine")

    def test_missing_previously_installed_file_is_a_local_change(self):
        self.apply(self.preview({"a.txt": "base"}))
        (self.root / "a.txt").unlink()
        unchanged = self.preview({"a.txt": "base"})
        self.assertEqual(self.classes(unchanged)["a.txt"], "local-only")
        self.apply(unchanged)
        self.assertFalse((self.root / "a.txt").exists())
        changed = self.preview({"a.txt": "new"}, "revision-2")
        self.assertEqual(self.classes(changed)["a.txt"], "conflict")

    def test_protected_paths_are_preserved_even_with_explicit_resolution(self):
        protected = [
            "projects/client/output.txt",
            "library/brands/brand.json",
            ".agents/local/preferences.json",
            ".agents/preferences.json",
            ".env",
            ".env.production",
            ".vscode/settings.json",
            ".claude/settings.json",
            ".claude/settings.local.json",
            ".idea/workspace.xml",
            ".mypy_cache/cache.json",
            "cache/inference.json",
            ".npm/cache/index",
            ".zed/settings.json",
            "custom.code-workspace",
            "__pycache__/cache.pyc",
            "node_modules/module/index.js",
            ".trae-html-share-packages/package.json",
            "docs/notes.md",
        ]
        for name in protected:
            self.write(name, "local")
        result = self.preview({name: "upstream" for name in protected})
        for name in protected:
            self.assertEqual(self.classes(result)[name], "protected")
        with self.assertRaises(updater.UpdateError):
            self.apply(result, {".env": "upstream"})
        self.apply(result)
        for name in protected:
            self.assertEqual((self.root / name).read_text(), "local")

    def test_workspace_staging_manifest_base_and_plan_changes_are_refused(self):
        for change in ("workspace", "stage", "source", "base", "plan"):
            with self.subTest(change=change):
                result = self.preview({"a.txt": "upstream"})
                plan = Path(result["plan"])
                body = json.loads(plan.read_text())
                if change == "workspace":
                    self.write("new-local.txt", "new")
                elif change == "stage":
                    (plan.parent / "files/a.txt").write_text("tampered")
                elif change == "source":
                    self.write(".agents/contracts/update-source.json", "{}")
                elif change == "base":
                    self.write(".agents/local/update-state.json", "{}")
                else:
                    body["revision"] = "tampered"
                    plan.write_text(json.dumps(body))
                with self.assertRaises(updater.UpdateError):
                    self.apply(result)
                self.assertFalse((self.root / "a.txt").exists())
                if change == "workspace":
                    (self.root / "new-local.txt").unlink()
                self.write(".agents/contracts/update-source.json", json.dumps(SOURCE))
                state = self.root / ".agents/local/update-state.json"
                if state.exists():
                    state.unlink()

    def test_confirmation_and_valid_file_level_resolutions_are_required(self):
        result = self.preview({"a.txt": "new"})
        with self.assertRaises(updater.UpdateError):
            updater.apply(Path(result["plan"]), result["plan_sha256"], False, {})
        for resolutions in (
            {"a.txt": "shell"},
            {"../escape": "local"},
            {"absent.txt": "upstream"},
        ):
            with self.assertRaises(updater.UpdateError):
                self.apply(result, resolutions)
        self.assertFalse((self.root / "a.txt").exists())

    def test_live_lock_refuses_another_apply(self):
        result = self.preview({"a.txt": "new"})
        self.write(".agents/local/update.lock", "another writer")
        with self.assertRaises(updater.UpdateError):
            self.apply(result)
        self.assertFalse((self.root / "a.txt").exists())
        self.assertEqual(
            (self.root / ".agents/local/update.lock").read_text(), "another writer"
        )

    def test_write_failure_rolls_back_files_and_state(self):
        self.write("a.txt", "old")
        result = self.preview({"a.txt": "new", "b.txt": "new"})
        original = updater.install_entry

        def fail_second(root, name, entry, contents):
            if name == "b.txt":
                raise OSError("synthetic write failure")
            return original(root, name, entry, contents)

        with (
            patch.object(updater, "install_entry", side_effect=fail_second),
            self.assertRaisesRegex(updater.UpdateError, "rolled back"),
        ):
            self.apply(result, {"a.txt": "upstream"})
        self.assertEqual((self.root / "a.txt").read_text(), "old")
        self.assertFalse((self.root / "b.txt").exists())
        self.assertFalse((self.root / ".agents/local/update-state.json").exists())
        self.assertFalse((self.root / ".agents/local/update.lock").exists())

    def test_rollback_failure_keeps_backup_and_lock_for_manual_recovery(self):
        self.write("a.txt", "old")
        result = self.preview({"a.txt": "new", "b.txt": "new"})
        original = updater.install_entry

        def fail_second(root, name, entry, contents):
            if name == "b.txt":
                raise OSError("write failed")
            return original(root, name, entry, contents)

        with (
            patch.object(updater, "install_entry", side_effect=fail_second),
            patch.object(updater, "restore_entry", side_effect=OSError("restore")),
            self.assertRaisesRegex(updater.UpdateError, "recovery required"),
        ):
            self.apply(result, {"a.txt": "upstream"})
        lock = json.loads((self.root / ".agents/local/update.lock").read_text())
        backup = Path(lock["backup"])
        self.assertEqual((backup / "files/a.txt").read_text(), "old")
        self.assertTrue((backup / "journal.json").is_file())

    def test_expected_text_and_unix_symlink_aliases_are_rebuilt(self):
        entries = {
            "AGENTS.md": "# Studio",
            ".agents/skills/example/SKILL.md": "# Example",
            "CLAUDE.md": "AGENTS.md",
            ".claude/skills/example": ("../../.agents/skills/example",),
        }
        self.apply(self.preview(entries))
        self.assertEqual(os.readlink(self.root / "CLAUDE.md"), "AGENTS.md")
        alias = self.root / ".claude/skills/example"
        self.assertEqual(os.readlink(alias), "../../.agents/skills/example")
        self.assertEqual((alias / "SKILL.md").read_text(), "# Example")

    def test_whole_claude_alias_and_same_text_first_zip_can_be_adopted(self):
        self.write("CLAUDE.md", "AGENTS.md")
        result = self.preview(
            {
                "AGENTS.md": "# Studio",
                "CLAUDE.md": "AGENTS.md",
                ".claude": ".agents",
                ".agents/scripts/tool.py": "pass",
            }
        )
        self.assertEqual(self.classes(result)["CLAUDE.md"], "alias-rebuild")
        self.apply(result)
        self.assertTrue((self.root / "CLAUDE.md").is_symlink())
        self.assertTrue((self.root / ".claude").is_symlink())

    def test_arbitrary_escaping_and_missing_target_aliases_are_rejected(self):
        for entries in (
            {"evil": ("../../escape",)},
            {"CLAUDE.md": ("../../escape",)},
            {"CLAUDE.md": "README.md", "README.md": "x"},
            {".claude": ".agents"},
            {
                ".claude": ".agents",
                ".claude/scripts/file": "bad",
                ".agents/scripts/file": "good",
            },
        ):
            with self.subTest(entries=entries), self.assertRaises(updater.UpdateError):
                self.preview(entries)

    def test_local_symlink_parent_and_directory_collision_block_updates(self):
        external = self.area / "external"
        external.mkdir()
        (self.root / "linked").symlink_to(external, target_is_directory=True)
        result = self.preview({"linked/file.txt": "x"})
        self.assertEqual(self.classes(result)["linked/file.txt"], "blocked")
        with self.assertRaises(updater.UpdateError):
            self.apply(result, {"linked/file.txt": "upstream"})
        self.assertFalse((external / "file.txt").exists())
        (self.root / "directory").mkdir()
        self.write("directory/local.txt", "mine")
        with self.assertRaises(updater.UpdateError):
            self.apply(self.preview({"directory": "new"}))
        self.assertEqual((self.root / "directory/local.txt").read_text(), "mine")

    def test_traversal_malformed_paths_case_collisions_and_file_parents_rejected(self):
        for entries in (
            {"../escape": "x"},
            {"/absolute": "x"},
            {"a\\b": "x"},
            {"a//b": "x"},
            {"./a": "x"},
            {"a/../b": "x"},
            {"C:/drive": "x"},
            {"a.": "x"},
            {"a ": "x"},
            {"nul.txt": "x"},
            {"a\nb": "x"},
            {"Readme": "x", "README": "y"},
            {"Dir/a": "x", "dir/b": "y"},
            {"parent": "x", "parent/child": "y"},
            {".git/config": "x"},
            {"a/" * updater.MAX_PATH_DEPTH + "file": "x"},
            {"a" * 256: "x"},
        ):
            with self.subTest(entries=entries), self.assertRaises(updater.UpdateError):
                self.preview(entries)

    def test_duplicate_empty_corrupt_encrypted_and_size_limited_archives_rejected(self):
        duplicate = self.area / "duplicate.zip"
        with zipfile.ZipFile(duplicate, "w") as bundle:
            bundle.writestr("root/a", "one")
            with self.assertWarns(UserWarning):
                bundle.writestr("root/a", "two")
        empty = self.archive({}, "empty.zip")
        corrupt = self.area / "corrupt.zip"
        corrupt.write_bytes(b"not zip")
        for archive in (duplicate, empty, corrupt):
            with self.assertRaises(updater.UpdateError):
                updater.preview(self.root, archive, REPOSITORY, "rev")
        with (
            patch.object(updater, "MAX_FILE_BYTES", 4),
            self.assertRaises(updater.UpdateError),
        ):
            self.preview({"large.txt": "12345"})
        with (
            patch.object(updater, "MAX_TOTAL_BYTES", 4),
            self.assertRaises(updater.UpdateError),
        ):
            self.preview({"one": "123", "two": "456"})
        with (
            patch.object(updater, "MAX_ENTRIES", 1),
            self.assertRaises(updater.UpdateError),
        ):
            self.preview({"one": "1", "two": "2"})
        with (
            patch.object(updater, "MAX_RATIO", 2),
            self.assertRaises(updater.UpdateError),
        ):
            self.preview({"bomb": "0" * 10000})

    def test_raw_nul_encrypted_and_special_file_entries_are_rejected(self):
        archive = self.archive({"aXb": "x"})
        archive.write_bytes(archive.read_bytes().replace(b"aXb", b"a\x00b"))
        with self.assertRaises(updater.UpdateError):
            updater.preview(self.root, archive, REPOSITORY, "rev")
        archive = self.archive({"secret": "x"})
        contents = bytearray(archive.read_bytes())
        central = contents.index(b"PK\x01\x02")
        contents[central + 8] |= 1
        archive.write_bytes(contents)
        with self.assertRaises(updater.UpdateError):
            updater.preview(self.root, archive, REPOSITORY, "rev")
        with zipfile.ZipFile(archive, "w") as bundle:
            info = zipfile.ZipInfo("device")
            info.external_attr = (stat.S_IFCHR | 0o644) << 16
            bundle.writestr(info, "x")
        with self.assertRaises(updater.UpdateError):
            updater.preview(self.root, archive, REPOSITORY, "rev")

    def test_workspace_case_collision_cannot_be_forced(self):
        self.write("Local/file.txt", "mine")
        result = self.preview({"local/new.txt": "new"})
        self.assertEqual(self.classes(result)["local/new.txt"], "blocked")
        with self.assertRaises(updater.UpdateError):
            self.apply(result, {"local/new.txt": "upstream"})
        self.assertFalse((self.root / "local/new.txt").exists())

    def test_changed_file_during_apply_rolls_back_without_losing_intervening_edit(self):
        self.write("a.txt", "old")
        self.write("untouched.txt", "old")
        result = self.preview({"a.txt": "new"})
        original = updater.install_entry

        def intervening_edit(root, name, entry, contents):
            original(root, name, entry, contents)
            if name == "a.txt":
                self.write("untouched.txt", "edited while applying")

        with (
            patch.object(updater, "install_entry", side_effect=intervening_edit),
            self.assertRaisesRegex(updater.UpdateError, "rolled back"),
        ):
            self.apply(result, {"a.txt": "upstream"})
        self.assertEqual((self.root / "a.txt").read_text(), "old")
        self.assertEqual(
            (self.root / "untouched.txt").read_text(), "edited while applying"
        )
        self.assertFalse((self.root / ".agents/local/update-state.json").exists())

    def test_failed_state_write_restores_previous_base_and_workspace(self):
        self.apply(self.preview({"a.txt": "base"}))
        before = (self.root / ".agents/local/update-state.json").read_bytes()
        result = self.preview({"a.txt": "new"}, "revision-2")
        original = updater.install_entry

        def failed_state(root, name, entry, contents):
            if name == updater.STATE_PATH:
                raise OSError("state failure")
            return original(root, name, entry, contents)

        with (
            patch.object(updater, "install_entry", side_effect=failed_state),
            self.assertRaisesRegex(updater.UpdateError, "rolled back"),
        ):
            self.apply(result)
        self.assertEqual((self.root / "a.txt").read_text(), "base")
        self.assertEqual(
            (self.root / ".agents/local/update-state.json").read_bytes(), before
        )

    def test_download_network_errors_and_cli_missing_input_do_not_change_workspace(
        self,
    ):
        before = updater.inventory(self.root)
        for error in (
            urllib.error.HTTPError("url", 401, "auth", {}, None),
            urllib.error.HTTPError("url", 429, "rate", {}, None),
            urllib.error.URLError("offline"),
        ):
            with (
                patch.object(updater, "open_url", side_effect=error),
                self.assertRaises(updater.UpdateError),
            ):
                updater.download_preview(self.root, "a" * 40)
        for arguments in (
            [
                "preview",
                "--workspace",
                str(self.root),
                "--zip",
                str(self.archive({"x": "x"})),
            ],
            ["apply", "--plan", "/absent/plan.json", "--plan-sha256", "a" * 64],
        ):
            failed = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), *arguments],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(failed.returncode, 2)
            self.assertEqual(json.loads(failed.stderr)["status"], "error")
        self.assertEqual(updater.inventory(self.root), before)

    def test_unsafe_urls_and_redirects_are_rejected_without_leaking_token(self):
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": "synthetic-secret"}),
            patch.object(updater.urllib.request, "build_opener") as opener,
        ):
            for url in (
                "http://codeload.github.com/path",
                "https://attacker.example/archive.zip",
                "https://api.github.com@attacker.example/path",
                "https://api.github.com/path?token=synthetic-secret",
            ):
                with self.assertRaises(updater.UpdateError) as caught:
                    updater.open_url(url)
                self.assertNotIn("synthetic-secret", str(caught.exception))
            opener.assert_not_called()
        with self.assertRaises(updater.UpdateError):
            updater.NoRedirect().redirect_request(
                None, None, 302, "", {}, "https://attacker.example"
            )

    def test_rehashed_plan_cannot_reclassify_protected_files(self):
        self.write(".env", "local")
        result = self.preview({".env": "upstream", "new.txt": "new"})
        plan = Path(result["plan"])
        body = json.loads(plan.read_text())
        for row in body["paths"]:
            if row["path"] == ".env":
                row["classification"] = "upstream-only"
        data = updater.encode_json(body)
        plan.write_bytes(data)
        with self.assertRaises(updater.UpdateError):
            updater.apply(plan, updater.digest(data), True, {})
        self.assertEqual((self.root / ".env").read_text(), "local")
        self.assertFalse((self.root / "new.txt").exists())

    def test_explicit_local_resolution_cannot_leave_new_alias_without_target(self):
        self.apply(self.preview({"AGENTS.md": "base"}))
        (self.root / "AGENTS.md").unlink()
        result = self.preview({"AGENTS.md": "new", "CLAUDE.md": "AGENTS.md"})
        with self.assertRaises(updater.UpdateError):
            self.apply(result, {"AGENTS.md": "local"})
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_local_zip_can_apply_to_workspace_without_agents_or_git(self):
        shutil_target = self.root / ".agents"
        (shutil_target / "contracts/update-source.json").unlink()
        (shutil_target / "contracts").rmdir()
        shutil_target.rmdir()
        result = self.preview({"new.txt": "new"})
        self.apply(result)
        self.assertEqual((self.root / "new.txt").read_text(), "new")
        self.assertTrue((self.root / ".agents/local/update-state.json").is_file())
        self.assertFalse((self.root / ".git").exists())

    def test_staging_or_plan_changes_during_apply_trigger_rollback(self):
        for change in ("stage", "plan"):
            with self.subTest(change=change):
                self.write("a.txt", "old")
                result = self.preview({"a.txt": "new"})
                plan = Path(result["plan"])
                original = updater.install_entry

                def tamper(
                    root,
                    name,
                    entry,
                    contents,
                    install=original,
                    plan_path=plan,
                    target_kind=change,
                ):
                    install(root, name, entry, contents)
                    if name == "a.txt":
                        target = (
                            plan_path
                            if target_kind == "plan"
                            else plan_path.parent / "files/a.txt"
                        )
                        target.write_text("changed")

                with (
                    patch.object(updater, "install_entry", side_effect=tamper),
                    self.assertRaisesRegex(updater.UpdateError, "rolled back"),
                ):
                    self.apply(result, {"a.txt": "upstream"})
                self.assertEqual((self.root / "a.txt").read_text(), "old")

    def test_parent_replaced_during_apply_retains_recovery_lock(self):
        self.write("folder/a.txt", "old")
        result = self.preview({"folder/a.txt": "new"})
        original = updater.install_entry
        external = self.area / "external"
        external.mkdir()

        def replace_parent(root, name, entry, contents):
            original(root, name, entry, contents)
            if name == "folder/a.txt":
                (root / "folder").rename(root / "saved-folder")
                (root / "folder").symlink_to(external, target_is_directory=True)

        with (
            patch.object(updater, "install_entry", side_effect=replace_parent),
            self.assertRaisesRegex(updater.UpdateError, "recovery required"),
        ):
            self.apply(result, {"folder/a.txt": "upstream"})
        self.assertTrue((self.root / ".agents/local/update.lock").is_file())
        self.assertEqual(list(external.iterdir()), [])

    def test_symlink_swap_at_replace_cannot_write_outside_workspace(self):
        self.write("folder/a.txt", "old")
        external = self.area / "external"
        external.mkdir()
        victim = external / "a.txt"
        victim.write_text("do not touch")
        original_replace = updater.os.replace

        def swap_parent(source, destination, **arguments):
            (self.root / "folder").rename(self.root / "saved-folder")
            (self.root / "folder").symlink_to(external, target_is_directory=True)
            (external / Path(source).name).write_text("attacker-controlled")
            return original_replace(source, destination, **arguments)

        payload = b"new"
        with patch.object(updater.os, "replace", side_effect=swap_parent):
            updater.install_entry(
                self.root,
                "folder/a.txt",
                {"kind": "file", "sha256": updater.digest(payload), "mode": 0o644},
                payload,
            )
        self.assertEqual(victim.read_text(), "do not touch")

    def test_rollback_directory_cleanup_cannot_follow_replaced_parent(self):
        result = self.preview({"folder/nested/a.txt": "new"})
        external = self.area / "external"
        external.mkdir()
        preserved = external / "nested"
        preserved.mkdir()
        original = updater.install_entry

        def replace_created_parent(root, name, entry, contents):
            original(root, name, entry, contents)
            if name == "folder/nested/a.txt":
                (root / "folder").rename(root / "saved-folder")
                (root / "folder").symlink_to(external, target_is_directory=True)

        with (
            patch.object(updater, "install_entry", side_effect=replace_created_parent),
            self.assertRaisesRegex(updater.UpdateError, "recovery required"),
        ):
            self.apply(result)
        self.assertTrue(preserved.is_dir())
        self.assertTrue((self.root / ".agents/local/update.lock").is_file())

    def test_fifo_manifest_and_zip_inputs_fail_without_blocking(self):
        def assert_rejected(arguments):
            with tempfile.TemporaryFile(mode="w+t") as errors:
                failed = subprocess.run(
                    [sys.executable, "-B", str(SCRIPT), *arguments],
                    stdout=subprocess.DEVNULL,
                    stderr=errors,
                    check=False,
                    timeout=10,
                )
                self.assertEqual(failed.returncode, 2)
                errors.seek(0)
                self.assertIn("Not a regular file", json.load(errors)["error"])

        source = self.root / updater.SOURCE_PATH
        source.unlink()
        os.mkfifo(source)
        assert_rejected(["discover", "--workspace", str(self.root)])
        source.unlink()
        source.write_text(json.dumps(SOURCE))
        archive = self.area / "source-fifo.zip"
        os.mkfifo(archive)
        assert_rejected(
            [
                "preview",
                "--workspace",
                str(self.root),
                "--zip",
                str(archive),
                "--source",
                REPOSITORY,
                "--revision",
                "rev",
            ]
        )

    def test_source_and_state_schemas_reject_untrusted_or_malformed_data(self):
        malformed = [
            "null",
            "[]",
            "{}",
            "{",
            json.dumps({**SOURCE, "schema_version": True}),
            json.dumps({**SOURCE, "repository": "other/repo"}),
            json.dumps({**SOURCE, "ref": "../main"}),
            '{"schema_version":1,"repository":"other/repo",'
            '"repository":"' + REPOSITORY + '","ref":"main"}',
        ]
        for contents in malformed:
            with self.subTest(contents=contents):
                self.write(".agents/contracts/update-source.json", contents)
                with self.assertRaises(updater.UpdateError):
                    updater.read_source(self.root)
        self.write(".agents/contracts/update-source.json", json.dumps(SOURCE))
        for contents in ("{}", "[]", '{"schema_version":1,"hashes":{"../x":"bad"}}'):
            self.write(".agents/local/update-state.json", contents)
            with self.assertRaises(updater.UpdateError):
                self.preview({"file": "x"})

    def test_local_zip_needs_user_source_revision_and_checks_embedded_identity(self):
        archive = self.archive({"file": "x"})
        for source, revision in (("", "rev"), (REPOSITORY, ""), ("other/repo", "rev")):
            with self.assertRaises(updater.UpdateError):
                updater.preview(self.root, archive, source, revision)
        with self.assertRaises(updater.UpdateError):
            self.preview(
                {
                    ".agents/contracts/update-source.json": json.dumps(
                        {**SOURCE, "repository": "other/repo"}
                    )
                }
            )
        (self.root / ".agents/contracts/update-source.json").unlink()
        self.apply(self.preview({"file": "x"}))

    def test_discovery_uses_pinned_sha_without_downloading(self):
        response = io.BytesIO(json.dumps({"sha": "a" * 40}).encode())
        with patch.object(updater, "open_url", return_value=response) as request:
            result = updater.discover(self.root)
        self.assertEqual(result["revision"], "a" * 40)
        self.assertEqual(
            result["url"],
            "https://codeload.github.com/" + REPOSITORY + "/zip/" + "a" * 40,
        )
        self.assertEqual(request.call_count, 1)
        self.assertIn("/commits/main", request.call_args.args[0])

    def test_http_auth_rate_network_invalid_json_and_revision_failures_are_safe(self):
        errors = [
            urllib.error.HTTPError("url", 401, "auth", {}, None),
            urllib.error.HTTPError("url", 403, "forbidden", {}, None),
            urllib.error.HTTPError("url", 429, "rate", {}, None),
            urllib.error.HTTPError("url", 404, "missing", {}, None),
            urllib.error.URLError("network"),
            TimeoutError("timeout"),
        ]
        for error in errors:
            with self.subTest(error=error):
                with (
                    patch.object(updater, "open_url", side_effect=error),
                    self.assertRaises(updater.UpdateError) as caught,
                ):
                    updater.discover(self.root)
                self.assertNotIn("secret", str(caught.exception))
        for contents in (b"invalid", b"[]", b'{"sha":"main"}'):
            with (
                patch.object(updater, "open_url", return_value=io.BytesIO(contents)),
                self.assertRaises(updater.UpdateError),
            ):
                updater.discover(self.root)

    def test_download_is_codeload_only_bounded_and_does_not_execute_code(self):
        archive = self.archive({"code.py": "raise RuntimeError('never execute')"})
        with patch.object(
            updater, "open_url", return_value=io.BytesIO(archive.read_bytes())
        ):
            result = updater.download_preview(self.root, "a" * 40)
        self.addCleanup(updater.remove_staging, Path(result["plan"]).parent)
        self.assertFalse((self.root / "code.py").exists())
        with self.assertRaises(updater.UpdateError):
            updater.download_preview(self.root, "main")
        with (
            patch.object(updater, "MAX_ZIP_BYTES", 4),
            patch.object(updater, "open_url", return_value=io.BytesIO(b"12345")),
            self.assertRaises(updater.UpdateError),
        ):
            updater.download_preview(self.root, "a" * 40)

    def test_cli_local_preview_apply_smoke_runs_without_git_or_uv(self):
        archive = self.archive({"hello.txt": "world"})
        environment = {**os.environ, "PATH": ""}
        command = [
            sys.executable,
            "-B",
            str(SCRIPT),
            "preview",
            "--workspace",
            str(self.root),
            "--zip",
            str(archive),
            "--source",
            REPOSITORY,
            "--revision",
            "user-revision",
        ]
        preview = subprocess.run(
            command, capture_output=True, text=True, env=environment, check=True
        )
        result = json.loads(preview.stdout)
        self.addCleanup(updater.remove_staging, Path(result["plan"]).parent)
        apply = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "apply",
                "--plan",
                result["plan"],
                "--plan-sha256",
                result["plan_sha256"],
                "--confirm",
            ],
            capture_output=True,
            text=True,
            env=environment,
            check=True,
        )
        report = json.loads(apply.stdout)
        self.addCleanup(updater.remove_staging, Path(report["backup"]))
        self.assertEqual(report["status"], "applied")
        self.assertEqual((self.root / "hello.txt").read_text(), "world")
        self.assertFalse((self.root / ".git").exists())


if __name__ == "__main__":
    unittest.main()
