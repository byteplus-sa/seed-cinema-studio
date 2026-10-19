from __future__ import annotations

import copy
import hashlib
import importlib
import json
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import test_production_context as context_fixtures
import test_request_validation as request_fixtures
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import draft_ledger
import operation_store
import prepare_request
import validate_request as validation
from production_context import resolve_candidate_context


class ScopedIntegrityTests(unittest.TestCase):
    def setUp(self):
        fixture = request_fixtures.RequestValidationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root, self.request, self.caps = fixture.root, fixture.request, fixture.caps
        self.context = {
            "context_version": 1,
            "kind": "unit",
            "unit_id": "ep001",
            "effective_sha256": "c" * 64,
        }

    def scoped_request(self):
        self.fixture.prepare_v2()
        self.request["schema_version"] = 3
        self.request["context"] = copy.deepcopy(self.context)
        self.request["request_sha256"] = validation.compute_request_hash(
            (self.root / "prompt.md").read_bytes(), self.request["references"],
            self.request["model"], self.request["operation"], self.request["params"],
            approval_mode=self.request["approval_mode"],
            project_sha256=self.request["project_sha256"],
            schema_version=3, context=self.context,
        )
        return self.request

    def snapshot(self):
        return {
            path.relative_to(self.root).as_posix(): (
                str(path.readlink()) if path.is_symlink()
                else path.read_bytes() if path.is_file() else None
            )
            for path in self.root.rglob("*")
        }

    def test_legacy_hash_vectors_are_unchanged(self):
        arguments = (
            b"Cafe\xc3\xa9 @Image 1.\n",
            [{"sha256": "a" * 64, "role": "reference_image", "binding": "@Image 1",
              "approval_evidence": {"manifest": "x.md", "field": "selected_variant"}}],
            "model", "generate", {"seed": 0, "ratio": "16:9"},
        )
        self.assertEqual(validation.compute_request_hash(*arguments),
                         "151e4a79e4292e45f55c7d99ddc09a44529a84e07d66dbd5db220dde25758a6a")
        self.assertEqual(validation.compute_request_hash(
            *arguments, approval_mode="approve_for_me", project_sha256="b" * 64),
            "8e9e518a0d6a5ffcfb887e1d9a42624c6a1b01473f5d4c813dba7a6bec3817ac")

    def test_v3_schema_and_registry_accept_typed_context_only(self):
        request = self.scoped_request()
        self.assertEqual(validation.schema_findings(request, "generation-request.schema.json"), [])
        self.assertEqual(validation.schema_findings(
            {"schema_version": 1, "tasks": [request]}, "task-registry.schema.json"), [])
        for context in (None, {}, {**self.context, "unit_id": "../ep001"},
                        {**self.context, "extra": True},
                        {**self.context, "effective_sha256": "c" * 64 + "\n"}):
            with self.subTest(context=context):
                request["context"] = context
                self.assertTrue(validation.schema_findings(request, "generation-request.schema.json"))
        request.pop("context")
        self.assertTrue(validation.schema_findings(request, "generation-request.schema.json"))

    def test_schema_definitions_stay_self_contained_and_in_sync(self):
        generation = json.loads((validation.SCHEMA_ROOT / "generation-request.schema.json").read_text())
        registry = json.loads((validation.SCHEMA_ROOT / "task-registry.schema.json").read_text())
        decision = json.loads((validation.SCHEMA_ROOT / "production-decision.schema.json").read_text())
        context = json.loads((validation.SCHEMA_ROOT / "production-context.schema.json").read_text())
        for version in (1, 2, 3):
            self.assertEqual(generation["$defs"][f"requestV{version}"],
                             registry["$defs"][f"requestV{version}"])
        for schema in (generation, registry, decision):
            Draft202012Validator.check_schema(schema)
            for key in ("type", "required", "properties", "additionalProperties", "allOf"):
                self.assertEqual(schema["$defs"]["productionContext"][key], context[key])

    def test_legacy_requests_detect_prompt_and_parameter_tampering(self):
        for version in (1, 2):
            if version == 2:
                self.fixture.prepare_v2()
            self.assertEqual(validation.request_hash_findings(self.root, self.request), [])
            request = copy.deepcopy(self.request)
            request["params"]["duration"] = 6
            self.assertIn("request.current_hash", {
                item.rule_id for item in validation.request_hash_findings(self.root, request)})
            request["prompt_sha256"] = "f" * 64
            self.assertIn("prompt.current_hash", {
                item.rule_id for item in validation.request_hash_findings(self.root, request)})

    def test_prompt_disappearing_between_hash_and_reference_checks_fails_closed(self):
        with patch.object(validation, "contained_path",
                          side_effect=[self.root / "prompt.md", ValueError("Prompt disappeared")]):
            findings = validation.prepared_evidence_findings(self.root, self.request)
        self.assertIn("path.containment", {item.rule_id for item in findings})

    def test_v3_hash_binds_every_context_field_and_rejects_downgrade(self):
        request = self.scoped_request()
        for key, value in (("unit_id", "ep002"), ("effective_sha256", "d" * 64)):
            changed = copy.deepcopy(request)
            changed["context"][key] = value
            rules = {finding.rule_id for finding in validation.prepared_evidence_findings(
                self.root, changed)}
            self.assertIn("request.current_hash", rules)
            self.assertIn("production.context_hash", rules)
        for version in (1, 2):
            with self.assertRaisesRegex(ValueError, "context"):
                validation.compute_request_hash(
                    b"prompt", [], "model", "generate", {},
                    schema_version=version, context=self.context)
        with self.assertRaisesRegex(ValueError, "context"):
            validation.compute_request_hash(b"prompt", [], "model", "generate", {},
                                            schema_version=3)

    def test_v3_without_active_manifest_cannot_enter_preflight_or_registration(self):
        request = self.scoped_request()
        before = self.snapshot()
        findings = validation.validate_request(self.root, request, self.caps)
        self.assertIn("production.context_hash", {item.rule_id for item in findings})
        for action in (
            lambda: operation_store.prepare_operation(self.root, request, self.caps, {}, []),
            lambda: operation_store.adopt_submitted_operation(
                self.root, request, self.caps, {}, [], "known-task", "succeeded", True),
            lambda: operation_store.require_current_approval_contract(self.root, request),
        ):
            with self.assertRaisesRegex(ValueError, "[Ss]coped"):
                action()
            self.assertEqual(before, self.snapshot())

    def test_v3_registry_without_active_manifest_cannot_transition_or_record_draft(self):
        request = self.scoped_request()
        request["params"] = {"draft": True, "resolution": "480p"}
        for status, next_status in (("prepared", "submitting"),
                                    ("acknowledged", "terminal"),
                                    ("submission_unknown", "acknowledged")):
            request["submission_status"] = status
            request["provider_task_id"] = "known-task"
            (self.root / "task_ids.json").write_text(json.dumps(
                {"schema_version": 1, "tasks": [request]}))
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "[Ss]coped"):
                operation_store.transition_operation(
                    self.root, request["operation_id"], status, next_status)
            with self.assertRaisesRegex(ValueError, "[Ss]coped"):
                draft_ledger.record_draft(
                    self.root, "fixture", request["operation_id"], "known-task", date(2026, 10, 19))
            self.assertEqual(before, self.snapshot())

    def test_scoped_decision_schema_does_not_authorize_without_active_manifest(self):
        self.fixture.prepare_v2()
        decision = json.loads((self.root / "decisions/choice-1.json").read_text())
        decision.update(schema_version=2, context=self.context)
        self.assertEqual(validation.schema_findings(
            decision, "production-decision.schema.json", candidate=True), [])
        self.assertIn("production.context_hash", {
            finding.rule_id for finding in validation.decision_findings(self.root, decision)})
        schema = json.loads((validation.SCHEMA_ROOT / "production-decision.schema.json").read_text())
        self.assertTrue(Draft202012Validator(schema).is_valid(decision))
        service_path = validation.SCHEMA_ROOT.parents[1] / "skills/showcase-html/scripts"
        sys.path.insert(0, str(service_path))
        self.addCleanup(sys.path.remove, str(service_path))
        service = importlib.import_module("selection_service")
        with self.assertRaises(service.SelectionError):
            service.validated_decision(
                self.root, decision, decision["subject_path"], decision["selected_sha256"],
                "approve_for_me", allow_chat=True)
        for context in (None, {}, {**self.context, "kind": "production"}):
            malformed = {**decision, "context": context}
            self.assertTrue(validation.schema_findings(
                malformed, "production-decision.schema.json", candidate=True))
        decision["schema_version"] = 1
        self.assertTrue(validation.schema_findings(decision, "production-decision.schema.json"))

    def test_production_context_requires_an_active_manifest(self):
        request = self.scoped_request()
        request["context"] = {
            "context_version": 1, "kind": "production", "effective_sha256": "d" * 64,
        }
        self.assertEqual(validation.schema_findings(request, "generation-request.schema.json"), [])
        with self.assertRaisesRegex(ValueError, "[Ss]coped"):
            operation_store.require_current_approval_contract(self.root, request)

    def test_v3_preparation_without_active_manifest_is_rejected_through_direct_api(self):
        arguments = prepare_request.parser().parse_args([
            "--project", str(self.root), "--asset", "fixture", "--prompt", "prompt.md",
            "--model", "fixture-model", "--operation", "generate",
            "--expected-output", "out.mp4",
        ])
        arguments.schema_version = 3
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "[Ss]coped"):
            prepare_request.build_request(self.root, arguments)
        self.assertEqual(before, self.snapshot())

    def test_legacy_promotion_cannot_use_scoped_source(self):
        self.fixture.promote()
        registry = json.loads((self.root / "task_ids.json").read_text())
        draft = registry["tasks"][0]
        draft.update(schema_version=3, context=self.context, approval_mode="approve_for_me",
                     project_sha256="b" * 64)
        draft["references"] = []
        (self.root / "task_ids.json").write_text(json.dumps(registry))
        findings = validation.draft_promotion_findings(self.root, self.request)
        self.assertTrue(any("same effective production context" in item.message
                            for item in findings))
        self.assertFalse(validation.draft_selected(self.root, draft))

    def test_invalid_active_manifest_blocks_all_mutations_before_any_write(self):
        (self.root / "requests").mkdir()
        (self.root / "requests/request_fixture.json").write_text("preserved")
        actions = (
            lambda: prepare_request.write_once(self.root, "requests/new.json", "{}"),
            lambda: prepare_request.release_unregistered_request(self.root, "fixture", "op"),
            lambda: operation_store.prepare_operation(self.root, self.request, self.caps, {}, []),
            lambda: operation_store.adopt_submitted_operation(
                self.root, self.request, self.caps, {}, [], "known", "succeeded", True),
            lambda: operation_store.transition_operation(
                self.root, "fixture-operation", "acknowledged", "terminal"),
            lambda: operation_store.replace_registry(
                self.root / "task_ids.json", {"schema_version": 1, "tasks": []}),
            lambda: draft_ledger.write_ledger(self.root, {"schema_version": 1, "drafts": []}),
            lambda: draft_ledger.record_draft(
                self.root, "fixture", "fixture-operation", "known", date(2026, 10, 19)),
        )
        active = self.root / "production.json"
        for state in ("valid", "malformed", "dangling", "directory"):
            if state == "dangling":
                active.symlink_to(self.root / "missing.json")
            elif state == "directory":
                active.mkdir()
            else:
                active.write_text("{}" if state == "valid" else "{")
            before = self.snapshot()
            for action in actions:
                with self.subTest(state=state, action=action):
                    with self.assertRaises(ValueError):
                        action()
                    self.assertEqual(before, self.snapshot())
            if active.is_dir():
                active.rmdir()
            else:
                active.unlink()

    def test_active_manifest_blocks_preparation_cli_without_output_files(self):
        (self.root / "production.json").write_text("{}")
        before = self.snapshot()
        result = subprocess.run(
            [sys.executable, str(validation.SCHEMA_ROOT.parents[1] / "scripts/prepare_request.py"),
             "--project", str(self.root), "--asset", "fixture", "--prompt", "prompt.md",
             "--model", "fixture-model", "--operation", "generate",
             "--expected-output", "out.mp4", "--write"],
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertEqual(before, self.snapshot())

    def test_studio_recognition_rejects_active_manifest_and_dangling_symlink(self):
        (self.root / "studio").mkdir()
        self.assertTrue(validation.studio_project(self.root))
        active = self.root / "production.json"
        active.write_text("{}")
        self.assertFalse(validation.studio_project(self.root))
        active.unlink()
        active.symlink_to(self.root / "missing.json")
        self.assertFalse(validation.studio_project(self.root))

    def test_scene_100_boards_and_keyframe_boards_are_guarded(self):
        for scene in ("01", "001", "100", "1000"):
            for name in ("sh010_p010_t01_v01.png", "sh010_board_t01_v01.png",
                         "kf01_board_v01.png", "sheet_pg01_v01.png",
                         "overview_v01.png", "animatic_v01.mp4"):
                self.assertTrue(validation.is_board_artifact(f"elsewhere/s{scene}_{name}"))
            self.assertTrue(validation.is_board_artifact(f"scenes/scene-{scene}/board/x.png"))
            self.assertFalse(validation.is_board_artifact(f"scenes/scene-{scene}/s{scene}_kf01_v01.png"))
            self.assertFalse(validation.is_board_artifact(f"elements/s{scene}_blocking_v01.png"))

    def test_scene_100_board_alias_and_missing_board_keep_reference_guards(self):
        board = self.root / "scenes/scene-100/board/panel.png"
        board.parent.mkdir(parents=True)
        board.write_bytes(b"panel")
        (self.root / "alias.png").symlink_to(board)
        self.request["references"][0]["path"] = "alias.png"
        findings = validation.reference_findings(
            self.root, self.request["references"], "@Image 1", model="seedance-2-5")
        self.assertIn("board.animatic_review_only", {item.rule_id for item in findings})
        self.request["references"][0]["path"] = "../scenes/scene-100/board/missing.png"
        findings = validation.reference_findings(
            self.root, self.request["references"], "@Image 1", model="seedance-2-5")
        self.assertIn("board.animatic_review_only", {item.rule_id for item in findings})
        self.assertIn("path.containment", {item.rule_id for item in findings})


class CandidateIntegrityTests(unittest.TestCase):
    def setUp(self):
        fixture = context_fixtures.ProductionContextTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.fixture = fixture
        self.context = resolve_candidate_context(self.root, "production.plan.json", "ep001").identity()

    def findings(self, context=None, unit="ep001"):
        return validation.candidate_scope_findings(
            self.root, self.context if context is None else context,
            manifest="production.plan.json", unit_id=unit)

    def test_candidate_scope_recomputes_and_detects_foreign_or_stale_context(self):
        self.assertEqual(self.findings(), [])
        self.assertTrue(self.findings(unit="ep002"))
        self.fixture.write("units/ep002/unit.md", "Unrelated revision")
        self.assertEqual(self.findings(), [])
        self.fixture.write("units/ep001/unit.md", "Changed selected unit")
        self.assertTrue(self.findings())

    def test_candidate_scope_rejects_malformed_and_production_scope(self):
        for context in ({}, None, {**self.context, "unit_id": "../ep001"},
                        {"context_version": 1, "kind": "production", "effective_sha256": "c" * 64}):
            if context is None:
                context = {"context_version": 99}
            self.assertTrue(self.findings(context))
        (self.root / "production.json").write_text("{}")
        self.assertTrue(self.findings())

    def test_candidate_request_checks_hash_and_recomputed_scope_without_writes(self):
        self.fixture.write("prompt.md", "A held shot.\n")
        prompt = (self.root / "prompt.md").read_bytes()
        request = {
            "schema_version": 3, "operation_id": "candidate", "asset_id": "candidate",
            "transport": "ark-mcp", "model": "fixture-model", "operation": "generate",
            "prompt_file": "prompt.md", "prompt_sha256": hashlib.sha256(prompt).hexdigest(),
            "references": [], "params": {}, "submission_status": "prepared",
            "provider_task_id": None, "provider_status": None, "review_status": "not_started",
            "cost": {"estimated": None, "confirmed": None, "currency": "USD"},
            "approval_mode": "approve_for_me",
            "project_sha256": validation.project_mode_snapshot(self.root)[1],
            "context": self.context,
        }
        request["request_sha256"] = validation.compute_request_hash(
            prompt, [], request["model"], request["operation"], {},
            approval_mode=request["approval_mode"], project_sha256=request["project_sha256"],
            schema_version=3, context=self.context)
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(validation.candidate_request_findings(
            self.root, request, manifest="production.plan.json", unit_id="ep001"), [])
        self.assertEqual(before, {
            path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()})
        request["context"] = {**self.context, "unit_id": "ep002"}
        rules = {item.rule_id for item in validation.candidate_request_findings(
            self.root, request, manifest="production.plan.json", unit_id="ep001")}
        self.assertEqual(rules, {"production.context_hash", "request.current_hash"})
        request["context"] = self.context
        for field, value in (("project_sha256", "a" * 64), ("approval_mode", "ask_for_approval")):
            changed = {**request, field: value}
            changed["request_sha256"] = validation.compute_request_hash(
                prompt, [], changed["model"], changed["operation"], {},
                approval_mode=changed["approval_mode"], project_sha256=changed["project_sha256"],
                schema_version=3, context=self.context)
            rules = {item.rule_id for item in validation.candidate_request_findings(
                self.root, changed, manifest="production.plan.json", unit_id="ep001")}
            self.assertEqual(rules, {"approval.current_mode"})


if __name__ == "__main__":
    unittest.main()
