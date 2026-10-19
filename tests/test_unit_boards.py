from __future__ import annotations

import copy
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_scene_board import MODULE, RENDERER, ROOT, SCRIPT, write_png

sys.path.insert(0, str(ROOT / ".agents/scripts"))
CONTEXT = importlib.import_module("production_context")
VALIDATOR = importlib.import_module("validate_request")


class UnitBoardTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="unit-board-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.set_mode("approve_for_me")
        self.manifest = {"schema_version": 1, "format": "episodic-show", "units": []}
        for unit, digits in (("ep001", "001"), ("ep002", "100")):
            brief = f"units/{unit}/unit.md"
            (self.root / brief).parent.mkdir(parents=True)
            (self.root / brief).write_text(f"# {unit}\n")
            studio = self.root / f"units/{unit}/studio"
            studio.mkdir()
            (studio / "index.html").write_text("<html></html>")
            (studio / "hyperframes.json").write_text("{}")
            scene = f"scene-{digits}"
            directory = self.root / f"scenes/{scene}"
            directory.mkdir(parents=True)
            plan = {"scene": scene, "shots": [{
                "id": f"s{digits}_sh010", "duration_s": 1,
                "move": "static hold", "static_reason": "quiet observation",
            }]}
            (directory / "scene.md").write_text(
                "## Shot plan\n\n```yaml\n"
                + MODULE.dump_yaml({"shot_plan": plan}) + "```\n",
            )
            self.manifest["units"].append(
                {"id": unit, "kind": "episode", "brief": brief, "scene_ids": [scene]},
            )
        self.save_manifest()

    def set_mode(self, mode: str) -> None:
        (self.root / "project.md").write_text(f"---\napproval_mode: {mode}\n---\n")

    def save_manifest(self, name: str = "production.json") -> None:
        (self.root / name).write_text(json.dumps(self.manifest))

    def snapshot(self) -> dict[str, bytes | None]:
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes() if path.is_file() else None
            for path in self.root.rglob("*") if not path.is_symlink()
        }

    def init(self, scene: str = "scene-001", **kwargs: object) -> dict:
        return MODULE.init_board(
            self.root, scene, "L1", "unit scope test", [], "pencil", "16:9", False,
            **kwargs,
        )

    def register(self, scene: str = "scene-001") -> dict:
        self.init(scene)
        panel = MODULE.read_board(self.root, scene)[0]["panels"][0]
        path = f"scenes/{scene}/{panel['clip']}/{panel['id']}_t01_v01.png"
        write_png(self.root / path, 80)
        MODULE.register_panel(
            self.root, scene, panel["id"], path, None, None, None, None, None,
        )
        return MODULE.read_board(self.root, scene)[0]["panels"][0]

    def review(self, panel: dict) -> str:
        path = f"review_{panel['id']}.json"
        (self.root / path).write_text(json.dumps({
            "schema_version": 1, "artifact_path": panel["file"],
            "artifact_sha256": panel["sha256"], "status": "pass",
            "inspection_method": "full image inspection", "coverage": "whole panel",
            "checks": [{"criterion": "staging", "status": "pass", "evidence": "matches"}],
            "observations": ["Staging matches"], "limitations": [],
            "recommendation": "Approve",
        }))
        return path

    def decision(self, panel: dict, **changes: object) -> str:
        context = CONTEXT.resolve_context(self.root, "ep001")
        review = self.review(panel)
        brief = "units/ep001/unit.md"
        record = {
            "schema_version": 2, "context": context.identity(),
            "decision_id": "select_panel", "decision_type": "variant_selection",
            "asset_id": panel["id"], "subject_path": panel["file"],
            "selected_variant": Path(panel["file"]).name,
            "selected_sha256": panel["sha256"], "actor": "agent",
            "approval_mode": "approve_for_me",
            "project_sha256": CONTEXT.context_project_sha256(self.root),
            "result": "approved", "review_path": review,
            "review_sha256": MODULE.sha256_file(self.root / review),
            "upstream_sha256": {brief: MODULE.sha256_file(self.root / brief)},
            "reason": "Matches the shot plan", "decided_at": "2026-10-19T00:00:00+00:00",
        }
        record.update(changes)
        if record["schema_version"] == 1:
            record.pop("context", None)
        (self.root / "decision.json").write_text(json.dumps(record))
        return "decision.json"

    def cli(self, command: str, scene: str = "scene-001", *options: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, str(self.root), scene, *options],
            capture_output=True, text=True, timeout=30, check=False,
        )

    def test_cli_selected_unit_builds_and_checks_without_root_studio(self) -> None:
        for command in ("init", "check", "status", "sheet", "review-page"):
            result = self.cli(command, "001", "--unit", "ep001")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsInstance(json.loads(result.stdout), dict)
        self.assertFalse((self.root / "studio").exists())
        self.assertFalse((self.root / "scenes/scene-100/board.md").exists())
        self.assertTrue((self.root / "review/scene-001-board.html").is_file())

    def test_multi_unit_cli_requires_explicit_selection_without_writes(self) -> None:
        before = self.snapshot()
        result = self.cli("init")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unit", result.stderr.lower())
        self.assertEqual(self.snapshot(), before)

    def test_foreign_unknown_and_traversing_cli_units_do_not_write(self) -> None:
        before = self.snapshot()
        for unit in ("ep002", "missing", "../ep001"):
            with self.subTest(unit=unit):
                result = self.cli("init", "scene-001", "--unit", unit)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_single_unit_cli_can_omit_unit(self) -> None:
        self.manifest["units"][0]["scene_ids"].append("scene-100")
        self.manifest["units"].pop()
        self.save_manifest()
        result = self.cli("init")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scene_apis_infer_owner_and_keep_production_relative_artifacts(self) -> None:
        panel = self.register("scene-100")
        self.assertEqual(MODULE.check_board(self.root, "scene-100"), [])
        result = MODULE.build_sheet(self.root, "scene-100", None)
        self.assertTrue(result["pages"][0]["html"].startswith("scenes/scene-100/board/"))
        result = MODULE.build_review_page(self.root, "scene-100")
        self.assertEqual(result["page"], "review/scene-100-board.html")
        result = MODULE.plan_repair(
            self.root, "scene-100", [panel["id"]], "local", "hand",
            "repair hand", ["hand is correct"], None,
        )
        self.assertTrue(result["actions"][0]["contract"].startswith("scenes/scene-100/"))
        self.assertFalse((self.root / "scenes/scene-001/board.md").exists())

    def test_explicit_foreign_unit_rejects_every_scene_entrypoint_without_writes(self) -> None:
        panel = self.register()
        board, body = MODULE.read_board(self.root, "scene-001")
        calls = (
            lambda: self.init(unit_id="ep002"),
            lambda: MODULE.read_board(self.root, "scene-001", unit_id="ep002"),
            lambda: MODULE.write_board(self.root, "scene-001", board, body, unit_id="ep002"),
            lambda: MODULE.rebase_plan(self.root, "scene-001", unit_id="ep002"),
            lambda: MODULE.check_board(self.root, "scene-001", unit_id="ep002"),
            lambda: MODULE.status_report(self.root, "scene-001", unit_id="ep002"),
            lambda: MODULE.register_panel(
                self.root, "scene-001", panel["id"], panel["file"],
                None, None, None, None, None, unit_id="ep002",
            ),
            lambda: MODULE.mark_panel(
                self.root, "scene-001", panel["id"], "review", None, unit_id="ep002",
            ),
            lambda: MODULE.edit_source(
                self.root, "scene-001", panel["id"], "absent.json", "repair", None,
                unit_id="ep002",
            ),
            lambda: MODULE.plan_repair(
                self.root, "scene-001", [panel["id"]], "local", "hand", "fix",
                ["fixed"], None, unit_id="ep002",
            ),
            lambda: MODULE.build_sheet(self.root, "scene-001", None, unit_id="ep002"),
            lambda: MODULE.render_sheet(self.root, "scene-001", str(SCRIPT), None, unit_id="ep002"),
            lambda: MODULE.build_overview(self.root, "scene-001", unit_id="ep002"),
            lambda: MODULE.build_animatic(self.root, "scene-001", None, None, unit_id="ep002"),
            lambda: MODULE.build_review_page(self.root, "scene-001", unit_id="ep002"),
        )
        before = self.snapshot()
        with patch.object(MODULE.subprocess, "run") as runner:
            for index, call in enumerate(calls):
                with self.subTest(entrypoint=index), self.assertRaises(MODULE.BoardError):
                    call()
                self.assertEqual(self.snapshot(), before)
            runner.assert_not_called()

    def test_v2_final_decision_and_revalidation_use_owning_unit(self) -> None:
        panel = self.register()
        decision = self.decision(panel)
        MODULE.check_final_decision(self.root, panel, self.root / decision)
        MODULE.mark_panel(self.root, "scene-001", panel["id"], "approved", decision)
        self.assertEqual(MODULE.check_board(self.root, "scene-001"), [])
        (self.root / "units/ep002/unit.md").write_text("# unrelated revision\n")
        self.assertEqual(MODULE.check_board(self.root, "scene-001"), [])
        (self.root / "units/ep001/unit.md").write_text("# changed unit\n")
        self.assertIn("board.decision_stale", [
            finding.rule_id for finding in MODULE.check_board(self.root, "scene-001")
        ])

    def test_unscoped_foreign_malformed_and_missing_upstream_decisions_never_approve(self) -> None:
        panel = self.register()
        foreign = CONTEXT.resolve_context(self.root, "ep002").identity()
        for changes in (
            {"schema_version": 1},
            {"context": foreign},
            {"context": CONTEXT.resolve_production_context(self.root).identity()},
            {"context": {"kind": "unit"}},
            {"upstream_sha256": {}},
        ):
            with self.subTest(changes=changes):
                decision = self.decision(panel, **changes)
                before = self.snapshot()
                with self.assertRaises(MODULE.BoardError):
                    MODULE.mark_panel(self.root, "scene-001", panel["id"], "approved", decision)
                self.assertEqual(self.snapshot(), before)

    def test_user_final_approval_works_in_both_modes_and_agent_cannot_use_ask_mode(self) -> None:
        panel = self.register()
        for mode in ("approve_for_me", "ask_for_approval"):
            self.set_mode(mode)
            decision = self.decision(
                panel, actor="user", approval_mode=mode,
                authorization={"source": "chat", "evidence": "Approve this panel"},
            )
            MODULE.mark_panel(self.root, "scene-001", panel["id"], "approved", decision)
            self.assertEqual(MODULE.check_board(self.root, "scene-001"), [])
            MODULE.mark_panel(self.root, "scene-001", panel["id"], "review", None)
        decision = self.decision(panel, approval_mode="ask_for_approval")
        before = self.snapshot()
        with self.assertRaises(MODULE.BoardError):
            MODULE.mark_panel(self.root, "scene-001", panel["id"], "approved", decision)
        self.assertEqual(self.snapshot(), before)

    def test_edit_source_v2_evidence_for_agent_and_chat_in_both_modes(self) -> None:
        panel = self.register()
        review = self.review(panel)
        for mode, words, actor in (
            ("approve_for_me", None, "agent"),
            ("approve_for_me", "Use this panel for the repair", "user"),
            ("ask_for_approval", "Use this panel for the repair", "user"),
        ):
            with self.subTest(mode=mode, actor=actor):
                self.set_mode(mode)
                result = MODULE.edit_source(
                    self.root, "scene-001", panel["id"], review, "repair input only", words,
                )
                decision = json.loads((self.root / result["decision"]).read_text())
                context = CONTEXT.resolve_context(self.root, "ep001")
                self.assertEqual(decision["schema_version"], 2)
                self.assertEqual(decision["context"], context.identity())
                self.assertEqual(decision["actor"], actor)
                self.assertEqual(
                    VALIDATOR.decision_findings(
                        self.root, decision, context=context, require_current_project=True,
                    ), [],
                )
                self.assertTrue(result["ref"].startswith("scenes/scene-001/"))
                self.assertFalse((self.root / "studio").exists())
                self.assertEqual(MODULE.read_board(self.root, "scene-001")[0]["panels"][0]["status"], "review")
                before = (self.root / result["decision"]).read_bytes()
                MODULE.edit_source(self.root, "scene-001", panel["id"], review, "repair input only", words)
                self.assertEqual((self.root / result["decision"]).read_bytes(), before)
                (self.root / result["decision"]).unlink()

    def test_edit_source_missing_studio_or_authorization_does_not_write(self) -> None:
        panel = self.register()
        review = self.review(panel)
        studio = self.root / "units/ep001/studio"
        (studio / "index.html").unlink()
        before = self.snapshot()
        with self.assertRaises(MODULE.BoardError):
            MODULE.edit_source(self.root, "scene-001", panel["id"], review, "repair", None)
        self.assertEqual(self.snapshot(), before)
        (studio / "index.html").write_text("<html></html>")
        self.set_mode("ask_for_approval")
        before = self.snapshot()
        with self.assertRaises(MODULE.BoardError):
            MODULE.edit_source(self.root, "scene-001", panel["id"], review, "repair", None)
        self.assertEqual(self.snapshot(), before)

    def test_candidate_does_not_authorize_unit_mutation(self) -> None:
        (self.root / "production.json").unlink()
        self.save_manifest("production.plan.json")
        before = self.snapshot()
        with self.assertRaises(MODULE.BoardError):
            self.init(unit_id="ep001")
        result = self.cli("init", "scene-001", "--unit", "ep001")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.snapshot(), before)
        self.init()
        self.assertFalse((self.root / "studio").exists())

    def test_candidate_context_cannot_authorize_lower_level_operations(self) -> None:
        (self.root / "production.json").unlink()
        self.save_manifest("production.plan.json")
        candidate = CONTEXT.resolve_candidate_context(self.root, "production.plan.json", "ep001")
        before = self.snapshot()
        with (
            patch.object(CONTEXT, "resolve_context", return_value=candidate),
            self.assertRaisesRegex(MODULE.BoardError, "Candidate"),
        ):
            self.init()
        self.assertEqual(self.snapshot(), before)

    def test_malformed_edit_manifest_does_not_leave_a_decision(self) -> None:
        panel = self.register()
        review = self.review(panel)
        path = self.root / f"scenes/scene-001/{panel['clip']}/panel_{panel['id']}.md"
        path.write_text("---\ninvalid: [\n---\n")
        before = self.snapshot()
        with self.assertRaises(MODULE.BoardError):
            MODULE.edit_source(self.root, "scene-001", panel["id"], review, "repair", None)
        self.assertEqual(self.snapshot(), before)

    def test_membership_change_invalidates_previous_panel_approval(self) -> None:
        panel = self.register()
        decision = self.decision(panel)
        MODULE.mark_panel(self.root, "scene-001", panel["id"], "approved", decision)
        self.manifest["units"][0]["scene_ids"], self.manifest["units"][1]["scene_ids"] = (
            self.manifest["units"][1]["scene_ids"], self.manifest["units"][0]["scene_ids"],
        )
        self.save_manifest()
        findings = MODULE.check_board(self.root, "scene-001")
        self.assertIn("board.decision_stale", [item.rule_id for item in findings])

    def test_renderer_cannot_write_a_foreign_units_output(self) -> None:
        self.init()
        result = MODULE.build_sheet(self.root, "scene-001", None)
        path = self.root / result["pages"][0]["sidecar"]
        record = json.loads(path.read_text())
        foreign = "scenes/scene-100/foreign.png"
        record["png"] = foreign
        record["render_arguments"][1] = str(self.root / foreign)
        path.write_text(json.dumps(record))
        before = self.snapshot()
        with patch.object(MODULE.subprocess, "run") as runner:
            with self.assertRaises(MODULE.BoardError):
                MODULE.render_sheet(self.root, "scene-001", str(SCRIPT), None)
            runner.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_renderer_rejects_overridden_record_path_before_launch(self) -> None:
        self.init()
        result = MODULE.build_sheet(self.root, "scene-001", None)
        path = self.root / result["pages"][0]["sidecar"]
        record = json.loads(path.read_text())
        record["render_arguments"].extend(["--record", str(self.root / "scenes/scene-100/foreign.json")])
        path.write_text(json.dumps(record))
        before = self.snapshot()
        with patch.object(MODULE.subprocess, "run") as runner:
            with self.assertRaises(MODULE.BoardError):
                MODULE.render_sheet(self.root, "scene-001", str(SCRIPT), None)
            runner.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_scoped_sheet_renderer_accepts_generated_arguments(self) -> None:
        self.register()
        MODULE.build_sheet(self.root, "scene-001", None)
        result = MODULE.render_sheet(self.root, "scene-001", str(RENDERER), None)
        self.assertTrue((self.root / result["rendered"][0]["png"]).is_file())
        self.assertEqual(MODULE.status_report(self.root, "scene-001")["stale_sheet_pages"], [])
        self.assertFalse((self.root / "scenes/scene-100/board").exists())

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg unavailable")
    def test_scoped_animatic_smoke_and_rebase_preserve_panel_history(self) -> None:
        panel = self.register()
        MODULE.rebase_plan(self.root, "scene-001")
        board = MODULE.read_board(self.root, "scene-001")[0]
        self.assertEqual(board["panels"][0]["versions"], panel["versions"])
        before = self.snapshot()
        with self.assertRaisesRegex(MODULE.BoardError, "registered panels"):
            MODULE.init_board(
                self.root, "scene-001", "L1", "keep history", [], "pencil", "16:9", True,
            )
        self.assertEqual(self.snapshot(), before)
        result = self.cli("animatic", "scene-001", "--unit", "ep001", "--size", "320x180")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["file"].startswith("scenes/scene-001/board/animatic/"))
        self.assertTrue((self.root / output["file"]).is_file())
        self.assertEqual(MODULE.status_report(self.root, "scene-001")["animatic"]["state"], "current")

    def test_writers_reject_in_production_symlink_to_foreign_scene(self) -> None:
        (self.root / "scenes/scene-001/board").symlink_to(self.root / "scenes/scene-100")
        before = self.snapshot()
        with self.assertRaises(MODULE.BoardError):
            MODULE.write_json(self.root, self.root / "scenes/scene-001/board/foreign.json", {})
        self.assertEqual(self.snapshot(), before)

    def test_writers_reject_foreign_board_identity(self) -> None:
        self.init()
        board, body = MODULE.read_board(self.root, "scene-001")
        board["scene"] = "scene-100"
        before = self.snapshot()
        with self.assertRaises(MODULE.BoardError):
            MODULE.write_board(self.root, "scene-001", board, body)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_or_duplicate_membership_blocks_all_writes(self) -> None:
        for kind in ("malformed", "duplicate", "missing"):
            manifest = copy.deepcopy(self.manifest)
            if kind == "duplicate":
                manifest["units"][1]["scene_ids"] = ["scene-001"]
            elif kind == "missing":
                manifest["units"][0]["scene_ids"] = ["scene-404"]
            (self.root / "production.json").write_text(
                "{broken" if kind == "malformed" else json.dumps(manifest),
            )
            before = self.snapshot()
            with self.subTest(kind=kind), self.assertRaises(MODULE.BoardError):
                self.init()
            self.assertEqual(self.snapshot(), before)

    def test_low_level_writes_require_resolved_membership(self) -> None:
        before = self.snapshot()
        for call in (
            lambda: MODULE.safe_directory(self.root, "review"),
            lambda: MODULE.write_json(self.root, self.root / "new.json", {}),
            lambda: MODULE.safe_directory(self.root, "scenes/scene-404/board"),
            lambda: MODULE.safe_directory(self.root, "scenes/scene-100/board", unit_id="ep001"),
        ):
            with self.assertRaises(MODULE.BoardError):
                call()
            self.assertEqual(self.snapshot(), before)
        MODULE.safe_directory(self.root, "scenes/scene-001/board")
        MODULE.write_json(self.root, self.root / "scenes/scene-001/board/test.json", {})

    def test_scoped_checks_preserve_historical_board_reference_warning(self) -> None:
        self.init("scene-100")
        registry = self.root / "task_ids.json"
        for status, severity in (("prepared", "error"), ("terminal", "warning")):
            registry.write_text(json.dumps({"tasks": [{
                "submission_status": status, "model": "dreamina-seedance-2-5-260628",
                "references": [{"path": "scenes/scene-100/board/animatic/custom.mp4"}],
            }]}))
            before = self.snapshot()
            findings = MODULE.check_board(self.root, "scene-100")
            self.assertEqual([(item.rule_id, item.severity) for item in findings],
                             [("board.animatic_review_only", severity)])
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
