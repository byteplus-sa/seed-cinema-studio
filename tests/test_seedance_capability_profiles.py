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

    def test_profile_selection_binds_exact_registered_request_file_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requests").mkdir()
            (root / "decisions").mkdir()
            draft = {
                **request(), "asset_id": "fixture", "review_status": "approved",
                "request_sha256": "a" * 64,
            }
            draft["extensions"]["expected_output"] = "take.mp4"
            source = root / "requests/request_fixture.json"
            source.write_text(json.dumps(draft))
            decision = {
                "decision_type": "variant_selection", "subject_path": "take.mp4",
                "upstream_sha256": {},
            }
            target = root / "decisions/select.json"
            target.write_text(json.dumps(decision))
            with patch.object(validation, "decision_findings", return_value=[]):
                self.assertFalse(validation.draft_selected(root, draft, require_decision=True))
                decision["upstream_sha256"][source.relative_to(root).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
                target.write_text(json.dumps(decision))
                self.assertTrue(validation.draft_selected(root, draft, require_decision=True))
                source.write_text(json.dumps({**draft, "request_sha256": "b" * 64}))
                self.assertFalse(validation.draft_selected(root, draft, require_decision=True))

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


if __name__ == "__main__":
    unittest.main()
