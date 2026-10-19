from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import studio_project as studio


class CinemaStudioGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name).resolve()
        (self.project / "project.md").write_text(
            "---\napproval_mode: approve_for_me\n---\n# Test\n"
        )

    def snapshot(self):
        return {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file() and not path.is_symlink()
        }

    def test_candidate_manifest_does_not_change_legacy_studio_location(self):
        (self.project / "production.plan.json").write_text("{}")
        self.assertEqual(studio.init_studio(self.project), self.project / "studio")

    def test_invalid_active_manifest_blocks_initialization_before_writes(self):
        (self.project / "production.json").write_text("{}")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            studio.init_studio(self.project)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.project / "studio").exists())

    def test_valid_active_manifest_initializes_its_single_unit(self):
        scene = self.project / "scenes/scene-001"
        scene.mkdir(parents=True)
        (scene / "scene.md").write_text("# Scene\n")
        unit = self.project / "units/ep001"
        unit.mkdir(parents=True)
        (unit / "unit.md").write_text("# Episode one\n")
        (self.project / "production.json").write_text(json.dumps({
            "schema_version": 1, "format": "episodic-show", "units": [{
                "id": "ep001", "kind": "episode", "brief": "units/ep001/unit.md",
                "scene_ids": ["scene-001"],
            }],
        }))
        self.assertEqual(studio.init_studio(self.project), unit / "studio")
        studio.start_stage(self.project, "brief-development")
        studio.complete_stage(self.project, "brief-development")
        self.assertEqual(studio.read_stages(self.project)["schema_version"], 2)
        self.assertFalse((self.project / "studio").exists())

    def test_dangling_active_manifest_is_not_treated_as_legacy(self):
        (self.project / "production.json").symlink_to("missing.json")
        with self.assertRaises(ValueError):
            studio.init_studio(self.project)
        self.assertFalse((self.project / "studio").exists())

    def test_malformed_active_manifest_blocks_every_command_before_dispatch(self):
        (self.project / "production.json").write_text("malformed")
        commands = [
            ["init"], ["sync"], ["status"], ["check"], ["render"],
            ["candidates", "s01_sh010"], ["place", "s01_sh010", "take.mp4"],
            ["stage", "start", "brief-development"], ["stage", "show"],
            ["record-selection", "s01_sh010", "--decision", "missing.json"],
            ["record-lock", "--decision", "missing.json"],
            ["lock-element", "character", "--decision", "missing.json"],
            ["sync-elements"], ["record-render", "missing.mp4"],
            ["hf", "preview", "--no-open"],
        ]
        before = self.snapshot()
        with (
            patch.object(studio, "run_hyperframes") as runner,
            patch.object(studio, "hf_command") as hf_runner,
        ):
            for command in commands:
                with self.subTest(command=command):
                    output = io.StringIO()
                    with contextlib.redirect_stdout(output):
                        code = studio.main([command[0], str(self.project), *command[1:]])
                    self.assertEqual(code, 1)
                    self.assertTrue(json.loads(output.getvalue())["error"])
                    self.assertEqual(self.snapshot(), before)
            runner.assert_not_called()
            hf_runner.assert_not_called()

    def test_legacy_stage_progress_remains_available(self):
        studio.init_studio(self.project)
        studio.start_stage(self.project, "brief-development")
        self.assertEqual(studio.read_stages(self.project)["current_stage"], "brief-development")


if __name__ == "__main__":
    unittest.main()
