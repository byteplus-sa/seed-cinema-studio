from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))
import draft_ledger
import operation_store
import prepare_request
import validate_request as validation


def profile() -> dict:
    now = datetime.now(UTC)
    return {
        "schema_version": 2,
        "profile_id": "synthetic-video-v1",
        "provider": "test-provider",
        "model": "synthetic-video",
        "operation": "text_to_video",
        "transport": "ark-mcp",
        "tool_schema_revision": "test-revision",
        "source": "offline synthetic fixture, not provider evidence",
        "verified_at": (now - timedelta(hours=1)).isoformat(),
        "valid_from": (now - timedelta(hours=2)).isoformat(),
        "expires_at": (now + timedelta(hours=2)).isoformat(),
        "operations": ["text_to_video"],
        "parameters": {
            "resolution": {"enum": ["480p", "720p"]},
            "draft": {"type": "boolean"},
            "draft_task_id": {"type": "string", "minLength": 1},
            "duration": {"type": "number", "minimum": 1},
        },
        "reference_roles": ["reference_image", "reference_audio"],
        "max_references": 3,
        "modality_limits": {
            "image": {"max_count": 1},
            "audio": {"max_count": 1, "max_duration_seconds": 2},
        },
        "parameter_constraints": [{"if": {"required": ["draft"]}, "then": {
            "properties": {"resolution": {"const": "480p"}}
        }}],
        "preview": {
            "native_draft": "unsupported",
            "promotion": "unsupported",
            "ordinary_preview": "supported",
        },
    }


def request(evidence: dict | None = None) -> dict:
    evidence = evidence or profile()
    destination = {key: evidence[key] for key in (
        "provider", "model", "operation", "transport", "tool_schema_revision"
    )}
    return {
        "model": evidence["model"], "operation": evidence["operation"],
        "transport": evidence["transport"], "params": {"resolution": "480p"},
        "references": [],
        "extensions": {"execution_profile": {
            "destination": destination, "evidence": copy.deepcopy(evidence)
        }},
    }


