from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_scene_board import MODULE, SCRIPT, write_png


class SceneIdTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="scene-id-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def scene(self, digits: str, *, shot: str = "010", beats: int = 0) -> str:
        scene = f"scene-{digits}"
        directory = self.root / "scenes" / scene
        directory.mkdir(parents=True, exist_ok=True)
        plan = {
            "scene": scene,
            "shots": [{
                "id": f"s{digits}_sh{shot}",
                "duration_s": 12,
                "move": "static hold",
                "turn": bool(beats),
                "sub_beats": [f"beat-{number}" for number in range(beats)],
            }],
        }
        (directory / "scene.md").write_text(
            "## Shot plan\n\n```yaml\n"
            + MODULE.dump_yaml({"shot_plan": plan}) + "```\n",
            encoding="utf-8",
        )
        return scene

    def init(self, scene: str, level: str = "L1") -> dict:
        return MODULE.init_board(
            self.root, scene, level, "ID regression", [], "pencil", "16:9", False,
        )

    def cli(self, command: str, scene: str, *options: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, str(self.root), scene, *options],
            capture_output=True, text=True, check=False, timeout=30,
        )

    def snapshot(self) -> dict[str, bytes | None]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes() if path.is_file() else None
            for path in self.root.rglob("*") if not path.is_symlink()
        }

    def test_scene_100_and_larger_build_register_and_check(self) -> None:
        for digits in ("01", "001", "100", "1234"):
            with self.subTest(scene=digits):
                scene = self.scene(digits)
                self.init(scene)
                board, _ = MODULE.read_board(self.root, scene)
                panel = board["panels"][0]
                self.assertEqual(panel["id"], f"s{digits}_sh010_p010")
                path = self.root / f"scenes/{scene}/{panel['clip']}/{panel['id']}_t01_v01.png"
                write_png(path, 80)
                MODULE.register_panel(
                    self.root, scene, panel["id"], path.relative_to(self.root).as_posix(),
                    None, None, None, None, None,
                )
                self.assertEqual(MODULE.check_board(self.root, scene), [])
                result = MODULE.build_sheet(self.root, scene, None)
                self.assertEqual(
                    Path(result["pages"][0]["html"]).name, f"s{digits}_sheet_pg01_v01.html",
                )
                self.assertEqual(
                    MODULE.build_review_page(self.root, scene)["page"],
                    f"review/{scene}-board.html",
                )

    def test_cli_scene_100_init_check_and_status(self) -> None:
        self.scene("100")
        for command, identifier in (("init", "100"), ("check", "scene-100"), ("status", "100")):
            with self.subTest(command=command):
                result = self.cli(command, identifier)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsInstance(json.loads(result.stdout), dict)

    def test_explicit_scene_spelling_and_legacy_shortcuts_survive(self) -> None:
        for value, expected in (
            ("scene-01", "scene-01"), ("s01", "scene-01"),
            ("scene-001", "scene-001"), ("s001", "scene-001"),
            ("1", "scene-01"), ("01", "scene-01"), ("scene-1", "scene-01"),
            ("scene-100", "scene-100"), ("100", "scene-100"),
        ):
            with self.subTest(value=value):
                self.assertEqual(MODULE.normalize_scene(value), expected)

    def test_numeric_shortcut_selects_only_matching_directory(self) -> None:
        self.scene("001")
        self.assertEqual(MODULE.normalize_scene("1", self.root), "scene-001")
        result = self.cli("init", "01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "scenes/scene-001/board.md").is_file())

    def test_ambiguous_numeric_shortcut_rejects_without_writes(self) -> None:
        self.scene("01")
        self.scene("001")
        before = self.snapshot()
        for value in ("1", "01", "001"):
            with self.subTest(value=value):
                result = self.cli("init", value)
                self.assertEqual(result.returncode, 2)
                self.assertIn("ambiguous", result.stderr.lower())
                self.assertEqual(self.snapshot(), before)
        for value in ("scene-01", "scene-001", "s01", "s001"):
            self.assertEqual(MODULE.normalize_scene(value, self.root), value.replace("s0", "scene-0"))
        for value in ("scene-01", "scene-001"):
            result = self.cli("init", value)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["board"], f"scenes/{value}/board.md")

    def test_invalid_scene_identifiers_reject(self) -> None:
        for value in ("", "../scene-01", "scene-01/x", "-1", "scene-1.0", "scene-\uff11\uff12", "\u0661\u0660\u0660"):
            with self.subTest(value=value), self.assertRaises(MODULE.BoardError):
                MODULE.normalize_scene(value)

    def test_explicit_scene_does_not_fall_back_to_another_padding(self) -> None:
        self.scene("001")
        result = self.cli("init", "scene-01")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Missing scenes/scene-01/scene.md", result.stderr)
        self.assertFalse((self.root / "scenes/scene-001/board.md").exists())

    def test_numeric_shortcut_rejects_escaped_scene_symlink(self) -> None:
        outside = tempfile.TemporaryDirectory(prefix="scene-id-outside-")
        self.addCleanup(outside.cleanup)
        (self.root / "scenes").mkdir()
        (self.root / "scenes/scene-100").symlink_to(outside.name)
        with self.assertRaisesRegex(MODULE.BoardError, "escapes"):
            MODULE.normalize_scene("100", self.root)
        result = self.cli("init", "scene-100")
        self.assertEqual(result.returncode, 2)
        self.assertIn("escapes", result.stderr)
        self.assertEqual(list(Path(outside.name).iterdir()), [])

    def test_shot_numbers_stay_three_digits_and_scene_prefix_is_exact(self) -> None:
        for digits, shot in (("100", "1000"), ("100", "10"), ("100", "\uff11\uff12\uff13")):
            with self.subTest(shot=shot):
                scene = self.scene(digits, shot=shot)
                with self.assertRaises(MODULE.BoardError):
                    self.init(scene)
                self.assertFalse((self.root / f"scenes/{scene}/board.md").exists())
        scene = self.scene("001")
        path = self.root / f"scenes/{scene}/scene.md"
        path.write_text(path.read_text().replace("s001_sh", "s01_sh"))
        with self.assertRaises(MODULE.BoardError):
            self.init(scene)

    def test_99_panels_fit_but_100_panels_reject_before_write(self) -> None:
        scene = self.scene("100", beats=99)
        self.init(scene, "L3")
        board, _ = MODULE.read_board(self.root, scene)
        self.assertEqual(len(board["panels"]), 99)
        self.assertEqual(board["panels"][-1]["id"], "s100_sh010_p990")
        scene = self.scene("101", beats=100)
        with self.assertRaisesRegex(MODULE.BoardError, "more than 99 panels"):
            self.init(scene, "L3")
        self.assertFalse((self.root / f"scenes/{scene}/board.md").exists())

    def test_schema_does_not_expand_shot_panel_take_or_version_width(self) -> None:
        scene = self.scene("100")
        self.init(scene)
        board, _ = MODULE.read_board(self.root, scene)
        for field, value in (
            ("id", "s100_sh010_p1000"), ("clip", "s100_sh1000"),
            ("shot", "s100_sh1000_a"),
        ):
            invalid = copy.deepcopy(board)
            invalid["panels"][0][field] = value
            with self.subTest(field=field):
                self.assertTrue(MODULE.schema_findings(invalid))
        for filename in (
            "s100_sh010_p1000_t01_v01.png", "s100_sh1000_p010_t01_v01.png",
            "s100_sh010_p010_t100_v01.png", "s100_sh010_p010_t01_v100.png",
        ):
            with self.subTest(filename=filename):
                self.assertIsNone(MODULE.PANEL_FILE.fullmatch(filename))

    def test_scene_100_board_reference_and_history_are_preserved(self) -> None:
        scene = self.scene("100")
        self.init(scene)
        registry = self.root / "task_ids.json"
        for status, severity in (("prepared", "error"), ("terminal", "warning")):
            registry.write_text(json.dumps({"tasks": [{
                "submission_status": status,
                "model": "dreamina-seedance-2-5-260628",
                "references": [{"path": "scenes/scene-100/board/animatic/custom.mp4"}],
            }]}))
            before = registry.read_bytes()
            findings = MODULE.check_board(self.root, scene)
            self.assertEqual([(item.rule_id, item.severity) for item in findings],
                             [("board.animatic_review_only", severity)])
            self.assertEqual(registry.read_bytes(), before)

    def test_invalid_active_manifest_rejects_all_mutation_entrypoints_before_writes(self) -> None:
        scene = self.scene("01")
        self.init(scene)
        panel = "s01_sh010_p010"
        calls = (
            lambda: self.init(scene),
            lambda: MODULE.rebase_plan(self.root, scene),
            lambda: MODULE.register_panel(self.root, scene, panel, "absent.png", None, None, None, None, None),
            lambda: MODULE.mark_panel(self.root, scene, panel, "review", None),
            lambda: MODULE.edit_source(self.root, scene, panel, "absent.json", "test", None),
            lambda: MODULE.plan_repair(self.root, scene, [panel], "local", "hand", "fix", ["fixed"], None),
            lambda: MODULE.build_sheet(self.root, scene, None),
            lambda: MODULE.render_sheet(self.root, scene, str(SCRIPT), None),
            lambda: MODULE.build_overview(self.root, scene),
            lambda: MODULE.build_animatic(self.root, scene, None, None),
            lambda: MODULE.build_review_page(self.root, scene),
            lambda: MODULE.is_studio_project(self.root),
        )
        for manifest_kind in ("json-object", "invalid", "directory", "dangling-symlink"):
            manifest = self.root / "production.json"
            if manifest_kind == "directory":
                manifest.mkdir()
            elif manifest_kind == "dangling-symlink":
                manifest.symlink_to(self.root / "absent.json")
            else:
                manifest.write_text("{}" if manifest_kind == "json-object" else "{broken")
            before = self.snapshot()
            with patch.object(MODULE.subprocess, "run") as subprocess_run:
                for index, call in enumerate(calls):
                    with self.subTest(manifest=manifest_kind, entrypoint=index):
                        with self.assertRaises(MODULE.BoardError):
                            call()
                        self.assertEqual(self.snapshot(), before)
                subprocess_run.assert_not_called()
            if manifest_kind == "directory":
                manifest.rmdir()
            else:
                manifest.unlink()

    def test_low_level_writers_recheck_manifest_before_creating_files(self) -> None:
        scene = self.scene("01")
        self.init(scene)
        board, body = MODULE.read_board(self.root, scene)
        (self.root / "production.json").write_text("{}")
        before = self.snapshot()
        for call in (
            lambda: MODULE.write_board(self.root, scene, board, body),
            lambda: MODULE.safe_directory(self.root, "review"),
            lambda: MODULE.write_json(self.root, self.root / "new.json", {}),
        ):
            with self.assertRaises(MODULE.BoardError):
                call()
            self.assertEqual(self.snapshot(), before)

    def test_cli_invalid_manifest_rejects_cleanly_and_candidate_does_not_activate(self) -> None:
        self.scene("100")
        (self.root / "production.plan.json").write_text("{}")
        result = self.cli("init", "100")
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.root / "production.json").write_text("{}")
        before = self.snapshot()
        for command in ("init", "sheet", "status", "check"):
            result = self.cli(command, "100")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("Invalid production manifest", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
