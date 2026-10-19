from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents/scripts"))

import production_post as post


class LocalizationPreservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.master = self.asset("master.mp4", b"source-master")
        self.script = self.asset("script.md", b"locked source words")
        self.output = self.asset("master.es.srt", b"subtitles")
        self.document = {
            "schema_version": 1, "unit_id": "short", "target_language": "es",
            "route": "subtitles", "source_master": self.master,
            "source_inputs": [self.script], "outputs": [self.output],
            "lip_sync": {"verdict": "not_applicable", "evidence": []},
            "cultural_review": {
                "status": "unverified", "evidence": [], "note": "Native review unavailable.",
            },
        }

    def asset(self, path, content):
        (self.root / path).write_bytes(content)
        return {"path": path, "sha256": hashlib.sha256(content).hexdigest()}

    def codes(self):
        return {item.code for item in post.validate_localization(self.root, self.document)}

    def test_source_master_and_script_preserved_without_claiming_cultural_approval(self):
        before = copy.deepcopy(self.document)
        self.assertEqual(post.validate_localization(self.root, self.document, unit_id="short"), [])
        self.assertEqual(self.document, before)
        self.assertEqual((self.root / "master.mp4").read_bytes(), b"source-master")
        self.assertEqual((self.root / "script.md").read_bytes(), b"locked source words")
        (self.root / "script.md").write_bytes(b"rewritten")
        self.assertIn("stale", self.codes())

    def test_changed_source_master_fails_even_when_outputs_exist(self):
        (self.root / "master.mp4").write_bytes(b"replacement")
        self.assertIn("stale", self.codes())

    def test_alias_check_failure_cannot_report_preservation_valid(self):
        with patch("pathlib.Path.samefile", side_effect=OSError("File disappeared")):
            self.assertIn("path", self.codes())

    def test_output_cannot_alias_source_by_path_symlink_or_hardlink(self):
        for kind in ("path", "symlink", "hardlink"):
            with self.subTest(kind=kind):
                alias = self.root / f"{kind}.mp4"
                if kind == "symlink":
                    alias.symlink_to(self.root / "master.mp4")
                elif kind == "hardlink":
                    os.link(self.root / "master.mp4", alias)
                self.document["outputs"] = [{
                    "path": "master.mp4" if kind == "path" else alias.name,
                    "sha256": self.master["sha256"],
                }]
                self.assertIn("preservation", self.codes())

    def test_revoice_never_claims_native_lipsync_and_regenerate_needs_evidence(self):
        self.document["route"] = "revoice"
        self.document["outputs"] = [self.asset("localized.mp4", b"new audio")]
        self.document["lip_sync"]["verdict"] = "native"
        self.assertIn("lip_sync", self.codes())
        self.document["lip_sync"]["verdict"] = "approximate"
        self.assertIn("evidence", self.codes())
        self.document["lip_sync"]["evidence"] = [self.asset("revoice-playback.md", b"Playback notes")]
        self.assertEqual(self.codes(), set())
        self.document["route"] = "regenerate"
        self.document["lip_sync"]["evidence"] = []
        self.document["lip_sync"]["verdict"] = "unverified"
        self.assertEqual(self.codes(), set())
        self.document["lip_sync"]["verdict"] = "native"
        self.assertIn("evidence", self.codes())
        self.document["lip_sync"]["evidence"] = [self.asset("playback.md", b"Actual playback notes")]
        self.assertEqual(self.codes(), set())

    def test_approximate_lipsync_cli_requires_current_evidence(self):
        self.document["route"] = "revoice"
        self.document["lip_sync"]["verdict"] = "approximate"
        record = self.root / "localization.json"
        command = [
            sys.executable, str(ROOT / ".agents/scripts/production_post.py"),
            "localization", str(self.root), "--record", record.name,
        ]
        for state in ("missing", "current", "stale"):
            with self.subTest(state=state):
                if state == "current":
                    self.document["lip_sync"]["evidence"] = [
                        self.asset("playback.md", b"Observed approximate lip sync"),
                    ]
                elif state == "stale":
                    (self.root / "playback.md").write_bytes(b"Changed evidence")
                record.write_text(json.dumps(self.document))
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0 if state == "current" else 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)["valid"], state == "current")

    def test_foreign_unit_invalid_language_and_invented_approval_fail(self):
        self.assertTrue(post.validate_localization(self.root, self.document, unit_id="ep002"))
        self.document["target_language"] = "../es"
        self.assertIn("schema", self.codes())
        self.document["target_language"] = "es"
        self.document["cultural_review"]["status"] = "pass"
        self.assertIn("schema", self.codes())


class GenericSubtitleCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = []
        for unit, offset in (("ep001", 0), ("ep002", 7200)):
            path = self.root / f"{unit}.json"
            path.write_text(json.dumps({
                "schema_version": 1, "offset_s": offset,
                "lines": [{
                    "id": f"{unit}-line-010", "speaker": "Speaker",
                    "start_s": 1, "end_s": 5,
                    "text": {"en": "A quiet moment before we leave this room."},
                }],
            }))
            self.inputs.append(path)

    def run_cli(self, skill, output, *extra):
        command = [
            sys.executable, str(ROOT / f".agents/skills/{skill}/scripts/make_subtitles.py"),
            "--master-stem", "feature_v01", "--language", "en", "--format", "both",
            "--out-dir", str(output), "--master-duration-s", "10800",
        ]
        for path in self.inputs:
            command.extend(["--input", str(path)])
        return subprocess.run([*command, *extra], capture_output=True, text=True, check=False)

    def test_new_and_old_cli_outputs_are_byte_identical_on_long_unit_offsets(self):
        source_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in self.inputs]
        old = self.root / "old"
        new = self.root / "new"
        for skill, output in (("microdrama-subtitles", old), ("subtitle-sidecars", new)):
            result = self.run_cli(skill, output, "--offset-s", "3")
            self.assertEqual(result.returncode, 0, result.stderr)
        for extension in ("srt", "vtt"):
            name = f"feature_v01.en.{extension}"
            self.assertEqual((old / name).read_bytes(), (new / name).read_bytes())
        self.assertIn("02:00:04,000", (new / "feature_v01.en.srt").read_text())
        self.assertEqual(source_hashes, [hashlib.sha256(path.read_bytes()).hexdigest() for path in self.inputs])

    def test_horizontal_settings_are_explicit_not_inferred_from_format(self):
        result = self.run_cli(
            "subtitle-sidecars", self.root / "wide",
            "--max-chars", "42", "--max-cps", "20", "--max-lines", "2",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("A quiet moment before we leave this room.", (self.root / "wide/feature_v01.en.srt").read_text())

    def test_unit_overlap_fails_without_mutating_inputs(self):
        document = json.loads(self.inputs[1].read_text())
        document["offset_s"] = 0
        self.inputs[1].write_text(json.dumps(document))
        before = [path.read_bytes() for path in self.inputs]
        result = self.run_cli("subtitle-sidecars", self.root / "out", "--overlap", "error")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("overlap", result.stderr)
        self.assertEqual(before, [path.read_bytes() for path in self.inputs])
        self.assertFalse(list((self.root / "out").glob("*.srt")))

    def test_overwrite_refuses_source_master_symlink(self):
        output = self.root / "out"
        output.mkdir()
        master = self.root / "source.mp4"
        master.write_bytes(b"preserved-master")
        (output / "feature_v01.en.srt").symlink_to(master)
        result = self.run_cli("microdrama-subtitles", output, "--overwrite")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(master.read_bytes(), b"preserved-master")

    def test_invalid_second_language_does_not_write_partial_delivery(self):
        output = self.root / "out"
        result = self.run_cli("microdrama-subtitles", output, "--language", "en", "fr")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(list(output.glob("*")))

    def test_overwrite_refuses_source_hardlink_and_direct_input_alias(self):
        output = self.root / "out"
        output.mkdir()
        target = output / "feature_v01.en.srt"
        os.link(self.inputs[0], target)
        before = self.inputs[0].read_bytes()
        result = self.run_cli("subtitle-sidecars", output, "--overwrite")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.inputs[0].read_bytes(), before)
        target.unlink()
        target.write_bytes(before)
        self.inputs = [target]
        result = self.run_cli("subtitle-sidecars", output, "--overwrite")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(target.read_bytes(), before)

    def test_case_only_output_name_preserves_dialogue_input(self):
        output = self.root / "out"
        output.mkdir()
        source = output / "FEATURE_V01.EN.SRT"
        source.write_bytes(self.inputs[0].read_bytes())
        before = source.read_bytes()
        self.inputs = [source]
        target = output / "feature_v01.en.srt"
        aliases_source = target.exists() and target.samefile(source)
        result = self.run_cli("subtitle-sidecars", output, "--overwrite")
        self.assertEqual(result.returncode, 2 if aliases_source else 0, result.stderr)
        self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
