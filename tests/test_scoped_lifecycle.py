from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from unittest.mock import patch

import test_production_context as fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / ".agents/skills/showcase-html/scripts"))

import draft_ledger
import operation_store
import prepare_request
import production_context
import selection_service
import validate_request as validation


class ScopedLifecycleTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ProductionContextTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.write = fixture.write
        clock = patch.object(draft_ledger, "today", return_value=date(2026, 10, 19))
        clock.start()
        self.addCleanup(clock.stop)
        self.write("production.json", json.dumps(fixture.manifest))
        self.write("units/ep001/studio/index.html", "<html></html>")
        self.write("units/ep001/studio/hyperframes.json", "{}")
        self.write("scenes/scene-001/prompt.md", "A quiet held shot.\n")
        self.write("scenes/scene-002/prompt.md", "A quiet held shot.\n")
        self.caps = {
            "model": "seedance-2-5", "source": "synthetic fixture",
            "verified_at": "2026-10-19T00:00:00Z", "operations": ["generate"],
            "parameters": {"resolution": {"enum": ["480p", "1080p"]},
                           "draft": {"type": "boolean"},
                           "draft_task_id": {"type": "string"}},
            "reference_roles": [], "max_references": 0,
        }

    def request(self, unit="ep001", production=False):
        scene = "scene-001" if unit == "ep001" else "scene-002"
        if production:
            self.write("elements/hero/prompt.md", "A portrait.\n")
        arguments = [
            "--project", str(self.root), "--asset", f"{unit}-draft",
            "--operation-id", f"{unit}-draft", "--model", "seedance-2-5",
            "--operation", "generate", "--param", "resolution=480p",
            "--param", "draft=true", "--prompt",
            "elements/hero/prompt.md" if production else f"scenes/{scene}/prompt.md",
            "--expected-output",
            "elements/hero/image.png" if production else f"scenes/{scene}/take.mp4",
        ]
        arguments += ["--production-scope"] if production else ["--unit", unit]
        return prepare_request.build_request(self.root, prepare_request.parser().parse_args(arguments))

    def review(self, request):
        return {
            "schema_version": 1, "request_sha256": request["request_sha256"],
            "reviewer_status": "complete",
            "checks": [{"rule_id": "fixture", "status": "pass", "evidence": "Inspected"}],
        }

    def rehash(self, request):
        prompt = (self.root / request["prompt_file"]).read_bytes()
        request["prompt_sha256"] = hashlib.sha256(prompt).hexdigest()
        request["request_sha256"] = validation.compute_request_hash(
            prompt, request["references"], request["model"], request["operation"],
            request["params"], approval_mode=request["approval_mode"],
            project_sha256=request["project_sha256"], schema_version=3,
            context=request["context"])

    def select(self, decision, manifest):
        registry = {decision["asset_id"]: {
            "manifest": manifest, "field": "selected_variant", "key": None,
            "stage": "shot-generation",
            "variants": {decision["selected_variant"]: decision["subject_path"]},
            "reviews": {},
        }}
        batch = selection_service.validate_selections(
            self.root, registry, {decision["asset_id"]: decision["selected_variant"]},
            context=decision["context"])
        return selection_service.apply_selection_batch(
            self.root, batch, batch["revision"],
            decisions={decision["asset_id"]: decision}, allow_chat=True,
            context=decision["context"])

    def complete(self, request, task_id):
        self.register(request, unit=request["context"].get("unit_id"),
                      production=request["context"]["kind"] == "production")
        operation_store.transition_operation(
            self.root, request["operation_id"], "prepared", "submitting")
        operation_store.transition_operation(
            self.root, request["operation_id"], "submitting", "terminal",
            provider_task_id=task_id, provider_status="succeeded")

    def register(self, request, unit="ep001", production=False):
        operation_store.prepare_operation(
            self.root, request, self.caps, self.review(request), ["fixture"],
            unit_id=unit if not production else None, production_scope=production,
        )

    def decision(self, request, actor="agent"):
        source = request["extensions"]["expected_output"]
        self.write(source, "synthetic media")
        digest = hashlib.sha256((self.root / source).read_bytes()).hexdigest()
        review_path = f"reviews/{request['asset_id']}.json"
        self.write(review_path, json.dumps({
            "schema_version": 1, "artifact_path": source, "artifact_sha256": digest,
            "status": "pass", "inspection_method": "full playback and listening",
            "coverage": "complete", "checks": [
                {"criterion": "continuity", "status": "pass", "evidence": "Verified"}],
            "observations": ["Synthetic fixture preserves the planned continuity."],
            "limitations": ["Synthetic lifecycle evidence, not creative approval."],
            "recommendation": "Select",
        }))
        upstream = {}
        if request["context"]["kind"] == "unit":
            brief = f"units/{request['context']['unit_id']}/unit.md"
            upstream[brief] = hashlib.sha256((self.root / brief).read_bytes()).hexdigest()
        decision = {
            "schema_version": 2, "decision_id": request["asset_id"],
            "decision_type": "variant_selection", "asset_id": "shot-not-take",
            "subject_path": source, "selected_variant": Path(source).name,
            "selected_sha256": digest, "actor": actor,
            "approval_mode": request["approval_mode"],
            "project_sha256": request["project_sha256"], "context": request["context"],
            "result": "approved", "review_path": review_path,
            "review_sha256": hashlib.sha256((self.root / review_path).read_bytes()).hexdigest(),
            "upstream_sha256": upstream, "reason": "Passing take",
            "decided_at": "2026-10-19T00:00:00Z",
        }
        if actor == "user":
            decision["authorization"] = {"source": "chat", "evidence": "Select this take."}
        return decision

    def test_preparation_registration_and_reconciliation_preserve_identity(self):
        request = self.request()
        self.assertEqual(request["schema_version"], 3)
        self.register(request)
        for before, after, extra in [
            ("prepared", "submitting", {}),
            ("submitting", "submission_unknown", {}),
            ("submission_unknown", "acknowledged", {"provider_task_id": "known"}),
            ("acknowledged", "terminal", {"provider_status": "succeeded"}),
        ]:
            operation_store.transition_operation(self.root, request["operation_id"], before, after, **extra)
        stored = operation_store.read_registry(self.root / "task_ids.json")["tasks"][0]
        self.assertEqual(stored["context"], request["context"])
        self.assertEqual(stored["request_sha256"], request["request_sha256"])
        self.assertEqual(stored["review_status"], "review")
        entry = draft_ledger.record_draft(
            self.root, request["asset_id"], request["operation_id"], "known", date(2026, 10, 19))
        self.assertEqual(entry["context"], request["context"])

    def test_foreign_registration_and_stale_submission_fail_without_registry_changes(self):
        request = self.request()
        with self.assertRaises(ValueError):
            self.register(request, unit="ep002")
        self.assertFalse((self.root / "task_ids.json").exists())
        self.register(request)
        before = (self.root / "task_ids.json").read_bytes()
        self.write("units/ep001/unit.md", "Changed story")
        with self.assertRaises(ValueError):
            operation_store.transition_operation(self.root, request["operation_id"], "prepared", "submitting")
        self.assertEqual((self.root / "task_ids.json").read_bytes(), before)

    def test_unrelated_unit_and_billing_edits_preserve_prepared_review(self):
        request = self.request()
        self.register(request)
        self.write("units/ep002/unit.md", "A different episode")
        self.write("project.md", "---\napproval_mode: approve_for_me\n"
                   "billing:\n  confirmed: 99\nupdated_at: today\n---\nShared story.\n")
        self.assertEqual(validation.validate_request(self.root, request, self.caps, unit_id="ep001"), [])
        operation_store.transition_operation(self.root, request["operation_id"], "prepared", "submitting")

    def test_scoped_checks_and_selection_require_explicit_unit(self):
        request = self.request()
        self.assertTrue(validation.validate_request(self.root, request, self.caps))
        decision = self.decision(request)
        with self.assertRaises(ValueError):
            selection_service.validated_decision(
                self.root, decision, decision["subject_path"], decision["selected_sha256"],
                "approve_for_me", allow_chat=True)
        selection_service.validated_decision(
            self.root, decision, decision["subject_path"], decision["selected_sha256"],
            "approve_for_me", context=request["context"])
        with self.assertRaises(ValueError):
            selection_service.validated_decision(
                self.root, decision, decision["subject_path"], decision["selected_sha256"],
                "approve_for_me", context=production_context.resolve_context(self.root, "ep002"))

    def test_unit_decision_requires_current_brief_and_real_unit_studio(self):
        request = self.request()
        decision = self.decision(request, actor="user")
        self.assertEqual(validation.decision_findings(
            self.root, decision, context=request["context"], require_current_project=True), [])
        decision["upstream_sha256"] = {}
        self.assertTrue(validation.decision_findings(self.root, decision, context=request["context"]))
        decision = self.decision(request, actor="user")
        self.write("units/ep001/unit.md", "Changed")
        self.assertTrue(validation.decision_findings(self.root, decision, context=request["context"]))

    def test_production_canon_decisions_work_in_both_modes_without_root_studio(self):
        for mode, actor in (("approve_for_me", "agent"), ("ask_for_approval", "user")):
            self.write("project.md", f"---\napproval_mode: {mode}\n---\nShared story.\n")
            request = self.request(production=True)
            decision = self.decision(request, actor=actor)
            self.assertEqual(validation.decision_findings(
                self.root, decision, context=request["context"], require_current_project=True), [])
            selection_service.validated_decision(
                self.root, decision, decision["subject_path"], decision["selected_sha256"],
                mode, allow_chat=True, context=request["context"])
        self.assertFalse((self.root / "studio").exists())

    def test_draft_promotion_requires_same_effective_context_and_selection(self):
        request = self.request()
        decision = self.decision(request)
        self.write(f"decisions/{decision['decision_id']}.json", json.dumps(decision))
        draft = {**request, "submission_status": "terminal", "provider_status": "succeeded",
                 "provider_task_id": "known", "review_status": "review"}
        self.write("task_ids.json", json.dumps({"schema_version": 1, "tasks": [draft]}))
        draft_ledger.record_draft(
            self.root, request["asset_id"], request["operation_id"], "known",
            date(2026, 10, 19), status="approved")
        final = copy.deepcopy(request)
        final["params"] = {"draft_task_id": "known", "resolution": "1080p"}
        self.assertEqual(validation.draft_promotion_findings(self.root, final), [])
        foreign = self.request("ep002")
        foreign["params"] = final["params"]
        self.assertTrue(validation.draft_promotion_findings(self.root, foreign))
        self.write("units/ep001/unit.md", "Changed")
        self.assertTrue(validation.draft_promotion_findings(self.root, final))

    def test_unscoped_history_is_not_reinterpreted_on_active_layout(self):
        request = self.request()
        request.pop("context")
        request["schema_version"] = 2
        self.assertTrue(validation.validate_request(self.root, request, self.caps, unit_id="ep001"))
        with self.assertRaises(ValueError):
            self.register(request)

    def test_adoption_never_resubmits_and_duplicate_registration_is_rejected(self):
        request = self.request()
        operation_store.adopt_submitted_operation(
            self.root, request, self.caps, self.review(request), ["fixture"],
            "known", "succeeded", True, unit_id="ep001")
        stored = operation_store.read_registry(self.root / "task_ids.json")["tasks"][0]
        self.assertEqual(stored["submission_status"], "terminal")
        self.assertEqual(stored["provider_task_id"], "known")
        with self.assertRaises(ValueError):
            self.register(request)

    def test_selection_batch_revalidates_scope_inside_transaction(self):
        request = self.request()
        decision = self.decision(request)
        manifest = "scenes/scene-001/s001_sh010/shot.md"
        registry = {
            decision["asset_id"]: {
                "manifest": manifest, "field": "selected_variant", "key": None,
                "stage": "shot-generation",
                "variants": {decision["selected_variant"]: decision["subject_path"]},
                "reviews": {},
            },
        }
        batch = selection_service.validate_selections(
            self.root, registry, {decision["asset_id"]: decision["selected_variant"]})
        self.write("units/ep001/unit.md", "Changed after reviewing")
        before = (self.root / manifest).read_bytes()
        with self.assertRaises(ValueError):
            selection_service.apply_selection_batch(
                self.root, batch, batch["revision"],
                decisions={decision["asset_id"]: decision}, context=request["context"])
        self.assertEqual((self.root / manifest).read_bytes(), before)
        self.assertFalse((self.root / "selection.log").exists())

    def test_same_path_foreign_registry_output_cannot_be_relabelled(self):
        request = self.request()
        request["extensions"]["expected_output"] = "library/shared.mp4"
        decision = self.decision(request)
        foreign = self.request("ep002")
        foreign["extensions"]["expected_output"] = decision["subject_path"]
        self.write("task_ids.json", json.dumps({"schema_version": 1, "tasks": [foreign]}))
        self.assertTrue(validation.decision_findings(self.root, decision, context=request["context"]))

    def test_agent_decision_and_chat_cannot_use_uninitialized_or_escaped_studio(self):
        request = self.request("ep002")
        for actor in ("agent", "user"):
            decision = self.decision(request, actor=actor)
            self.assertTrue(validation.decision_findings(self.root, decision, context=request["context"]))
        (self.root / "units/ep002/studio").symlink_to(self.root / "units/ep001/studio")
        self.assertFalse(validation.studio_project(self.root, request["context"]))

    def test_ledger_cannot_promote_a_foreign_unit_final(self):
        draft = self.request()
        draft.update(provider_task_id="known", submission_status="terminal", provider_status="succeeded")
        final = self.request("ep002")
        final["params"] = {"draft_task_id": "known", "resolution": "1080p"}
        self.write("task_ids.json", json.dumps({"schema_version": 1, "tasks": [draft, final]}))
        draft_ledger.record_draft(
            self.root, draft["asset_id"], draft["operation_id"], "known", date(2026, 10, 19))
        before = (self.root / "drafts.json").read_bytes()
        with self.assertRaises(ValueError):
            draft_ledger.record_draft(
                self.root, draft["asset_id"], draft["operation_id"], "known",
                date(2026, 10, 19), final_operation_id=final["operation_id"])
        self.assertEqual((self.root / "drafts.json").read_bytes(), before)

    def lifecycle(self, mode, actor):
        self.write("project.md", f"---\napproval_mode: {mode}\n---\nShared story.\n")
        canon = self.request(production=True)
        canon["asset_id"] = canon["operation_id"] = "shared-hero"
        self.complete(canon, "canon-task")
        decision = self.decision(canon, actor)
        decision["asset_id"] = "hero"
        self.write("elements/hero/element.md", "---\nstatus: review\n---\nHero.\n")
        self.select(decision, "elements/hero/element.md")
        draft = self.request()
        self.write(draft["prompt_file"], "A quiet held shot of @Image 1.\n")
        reference = prepare_request.build_references(self.root, [
            "elements/hero/image.png:reference_image:elements/hero/element.md"])[0]
        reference["approval_evidence"] = prepare_request.decision_evidence(
            self.root, reference, None)
        draft["references"] = [reference]
        self.caps.update(reference_roles=["reference_image"], max_references=1)
        self.rehash(draft)
        self.complete(draft, "draft-task")
        decision = self.decision(draft, actor)
        self.select(decision, "scenes/scene-001/s001_sh010/shot.md")
        with patch.object(draft_ledger, "today", return_value=date(2026, 10, 19)):
            draft_ledger.record_draft(
                self.root, draft["asset_id"], draft["operation_id"], "draft-task",
                date(2026, 10, 19), take=decision["subject_path"], status="approved")
            final = copy.deepcopy(draft)
            final["operation_id"] = final["asset_id"] = "ep001-final"
            final["params"] = {"draft_task_id": "draft-task", "resolution": "1080p"}
            final["references"] = []
            final["extensions"]["expected_output"] = "scenes/scene-001/final.mp4"
            self.rehash(final)
            self.complete(final, "final-task")
            entry = draft_ledger.record_draft(
                self.root, draft["asset_id"], draft["operation_id"], "draft-task",
                date(2026, 10, 19), final_operation_id=final["operation_id"])
        self.assertEqual(entry["status"], "promoted")
        decision = self.decision(final, actor)
        self.select(decision, "scenes/scene-001/s001_sh010/shot.md")
        self.assertEqual(validation.decision_findings(
            self.root, decision, context=final["context"]), [])
        self.assertFalse((self.root / "studio").exists())

    def test_full_lifecycle_with_agent_authorization_and_shared_canon(self):
        self.lifecycle("approve_for_me", "agent")

    def test_full_lifecycle_with_chat_authorization_and_shared_canon(self):
        self.lifecycle("ask_for_approval", "user")

    def test_separate_unit_selections_preserve_shared_derived_state(self):
        for unit, scene in (("ep001", "001"), ("ep002", "002")):
            self.write(f"units/{unit}/studio/index.html", "<html></html>")
            self.write(f"units/{unit}/studio/hyperframes.json", "{}")
            decision = self.decision(self.request(unit))
            decision["asset_id"] = f"s{scene}_sh010"
            self.select(decision, f"scenes/scene-{scene}/s{scene}_sh010/shot.md")
        selected = json.loads((self.root / "selection.json").read_text())["selections"]
        self.assertEqual(set(selected), {"s001_sh010", "s002_sh010"})

    def test_stale_submitted_context_can_reconcile_but_not_authorize(self):
        request = self.request()
        self.register(request)
        operation_store.transition_operation(
            self.root, request["operation_id"], "prepared", "submitting")
        self.write("units/ep001/unit.md", "Revised while provider was running.")
        operation_store.transition_operation(
            self.root, request["operation_id"], "submitting", "submission_unknown")
        operation_store.transition_operation(
            self.root, request["operation_id"], "submission_unknown", "terminal",
            provider_task_id="known", provider_status="succeeded")
        stored = operation_store.read_registry(self.root / "task_ids.json")["tasks"][0]
        self.assertEqual(stored["context"], request["context"])
        self.assertEqual(stored["review_status"], "review")
        self.assertFalse(validation.draft_selected(self.root, stored))

    def test_late_draft_recording_preserves_historical_context_without_authorizing(self):
        request = self.request()
        self.register(request)
        operation_store.transition_operation(
            self.root, request["operation_id"], "prepared", "submitting")
        self.write("units/ep001/unit.md", "Revised while provider was running.")
        operation_store.transition_operation(
            self.root, request["operation_id"], "submitting", "terminal",
            provider_task_id="late-id", provider_status="succeeded")
        entry = draft_ledger.record_draft(
            self.root, request["asset_id"], request["operation_id"], "late-id",
            date(2026, 10, 19), status=None)
        self.assertEqual(entry["status"], "drafted")
        self.assertEqual(entry["context"], request["context"])
        self.assertEqual(entry["request_sha256"], request["request_sha256"])
        before = (self.root / "drafts.json").read_bytes()
        for status in ("approved", "promoted"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                draft_ledger.record_draft(
                    self.root, request["asset_id"], request["operation_id"], "late-id",
                    date(2026, 10, 19), status=status)
            self.assertEqual((self.root / "drafts.json").read_bytes(), before)
        final = copy.deepcopy(request)
        final["params"] = {"draft_task_id": "late-id", "resolution": "1080p"}
        self.assertTrue(validation.draft_promotion_findings(self.root, final))

    def test_late_acknowledged_draft_can_record_take_but_not_mismatched_identity(self):
        request = self.request()
        self.register(request)
        operation_store.transition_operation(
            self.root, request["operation_id"], "prepared", "submitting")
        operation_store.transition_operation(
            self.root, request["operation_id"], "submitting", "acknowledged",
            provider_task_id="late-id", provider_status="running")
        self.write("units/ep001/unit.md", "Revised after acknowledgment.")
        draft_ledger.record_draft(
            self.root, request["asset_id"], request["operation_id"], "late-id",
            date(2026, 10, 19))
        take = request["extensions"]["expected_output"]
        self.write(take, "synthetic downloaded media")
        entry = draft_ledger.record_draft(
            self.root, request["asset_id"], request["operation_id"], "late-id",
            date(2026, 10, 19), take=take)
        self.assertEqual(entry["take"], take)
        self.assertEqual(entry["context"], request["context"])
        before = (self.root / "drafts.json").read_bytes()
        for task_id, output in (("foreign-id", take), ("late-id", "scenes/scene-002/take.mp4")):
            with self.subTest(task_id=task_id, output=output), self.assertRaises(ValueError):
                draft_ledger.record_draft(
                    self.root, request["asset_id"], request["operation_id"], task_id,
                    date(2026, 10, 19), take=output)
            self.assertEqual((self.root / "drafts.json").read_bytes(), before)
        forged = draft_ledger.read_ledger(self.root)
        forged["drafts"][0]["status"] = "approved"
        with self.assertRaises(ValueError):
            draft_ledger.write_ledger(self.root, forged)
        self.assertEqual((self.root / "drafts.json").read_bytes(), before)

    def test_late_draft_recording_cannot_invent_an_unacknowledged_provider_id(self):
        request = self.request()
        self.register(request)
        operation_store.transition_operation(
            self.root, request["operation_id"], "prepared", "submitting")
        operation_store.transition_operation(
            self.root, request["operation_id"], "submitting", "submission_unknown")
        self.write("units/ep001/unit.md", "Revised before reconciliation.")
        with self.assertRaises(ValueError):
            draft_ledger.record_draft(
                self.root, request["asset_id"], request["operation_id"], "invented",
                date(2026, 10, 19))
        self.assertFalse((self.root / "drafts.json").exists())

    def test_scoped_draft_status_cannot_invent_approval_or_promotion(self):
        request = self.request()
        self.complete(request, "known")
        draft_ledger.record_draft(
            self.root, request["asset_id"], request["operation_id"], "known",
            date(2026, 10, 19))
        before = (self.root / "drafts.json").read_bytes()
        for status in ("approved", "promoted"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                draft_ledger.record_draft(
                    self.root, request["asset_id"], request["operation_id"], "known",
                    date(2026, 10, 19), status=status)
            self.assertEqual((self.root / "drafts.json").read_bytes(), before)

    def test_ledger_whole_document_write_cannot_delete_history(self):
        request = self.request()
        self.complete(request, "known")
        draft_ledger.record_draft(
            self.root, request["asset_id"], request["operation_id"], "known",
            date(2026, 10, 19))
        before = (self.root / "drafts.json").read_bytes()
        with self.assertRaises(ValueError):
            draft_ledger.write_ledger(self.root, {"schema_version": 1, "drafts": []})
        self.assertEqual((self.root / "drafts.json").read_bytes(), before)

    def test_concurrent_unit_registration_and_ledger_updates_preserve_both(self):
        self.write("units/ep002/studio/index.html", "<html></html>")
        self.write("units/ep002/studio/hyperframes.json", "{}")
        requests = [self.request(unit) for unit in ("ep001", "ep002")]

        def run(request):
            task_id = request["operation_id"]
            self.complete(request, task_id)
            return draft_ledger.record_draft(
                self.root, request["asset_id"], request["operation_id"], task_id,
                date(2026, 10, 19))

        with ThreadPoolExecutor(max_workers=2) as workers:
            entries = list(workers.map(run, requests))
        self.assertEqual(len(entries), 2)
        self.assertEqual(len(draft_ledger.read_ledger(self.root)["drafts"]), 2)
        self.assertEqual(len(operation_store.read_registry(self.root / "task_ids.json")["tasks"]), 2)

    def test_selection_commit_recovery_preserves_unit_scope(self):
        request = self.request()
        decision = self.decision(request)
        atomic_write = selection_service.atomic_write

        def interrupted(path, content):
            if path == self.root / "selection.log":
                raise OSError("Injected commit interruption")
            return atomic_write(path, content)

        with (
            patch.object(selection_service, "atomic_write", side_effect=interrupted),
            self.assertRaises(selection_service.SelectionConflict),
        ):
            self.select(decision, "scenes/scene-001/s001_sh010/shot.md")
        with selection_service.writer_lock(self.root):
            self.assertTrue(selection_service.recover_selection(self.root))
            self.assertFalse(selection_service.recover_selection(self.root))
        stored = json.loads((self.root / f"decisions/{decision['decision_id']}.json").read_text())
        self.assertEqual(stored["context"], request["context"])
        self.assertEqual(len((self.root / "selection.log").read_text().splitlines()), 1)
        self.assertFalse((self.root / "studio").exists())

    def test_foreign_registry_output_alias_cannot_be_relabelled(self):
        request = self.request()
        request["extensions"]["expected_output"] = "library/shared.mp4"
        decision = self.decision(request)
        (self.root / "library/alias.mp4").symlink_to(self.root / decision["subject_path"])
        foreign = self.request("ep002")
        foreign["extensions"]["expected_output"] = "library/alias.mp4"
        self.write("task_ids.json", json.dumps({"schema_version": 1, "tasks": [foreign]}))
        self.assertTrue(validation.decision_findings(self.root, decision, context=request["context"]))

    def test_scoped_selection_revision_ignores_unrelated_runtime_changes(self):
        request = self.request()
        decision = self.decision(request)
        before = selection_service.stage_revision(self.root, context=request["context"])
        self.write("units/ep002/unit.md", "Unrelated revision.")
        self.write("project.md", "---\napproval_mode: approve_for_me\n"
                   "budget:\n  confirmed: 100\nbilling:\n  confirmed: 100\n"
                   "runtime:\n  status: running\n---\nShared story.\n")
        self.assertEqual(selection_service.stage_revision(self.root, context=request["context"]), before)
        self.assertEqual(validation.decision_findings(self.root, decision, context=request["context"]), [])
        self.select(decision, "scenes/scene-001/s001_sh010/shot.md")

    def test_concurrent_same_unit_selection_has_one_winner(self):
        request = self.request()
        decision = self.decision(request)

        def run(_):
            try:
                self.select(decision, "scenes/scene-001/s001_sh010/shot.md")
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(run, range(2))), [False, True])
        self.assertEqual(len((self.root / "selection.log").read_text().splitlines()), 1)

    def test_scoped_promotion_requires_unexpired_hash_bound_ledger(self):
        request = self.request()
        self.complete(request, "known")
        decision = self.decision(request)
        self.select(decision, "scenes/scene-001/s001_sh010/shot.md")
        final = copy.deepcopy(request)
        final["operation_id"] = final["asset_id"] = "final"
        final["params"] = {"draft_task_id": "known", "resolution": "1080p"}
        self.rehash(final)
        self.assertTrue(validation.draft_promotion_findings(self.root, final))
        draft_ledger.record_draft(
            self.root, request["asset_id"], request["operation_id"], "known",
            date(2026, 10, 19), status="approved")
        with patch.object(draft_ledger, "today", return_value=date(2026, 10, 26)):
            self.assertEqual(validation.draft_promotion_findings(self.root, final), [])
        with patch.object(draft_ledger, "today", return_value=date(2026, 10, 27)):
            self.assertTrue(validation.draft_promotion_findings(self.root, final))
        ledger = draft_ledger.read_ledger(self.root)
        ledger["drafts"][0]["request_sha256"] = "f" * 64
        self.write("drafts.json", json.dumps(ledger))
        self.assertTrue(validation.draft_promotion_findings(self.root, final))


if __name__ == "__main__":
    unittest.main()