class CapabilityProfiles(unittest.TestCase):
    def test_legacy_evidence_without_conditionals_keeps_valid_schema(self):
        evidence = {
            "source": "synthetic legacy fixture", "verified_at": "2026-01-01T00:00:00Z",
            "model": "legacy", "operations": ["generate"],
            "parameters": {}, "reference_roles": [], "max_references": 0,
        }
        candidate = {"model": "legacy", "operation": "generate", "params": {}, "references": []}
        self.assertEqual(validation.capability_findings(candidate, evidence), [])

    def test_verified_ordinary_preview_is_valid_and_not_native(self):
        evidence = profile()
        candidate = request(evidence)
        self.assertEqual(validation.capability_findings(candidate, evidence), [])
        self.assertEqual(validation.native_draft_findings(candidate), [])
        candidate["params"]["draft"] = True
        self.assertTrue(validation.native_draft_findings(candidate))

    def test_each_destination_field_is_independently_checked(self):
        for field in ("provider", "model", "operation", "transport", "tool_schema_revision"):
            with self.subTest(field=field):
                evidence = profile()
                candidate = request(evidence)
                evidence[field] = "wrong-destination"
                self.assertTrue(validation.capability_findings(candidate, evidence))

    def test_v2_requires_independent_destination_not_self_comparison(self):
        evidence = profile()
        candidate = request(evidence)
        candidate["extensions"] = {}
        self.assertTrue(validation.capability_findings(candidate, evidence))

    def test_expiry_unknown_preview_and_remote_constraints_block(self):
        for mutation in ("expiry", "unknown", "remote", "interval", "missing"):
            with self.subTest(mutation=mutation):
                evidence = profile()
                if mutation == "expiry":
                    evidence["expires_at"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
                elif mutation == "unknown":
                    evidence["preview"]["ordinary_preview"] = "unknown"
                elif mutation == "remote":
                    evidence["parameter_constraints"] = [{"$ref": "https://invalid/schema"}]
                elif mutation == "interval":
                    evidence["valid_from"] = evidence["expires_at"]
                else:
                    del evidence["preview"]
                candidate = request(evidence)
                self.assertTrue(
                    validation.capability_findings(candidate, evidence)
                    or validation.native_draft_findings(candidate)
                )

    def test_modality_count_duration_and_missing_measurement_fail_closed(self):
        evidence = profile()
        for refs in (
            [{"role": "reference_image"}, {"role": "reference_image"}],
            [{"role": "reference_audio", "duration_seconds": 2.1}],
            [{"role": "reference_audio"}],
        ):
            candidate = request(evidence)
            candidate["references"] = refs
            self.assertTrue(validation.capability_findings(candidate, evidence))

    def test_conditional_constraints_are_enforced(self):
        evidence = profile()
        candidate = request(evidence)
        candidate["params"] = {"draft": True, "resolution": "720p"}
        self.assertTrue(validation.capability_findings(candidate, evidence))

    def test_exact_standard_and_premium_policy_cannot_be_disabled_by_profile(self):
        for model in ("dreamina-seedance-2-5-260628", "dreamina-seedance-2-5-premium-260915"):
            evidence = profile()
            evidence["model"] = model
            candidate = request(evidence)
            self.assertTrue(validation.native_draft_findings(candidate))
            candidate["params"] = {"draft": True, "resolution": "480p"}
            self.assertTrue(validation.native_draft_findings(candidate))
            evidence["preview"]["native_draft"] = "supported"
            candidate = request(evidence)
            candidate["params"]["draft"] = True
            self.assertEqual(validation.native_draft_findings(candidate), [])

    def test_unknown_family_model_has_no_inferred_draft_support(self):
        candidate = request()
        candidate["model"] = "unverified-seedance-2-5-future"
        candidate["extensions"] = {}
        candidate["params"]["draft"] = True
        self.assertTrue(validation.native_draft_findings(candidate))

    def test_profile_free_hashes_keep_legacy_canonical_body(self):
        refs = [{"sha256": "a" * 64, "role": "first_frame", "binding": "Image 1"}]
        body = {
            "prompt_sha256": hashlib.sha256(b"prompt").hexdigest(),
            "model": "legacy", "operation": "video", "params": {},
            "references": refs,
        }
        for version in (1, 2):
            mode = {} if version == 1 else {
                "approval_mode": "manual", "project_sha256": "b" * 64
            }
            expected = copy.deepcopy(body)
            if mode:
                expected.update(mode)
                expected["references"][0]["approval_evidence"] = None
            digest = hashlib.sha256(json.dumps(
                expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                allow_nan=False,
            ).encode()).hexdigest()
            self.assertEqual(validation.compute_request_hash(
                b"prompt", refs, "legacy", "video", {}, schema_version=version, **mode
            ), digest)

    def test_profile_snapshot_changes_new_hash_only(self):
        binding = request()["extensions"]["execution_profile"]
        baseline = validation.compute_request_hash(b"prompt", [], "model", "video", {})
        bound = validation.compute_request_hash(
            b"prompt", [], "model", "video", {}, execution_profile=binding
        )
        self.assertNotEqual(baseline, bound)
        binding["destination"]["tool_schema_revision"] = "changed"
        self.assertNotEqual(bound, validation.compute_request_hash(
            b"prompt", [], "model", "video", {}, execution_profile=binding
        ))

    def test_preparation_rejects_wrong_destination_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.md").write_text("# Offline fixture\n")
            (root / "prompt.md").write_text("A performer waits.")
            (root / "caps.json").write_text(json.dumps(profile()))
            args = prepare_request.parser().parse_args([
                "--project", str(root), "--asset", "fixture", "--prompt", "prompt.md",
                "--model", "synthetic-video", "--operation", "text_to_video",
                "--expected-output", "output.mp4", "--capabilities", "caps.json",
                "--provider", "wrong-provider", "--tool-schema-revision", "test-revision",
                "--param", "resolution=480p", "--write",
            ])
            _, findings = prepare_request.run(args)
            self.assertTrue(findings)
            self.assertFalse((root / "requests").exists())
            self.assertFalse((root / "task_ids.json").exists())

    def test_historical_adoption_reconciles_without_authorizing_new_plain_final(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.md").write_text("# Offline fixture\n")
            (root / "prompt.md").write_text("A performer waits.")
            args = prepare_request.parser().parse_args([
                "--project", str(root), "--asset", "fixture", "--prompt", "prompt.md",
                "--model", "dreamina-seedance-2-5-260628", "--operation", "generate",
                "--expected-output", "output.mp4", "--param", "resolution=720p",
            ])
            _, findings = prepare_request.run(args)
            self.assertTrue(findings)
            args.adopt_provider_task_id = "already-submitted-offline-fixture"
            _, findings = prepare_request.run(args)
            self.assertEqual(findings, [])
            self.assertFalse((root / "task_ids.json").exists())

    def test_cli_smoke_prepares_offline_profile_and_rejects_wrong_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.md").write_text("# Offline fixture\n")
            (root / "prompt.md").write_text("A performer waits.")
            (root / "caps.json").write_text(json.dumps(profile()))
            command = [
                sys.executable, "-B", str(Path(prepare_request.__file__)),
                "--project", str(root), "--asset", "fixture", "--prompt", "prompt.md",
                "--model", "synthetic-video", "--operation", "text_to_video",
                "--expected-output", "output.mp4", "--capabilities", "caps.json",
                "--provider", "test-provider", "--tool-schema-revision", "test-revision",
                "--param", "resolution=480p",
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["ok"])
            command[command.index("test-provider")] = "wrong-provider"
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["ok"])
            self.assertFalse((root / "requests").exists())

    def test_persisted_profile_digest_and_policy_are_checked_on_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.md").write_text("# Offline fixture\n")
            (root / "prompt.md").write_text("A performer waits.")
            (root / "caps.json").write_text(json.dumps(profile()))
            args = prepare_request.parser().parse_args([
                "--project", str(root), "--asset", "fixture", "--prompt", "prompt.md",
                "--model", "synthetic-video", "--operation", "text_to_video",
                "--expected-output", "output.mp4", "--capabilities", "caps.json",
                "--provider", "test-provider", "--tool-schema-revision", "test-revision",
                "--param", "resolution=480p",
            ])
            result, findings = prepare_request.run(args)
            self.assertEqual(findings, [])
            candidate = result["request"]
            candidate["extensions"]["execution_profile"]["evidence"]["preview"]["ordinary_preview"] = "unsupported"
            self.assertIn("request.current_hash", {
                finding.rule_id for finding in validation.prepared_evidence_findings(root, candidate)
            })
            registry = {"schema_version": 1, "tasks": [candidate]}
            (root / "task_ids.json").write_text(json.dumps(registry))
            before = (root / "task_ids.json").read_bytes()
            with self.assertRaises(ValueError):
                operation_store.transition_operation(
                    root, candidate["operation_id"], "prepared", "submitting"
                )
            self.assertEqual((root / "task_ids.json").read_bytes(), before)

    def test_v3_profile_free_hash_preserves_typed_context_and_new_profile_binds_it(self):
        context = {"context_version": 1, "kind": "unit", "unit_id": "episode-1", "effective_sha256": "c" * 64}
        body = {
            "prompt_sha256": hashlib.sha256(b"prompt").hexdigest(),
            "model": "legacy", "operation": "video", "params": {}, "references": [],
            "approval_mode": "approve_for_me", "project_sha256": "b" * 64,
            "context": context,
        }
        expected = hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode()).hexdigest()
        self.assertEqual(validation.compute_request_hash(
            b"prompt", [], "legacy", "video", {}, schema_version=3,
            approval_mode="approve_for_me", project_sha256="b" * 64, context=context,
        ), expected)


