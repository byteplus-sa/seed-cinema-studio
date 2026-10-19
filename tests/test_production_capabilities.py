from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents/scripts"))

import production_post as post


class ProductionPostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.take = self.asset("scenes/scene-100/s100_sh010/take.mp4", b"take")
        self.edit_source = self.asset("studio/index.html", b"manual edit")
        self.editorial = {
            "schema_version": 1,
            "unit_id": "short",
            "cut_id": "main",
            "duration_s": 7200,
            "source_edit": self.edit_source,
            "entries": [{
                "id": "clip-010",
                "shot_id": "s100_sh010",
                "take": self.take,
                "source_in_s": 3,
                "source_out_s": 15,
                "source_duration_s": 20,
                "timeline_start_s": 7188,
            }],
        }

    def asset(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {"path": name, "sha256": hashlib.sha256(content).hexdigest()}

    def codes(self, findings):
        return {finding.code for finding in findings}

    def sound(self):
        edit = self.asset("editorial/short/main.json", json.dumps(self.editorial).encode())
        return {
            "schema_version": 1,
            "unit_id": "short",
            "cut_id": "main",
            "duration_s": 7200,
            "edit": edit,
            "cues": [{
                "id": "room-010",
                "kind": "ambience",
                "start_s": 0,
                "end_s": 7200,
                "intent": "Keep room tone continuous beneath the quiet held shot.",
                "gain_db": -6,
                "source": self.asset("sound/room.wav", b"room tone"),
            }],
            "listening": {"status": "unverified", "evidence": [], "note": "Not listened."},
        }

    def test_long_edit_validation_is_read_only_and_preserves_manual_studio(self):
        before = copy.deepcopy(self.editorial)
        self.assertEqual(post.validate_editorial(
            self.root, self.editorial, unit_id="short",
            selected_takes={"s100_sh010": self.take["path"]},
        ), [])
        self.assertEqual(self.editorial, before)
        self.assertEqual((self.root / "studio/index.html").read_bytes(), b"manual edit")
        self.assertFalse((self.root / "production.json").exists())

    def test_foreign_unit_or_unselected_take_fails(self):
        self.assertIn("scope", self.codes(post.validate_editorial(
            self.root, self.editorial, unit_id="ep002",
        )))
        self.assertIn("selection", self.codes(post.validate_editorial(
            self.root, self.editorial, selected_takes={},
        )))
        self.assertIn("selection", self.codes(post.validate_editorial(
            self.root, self.editorial,
            selected_takes={"s100_sh010": "different.mp4"},
        )))

    def test_changed_source_take_or_studio_edit_is_stale(self):
        for reference in (self.take, self.edit_source):
            with self.subTest(reference=reference):
                path = self.root / reference["path"]
                original = path.read_bytes()
                path.write_bytes(b"changed")
                self.assertIn("stale", self.codes(post.validate_editorial(self.root, self.editorial)))
                path.write_bytes(original)

    def test_trim_bounds_order_duplicates_and_overlap_fail(self):
        for field, value in (("source_in_s", 16), ("source_out_s", 21), ("timeline_start_s", 7199)):
            with self.subTest(field=field):
                document = copy.deepcopy(self.editorial)
                document["entries"][0][field] = value
                self.assertIn("range", self.codes(post.validate_editorial(self.root, document)))
        document = copy.deepcopy(self.editorial)
        document["entries"].append(copy.deepcopy(document["entries"][0]))
        self.assertIn("duplicate", self.codes(post.validate_editorial(self.root, document)))
        self.assertIn("overlap", self.codes(post.validate_editorial(self.root, document)))
        document["entries"][1]["id"] = "clip-020"
        document["entries"][1]["timeline_start_s"] = 1
        self.assertIn("order", self.codes(post.validate_editorial(self.root, document)))

    def test_unsafe_missing_and_symlink_paths_fail(self):
        outside = self.root.parent / f"{self.root.name}-outside"
        outside.write_bytes(b"take")
        self.addCleanup(outside.unlink)
        (self.root / "escape").symlink_to(outside)
        for name in ("../take.mp4", str(outside), "escape", "missing.mp4"):
            with self.subTest(name=name):
                document = copy.deepcopy(self.editorial)
                document["entries"][0]["take"]["path"] = name
                self.assertTrue(post.validate_editorial(self.root, document))

    def test_schema_rejects_empty_null_boolean_nonfinite_and_unknown_fields(self):
        documents = [None, {}, {"schema_version": 1}, []]
        for value in (True, float("nan"), float("inf"), -1, 0):
            document = copy.deepcopy(self.editorial)
            document["duration_s"] = value
            documents.append(document)
        document = copy.deepcopy(self.editorial)
        document["entries"] = []
        documents.append(document)
        document = copy.deepcopy(self.editorial)
        document["approved"] = True
        documents.append(document)
        for document in documents:
            with self.subTest(document=document):
                self.assertTrue(post.validate_editorial(self.root, document))

    def test_sound_cues_bind_edit_and_do_not_invent_listening(self):
        document = self.sound()
        before = copy.deepcopy(document)
        self.assertEqual(post.validate_sound(self.root, document, unit_id="short"), [])
        self.assertEqual(document, before)
        document["listening"]["status"] = "pass"
        self.assertIn("schema", self.codes(post.validate_sound(self.root, document)))
        document["listening"]["evidence"] = [self.asset("reviews/listening.md", b"Observed pass")]
        self.assertEqual(post.validate_sound(self.root, document), [])
        (self.root / "reviews/listening.md").write_bytes(b"changed")
        self.assertIn("stale", self.codes(post.validate_sound(self.root, document)))

    def test_sound_rejects_foreign_edit_timing_duplicate_cues_and_false_na(self):
        document = self.sound()
        document["unit_id"] = "ep002"
        self.assertIn("scope", self.codes(post.validate_sound(self.root, document)))
        document = self.sound()
        document["duration_s"] = 7201
        self.assertIn("duration", self.codes(post.validate_sound(self.root, document)))
        document = self.sound()
        document["cues"][0]["end_s"] = 7201
        self.assertIn("range", self.codes(post.validate_sound(self.root, document)))
        document = self.sound()
        document["cues"].append(copy.deepcopy(document["cues"][0]))
        self.assertIn("duplicate", self.codes(post.validate_sound(self.root, document)))
        document = self.sound()
        document["listening"]["status"] = "not_applicable"
        self.assertIn("evidence", self.codes(post.validate_sound(self.root, document)))

    def test_silent_cut_has_explicit_rationale_without_dialogue_gate(self):
        document = self.sound()
        document["cues"] = [{
            "id": "silence-010", "kind": "silence", "start_s": 0, "end_s": 7200,
            "intent": "Intentional silent cut.", "gain_db": 0,
        }]
        document["listening"] = {
            "status": "not_applicable", "evidence": [], "note": "No audio is intended.",
        }
        self.assertEqual(post.validate_sound(self.root, document), [])

    def test_read_only_cli_reports_findings_and_never_imports_edit(self):
        manifest = self.root / "edit.json"
        manifest.write_text(json.dumps(self.editorial))
        command = [
            sys.executable, str(ROOT / ".agents/scripts/production_post.py"),
            "editorial", str(self.root), "--record", "edit.json", "--unit", "short",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])
        manifest.write_text("{")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["valid"])
        self.assertEqual((self.root / "studio/index.html").read_bytes(), b"manual edit")


class CapabilitySkillTests(unittest.TestCase):
    def test_new_skills_have_valid_frontmatter_and_independent_leaves(self):
        from validate_workspace import validate_skill

        leaves = ("story-development", "series-continuity", "editorial-review", "sound-post", "subtitle-sidecars")
        for name in (*leaves, "production-localize"):
            with self.subTest(name=name):
                path = ROOT / ".agents/skills" / name / "SKILL.md"
                self.assertTrue(path.is_file(), name)
                metadata, findings = validate_skill(path)
                self.assertFalse(findings)
                self.assertEqual(metadata["name"], name)
                text = path.read_text()
                self.assertIn("orchestrator" if name == "production-localize" else "leaf", text)


if __name__ == "__main__":
    unittest.main()
