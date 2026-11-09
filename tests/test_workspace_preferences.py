import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents/scripts/workspace_preferences.py"


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


if __name__ == "__main__":
    unittest.main()