class CinemaRepairTests(unittest.TestCase):
    def setUp(self):
        from test_scoped_lifecycle import ScopedLifecycleTests

        self.fixture = ScopedLifecycleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.caps = profile()
        self.caps.update(
            model="dreamina-seedance-2-5-260628", operation="generate",
            operations=["generate"], reference_roles=[], max_references=0,
        )
        self.caps["parameters"]["resolution"] = {"enum": ["480p", "1080p"]}
        self.caps["parameters"].update({
            "watermark": {"type": "boolean"}, "return_last_frame": {"type": "boolean"},
            "priority": {"type": "integer", "minimum": 0, "maximum": 2},
            "execution_expires_after": {"type": "integer", "minimum": 1, "maximum": 86400},
            "safety_identifier": {"type": "string", "minLength": 1, "maxLength": 32},
        })
        self.caps["preview"].update(native_draft="supported", promotion="supported")
        self.fixture.caps = self.caps
        self.draft = self.fixture.request()
        self.draft["extensions"]["execution_profile"] = request(self.caps)["extensions"]["execution_profile"]
        self.fixture.rehash(self.draft)
        self.source = self.root / f"requests/request_{self.draft['asset_id']}.json"
        self.source.parent.mkdir()
        self.source.write_text(json.dumps(self.draft))
        self.fixture.complete(self.draft, "native-task")
        self.registered = operation_store.read_registry(self.root / "task_ids.json")["tasks"][0]
        self.decision = self.fixture.decision(self.draft)
        self.decision["upstream_sha256"][self.source.relative_to(self.root).as_posix()] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.fixture.select(self.decision, "scenes/scene-001/s001_sh010/shot.md")
        draft_ledger.record_draft(
            self.root, self.draft["asset_id"], self.draft["operation_id"], "native-task",
            draft_ledger.today(), status="approved",
        )

    def final(self, **controls):
        final = copy.deepcopy(self.draft)
        final["operation_id"] = final["asset_id"] = "final"
        final["extensions"]["expected_output"] = "scenes/scene-001/final.mp4"
        final["params"] = {"draft_task_id": "native-task", "resolution": "1080p", **controls}
        self.fixture.rehash(final)
        return final

    def rebind_source(self, value):
        self.source.write_text(json.dumps(value))
        self.decision["upstream_sha256"][self.source.relative_to(self.root).as_posix()] = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.fixture.write(
            f"decisions/{self.decision['decision_id']}.json", json.dumps(self.decision),
        )

    def test_profile_selection_binds_exact_registered_request_file_hash(self):
        self.assertNotEqual(self.decision["asset_id"], self.draft["asset_id"])
        self.assertEqual(validation.decision_findings(
            self.root, self.decision, context=self.draft["context"],
        ), [])
        self.assertTrue(validation.draft_selected(self.root, self.registered, require_decision=True))
        self.assertEqual(validation.draft_promotion_findings(self.root, self.final()), [])
        self.source.write_text(json.dumps({**self.draft, "request_sha256": "b" * 64}))
        self.assertFalse(validation.draft_selected(self.root, self.registered, require_decision=True))

    def test_rebound_source_body_schema_digest_and_registered_identity_block_submission(self):
        for mutation in (
            "operation_id", "asset_id", "model", "operation", "transport", "destination",
            "params", "expected_output", "schema", "digest", "null",
        ):
            with self.subTest(mutation=mutation):
                source = copy.deepcopy(self.draft)
                if mutation in ("operation_id", "asset_id", "model", "operation"):
                    source[mutation] = "other"
                elif mutation == "transport":
                    source[mutation] = "curl"
                elif mutation == "destination":
                    source["extensions"]["execution_profile"]["destination"]["provider"] = "other"
                elif mutation == "params":
                    source["params"]["duration"] = 9
                elif mutation == "expected_output":
                    source["extensions"]["expected_output"] = "scenes/scene-001/other.mp4"
                elif mutation == "schema":
                    del source["params"]
                elif mutation == "digest":
                    source["request_sha256"] = "b" * 64
                else:
                    source = None
                self.rebind_source(source)
                self.assertTrue(validation.decision_findings(
                    self.root, self.decision, context=self.draft["context"],
                ))
                self.assertFalse(validation.draft_selected(self.root, self.registered, require_decision=True))
                final = self.final()
                before = (self.root / "task_ids.json").read_bytes()
                with self.assertRaises(ValueError):
                    self.fixture.register(final)
                self.assertEqual((self.root / "task_ids.json").read_bytes(), before)
                self.fixture.write("task_ids.json", json.dumps({
                    "schema_version": 1, "tasks": [self.registered, final],
                }))
                before = (self.root / "task_ids.json").read_bytes()
                with self.assertRaises(ValueError):
                    operation_store.transition_operation(self.root, "final", "prepared", "submitting")
                self.assertEqual((self.root / "task_ids.json").read_bytes(), before)
                self.fixture.write("task_ids.json", json.dumps({
                    "schema_version": 1, "tasks": [self.registered],
                }))

    def test_missing_malformed_and_stale_source_fail_closed(self):
        for value in ("not json", "[]", "{}"):
            self.source.write_text(value)
            self.assertFalse(validation.draft_selected(self.root, self.registered, require_decision=True))
        self.source.unlink()
        self.assertFalse(validation.draft_selected(self.root, self.registered, require_decision=True))

    def test_documented_final_controls_pass_verified_value_schemas_and_submission(self):
        controls = {
            "watermark": False, "return_last_frame": True, "priority": 1,
            "execution_expires_after": 3600, "safety_identifier": "offline-fixture",
        }
        for control, value in controls.items():
            with self.subTest(control=control):
                final = self.final(**{control: value})
                self.assertEqual(validation.capability_findings(final, self.caps), [])
                self.assertEqual(validation.draft_promotion_findings(self.root, final), [])
        final = self.final(**controls)
        self.fixture.register(final)
        operation_store.transition_operation(self.root, "final", "prepared", "submitting")
        self.assertEqual(operation_store.read_registry(
            self.root / "task_ids.json",
        )["tasks"][1]["submission_status"], "submitting")

    def test_invalid_unsupported_and_creative_final_controls_remain_blocked(self):
        for controls in (
            {"execution_expires_after": 0}, {"execution_expires_after": 86401},
            {"execution_expires_after": True}, {"execution_expires_after": None},
            {"safety_identifier": ""}, {"safety_identifier": "x" * 33},
            {"safety_identifier": 1}, {"duration": 9}, {"unverified": True},
        ):
            with self.subTest(controls=controls):
                before = (self.root / "task_ids.json").read_bytes()
                with self.assertRaises(ValueError):
                    self.fixture.register(self.final(**controls))
                self.assertEqual((self.root / "task_ids.json").read_bytes(), before)
        final = self.final(safety_identifier="offline-fixture")
        unsupported = copy.deepcopy(self.caps)
        del unsupported["parameters"]["safety_identifier"]
        self.assertTrue(validation.capability_findings(final, unsupported))

    def test_expired_profile_allows_only_historical_recording_and_take_updates(self):
        (self.root / "drafts.json").unlink()
        with patch.object(validation, "datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime.now(UTC) + timedelta(hours=3)
            self.assertFalse(validation.native_task_supported(self.registered))
            entry = draft_ledger.record_draft(
                self.root, self.draft["asset_id"], self.draft["operation_id"],
                "native-task", draft_ledger.today(),
            )
            self.assertEqual(entry["status"], "drafted")
            entry = draft_ledger.record_draft(
                self.root, self.draft["asset_id"], self.draft["operation_id"],
                "native-task", draft_ledger.today(), take=self.decision["subject_path"],
            )
            self.assertEqual(entry["take"], self.decision["subject_path"])
            document = draft_ledger.read_ledger(self.root)
            document["drafts"][0]["status"] = "expired"
            draft_ledger.validate_ledger_update(self.root, document)
            draft_ledger.write_ledger(self.root, document)
            before = (self.root / "drafts.json").read_bytes()
            for status in ("approved", "promoted"):
                with self.subTest(status=status), self.assertRaises(ValueError):
                    draft_ledger.record_draft(
                        self.root, self.draft["asset_id"], self.draft["operation_id"],
                        "native-task", draft_ledger.today(), status=status,
                    )
                self.assertEqual((self.root / "drafts.json").read_bytes(), before)
            self.assertTrue(validation.draft_promotion_findings(self.root, self.final()))
            pending = copy.deepcopy(self.draft)
            pending["operation_id"] = pending["asset_id"] = "pending"
            self.assertTrue(validation.prepared_evidence_findings(
                self.root, pending, unit_id="ep001",
            ))
            self.fixture.write("units/ep001/unit.md", "Changed creative brief.\n")
            draft_ledger.record_draft(
                self.root, self.draft["asset_id"], self.draft["operation_id"],
                "native-task", draft_ledger.today(), status="expired",
            )
            self.assertEqual(draft_ledger.read_ledger(self.root)["drafts"][0]["context"], self.draft["context"])

    def test_expired_history_cannot_relabel_plain_or_changed_native_identity(self):
        (self.root / "drafts.json").unlink()
        for mutation in ("draft", "provider_task_id", "profile", "digest"):
            changed = copy.deepcopy(self.registered)
            if mutation == "draft":
                changed["params"].pop("draft")
            elif mutation == "provider_task_id":
                changed["provider_task_id"] = None
            elif mutation == "profile":
                changed["extensions"]["execution_profile"]["destination"]["provider"] = "other"
            else:
                changed["request_sha256"] = "b" * 64
            self.fixture.write("task_ids.json", json.dumps({"schema_version": 1, "tasks": [changed]}))
            with patch.object(validation, "datetime", wraps=datetime) as clock:
                clock.now.return_value = datetime.now(UTC) + timedelta(hours=3)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    draft_ledger.record_draft(
                        self.root, self.draft["asset_id"], self.draft["operation_id"],
                        "native-task", draft_ledger.today(),
                    )
                self.assertFalse((self.root / "drafts.json").exists())


if __name__ == "__main__":
    unittest.main()
