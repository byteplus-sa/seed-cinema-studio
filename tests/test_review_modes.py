from __future__ import annotations

import contextlib
import copy
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_prepare_request as prepare_fixtures
import test_scoped_lifecycle as scoped_fixtures
import test_unit_studio as studio_fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))
import operation_store
import prepare_request
import production_context
import production_profiles
import studio_project as studio
import validate_request as validation


def validate_cli(root, request, capabilities, *extra):
    request_path = root / "cli-request.json"
    capability_path = root / "cli-capabilities.json"
    request_path.write_text(json.dumps(request))
    capability_path.write_text(json.dumps(capabilities))
    return subprocess.run(
        [
            sys.executable, str(Path(validation.__file__)),
            "--project", str(root), "--request", str(request_path),
            "--capabilities", str(capability_path), *extra,
        ],
        capture_output=True, text=True, check=False,
    )


class ReviewModeTests(unittest.TestCase):
    def test_review_and_creative_policies_do_not_restore_financial_gates(self):
        root = Path(__file__).resolve().parents[1]
        for relative in (
            ".agents/contracts/production-policy.md",
            ".agents/skills/film-production/references/stage-contracts.md",
            ".agents/skills/seedance-prompt-25/SKILL.md",
            ".agents/skills/seedance-prompt-25/references/shot-staging.md",
        ):
            with self.subTest(path=relative):
                text = " ".join((root / relative).read_text().split()).lower()
                self.assertNotRegex(
                    text,
                    r"scope and budget|rights, spending|rights, budget|"
                    r"within the declared budget|within the caller's budget",
                )

    def test_review_depth_does_not_waive_native_drafts_or_performance_checks(self):
        root = Path(__file__).resolve().parents[1]
        paths = [
            root / "AGENTS.md",
            root / ".agents/contracts/draft-promotion.md",
            root / ".agents/contracts/production-policy.md",
            root / ".agents/contracts/production-brief.md",
            root / ".agents/contracts/rules.json",
        ]
        for name in ("brief-intake", "film-production", "micro-drama", "seedance-prompt-25"):
            paths.extend((root / ".agents/skills" / name).rglob("*.md"))
        for path in paths:
            with self.subTest(path=path.relative_to(root)):
                text = " ".join(path.read_text().split()).lower()
                self.assertNotRegex(
                    text,
                    r"default permits direct final|default direct finals|"
                    r"direct final generation is (?:permitted|allowed)|"
                    r"no compulsory draft|no mandatory.{0,70}draft-first",
                )
        contract = (root / ".agents/contracts/performance-direction.md").read_text()
        self.assertIn("in both review modes", contract)

    def setUp(self):
        fixture = prepare_fixtures.PrepareRequestTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.caps = copy.deepcopy(prepare_fixtures.CAPABILITIES)
        (self.root / "studio").mkdir()
        (self.root / fixture.prompt).write_text("A quiet held shot.\n")
        self.arguments = fixture.argv()
        while "--ref" in self.arguments:
            index = self.arguments.index("--ref")
            del self.arguments[index:index + 2]
        self.arguments += ["--schema-version", "2"]

    def mode(self, value=None):
        setting = "" if value is None else f"review_mode: {value}\n"
        (self.root / "project.md").write_text(
            f"---\napproval_mode: approve_for_me\n{setting}---\nA story.\n"
        )

    def request(self):
        return prepare_request.build_request(
            self.root, prepare_request.parser().parse_args(self.arguments)
        )

    def report(self, request):
        return {
            "schema_version": 1, "request_sha256": request["request_sha256"],
            "reviewer_status": "complete",
            "checks": [{"rule_id": "references.ordered_bindings", "status": "pass",
                        "evidence": "Synthetic fixture has no reference bindings."}],
        }

    def register(self, request, report=None, required=None):
        operation_store.prepare_operation(
            self.root, request, self.caps, report, required or []
        )

    def test_absent_and_explicit_default_allow_no_report(self):
        for mode in (None, "default"):
            with self.subTest(mode=mode):
                self.mode(mode)
                request = self.request()
                self.register(request)
                operation_store.transition_operation(
                    self.root, request["operation_id"], "prepared", "submitting"
                )
                (self.root / "task_ids.json").unlink()

    def test_strict_requires_report_and_accepts_matching_report(self):
        self.mode("strict")
        request = self.request()
        with self.assertRaisesRegex(ValueError, "review"):
            self.register(request)
        self.assertFalse((self.root / "task_ids.json").exists())
        self.register(request, self.report(request))

    def test_required_rules_and_supplied_reports_are_enforced_in_both_modes(self):
        for mode in ("default", "strict"):
            self.mode(mode)
            request = self.request()
            required = ["references.ordered_bindings"]
            report = self.report(request)
            invalid_reports = [
                None,
                {**report, "request_sha256": "0" * 64},
                {**report, "reviewer_status": "incomplete"},
                {**report, "checks": []},
            ]
            for status in ("fail", "not_applicable"):
                changed = copy.deepcopy(report)
                changed["checks"][0]["status"] = status
                invalid_reports.append(changed)
            for invalid in invalid_reports:
                with self.subTest(mode=mode, report=invalid), self.assertRaises(ValueError):
                    self.register(request, invalid, required)
                self.assertFalse((self.root / "task_ids.json").exists())
            self.register(request, report, required)
            (self.root / "task_ids.json").unlink()

    def test_optional_supplied_failure_or_stale_report_is_not_ignored(self):
        self.mode("default")
        request = self.request()
        for change in ("failure", "stale", "empty_evidence"):
            report = self.report(request)
            if change == "failure":
                report["checks"][0]["status"] = "fail"
            elif change == "stale":
                report["request_sha256"] = "0" * 64
            else:
                report["checks"][0]["evidence"] = " "
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.register(request, report)
        self.assertFalse((self.root / "task_ids.json").exists())

    def test_invalid_mode_fails_new_preparation_for_all_versions(self):
        for value in ("null", "false", "[]", "{}", "STRICT", "unknown", '""'):
            self.mode(value)
            for version in ("1", "2"):
                args = self.arguments.copy()
                args[-1] = version
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    code = prepare_request.main(args)
                with self.subTest(value=value, version=version):
                    self.assertEqual(code, 1, output.getvalue())
                    self.assertIn("review_mode", output.getvalue())

    def test_mode_is_rechecked_under_registration_lock(self):
        self.mode()
        request = self.request()
        original = operation_store.selection_lock

        @contextlib.contextmanager
        def changed_mode(root):
            with original(root):
                self.mode("strict")
                yield

        with (
            patch.object(operation_store, "selection_lock", changed_mode),
            self.assertRaises(ValueError),
        ):
            self.register(request)
        self.assertFalse((self.root / "task_ids.json").exists())

    def test_mode_change_under_submission_lock_preserves_registry(self):
        self.mode()
        request = self.request()
        self.register(request)
        before = (self.root / "task_ids.json").read_bytes()
        original = operation_store.selection_lock

        @contextlib.contextmanager
        def changed_mode(root):
            with original(root):
                self.mode("strict")
                yield

        with (
            patch.object(operation_store, "selection_lock", changed_mode),
            self.assertRaises(ValueError),
        ):
            operation_store.transition_operation(
                self.root, request["operation_id"], "prepared", "submitting"
            )
        self.assertEqual((self.root / "task_ids.json").read_bytes(), before)

    def test_version_one_cannot_bypass_explicit_review_mode(self):
        (self.root / "project.md").write_text("---\nreview_mode: strict\n---\n")
        args = self.arguments.copy()
        args[-1] = "1"
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = prepare_request.main(args)
        self.assertEqual(code, 1, output.getvalue())
        self.assertIn("version-2", output.getvalue())

    def test_pending_legacy_request_cannot_bypass_new_strict_mode(self):
        args = self.arguments.copy()
        args[-1] = "1"
        request = prepare_request.build_request(
            self.root, prepare_request.parser().parse_args(args)
        )
        self.register(request)
        before = (self.root / "task_ids.json").read_bytes()
        (self.root / "project.md").write_text("---\nreview_mode: strict\n---\n")
        with self.assertRaises(ValueError):
            operation_store.transition_operation(
                self.root, request["operation_id"], "prepared", "submitting"
            )
        self.assertEqual((self.root / "task_ids.json").read_bytes(), before)

    def test_cli_registration_and_read_only_validation_without_review(self):
        self.mode()
        args = self.arguments + [
            "--write", "--register", "--capabilities", "capabilities/seedance-2-5.json"
        ]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = prepare_request.main(args)
        self.assertEqual(code, 0, output.getvalue())
        result = json.loads(output.getvalue())
        command = [
            sys.executable, str(Path(validation.__file__)),
            "--project", str(self.root), "--request", str(self.root / result["path"]),
            "--capabilities", str(self.root / "capabilities/seedance-2-5.json"),
        ]
        checked = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        checked = subprocess.run(
            command + ["--required-rule", "references.ordered_bindings"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)

    def test_default_native_draft_keeps_capability_and_promotion_guards(self):
        self.mode("default")
        request = self.request()
        request["params"].update(resolution="480p", draft=True)
        self.caps["parameters"]["resolution"]["enum"].append("480p")
        self.caps["parameters"]["draft"] = {"type": "boolean"}
        request["request_sha256"] = validation.compute_request_hash(
            (self.root / request["prompt_file"]).read_bytes(), [],
            request["model"], request["operation"], request["params"],
            schema_version=2, approval_mode=request["approval_mode"],
            project_sha256=request["project_sha256"],
        )
        self.register(request)
        self.assertFalse((self.root / "drafts.json").exists())
        promotion = copy.deepcopy(request)
        promotion["params"]["draft_task_id"] = "unregistered"
        self.assertTrue(validation.draft_promotion_findings(self.root, promotion))
        self.assertTrue(validation.capability_findings(
            {**request, "params": {"resolution": "unsupported"}}, self.caps
        ))

    def test_cli_schema_invalid_roots_return_findings_without_tracebacks(self):
        report_path = self.root / "cli-review.json"
        for request in (None, [], "invalid", True, 1, {}):
            for report in ("omitted", "object", "null"):
                with self.subTest(request=request, report=report):
                    report_path.write_text(json.dumps({} if report == "object" else None))
                    extra = [] if report == "omitted" else ["--review", str(report_path)]
                    checked = validate_cli(self.root, request, self.caps, *extra)
                    self.assertEqual(checked.returncode, 1)
                    self.assertEqual(checked.stderr, "")
                    result = json.loads(checked.stdout)
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["findings"])
                    self.assertEqual(
                        {finding["rule_id"] for finding in result["findings"]},
                        {"schema.valid"},
                    )

    def test_cli_review_policy_remains_enforced_with_unrelated_failures(self):
        report_path = self.root / "cli-review.json"
        for failure in ("none", "prompt", "capabilities"):
            for policy in ("default", "strict", "required", "stale", "failed", "null", "valid"):
                with self.subTest(failure=failure, policy=policy):
                    self.mode("strict" if policy in ("strict", "valid") else "default")
                    request = self.request()
                    self.assertEqual(
                        validation.schema_findings(request, "generation-request.schema.json"), []
                    )
                    if failure == "prompt":
                        request["prompt_sha256"] = "0" * 64
                    capabilities = {} if failure == "capabilities" else self.caps
                    extra = []
                    if policy == "required":
                        extra = ["--required-rule", "references.ordered_bindings"]
                    elif policy in ("stale", "failed", "null", "valid"):
                        report = self.report(request)
                        if policy == "stale":
                            report["request_sha256"] = "0" * 64
                        elif policy == "failed":
                            report["checks"][0]["status"] = "fail"
                        report_path.write_text(json.dumps(None if policy == "null" else report))
                        extra = ["--review", str(report_path)]
                        if policy == "valid":
                            extra += ["--required-rule", "references.ordered_bindings"]
                    checked = validate_cli(self.root, request, capabilities, *extra)
                    expected_ok = failure == "none" and policy in ("default", "valid")
                    self.assertEqual(checked.returncode, int(not expected_ok), checked.stdout)
                    self.assertEqual(checked.stderr, "")
                    result = json.loads(checked.stdout)
                    self.assertEqual(result["ok"], expected_ok)
                    rules = {finding["rule_id"] for finding in result["findings"]}
                    expected_rules = set()
                    if failure == "prompt":
                        expected_rules.add("prompt.current_hash")
                    elif failure == "capabilities":
                        expected_rules.add("model.supported_mode")
                    if policy in ("strict", "required", "stale"):
                        expected_rules.add("review.complete_evidence")
                    elif policy == "failed":
                        expected_rules.add("references.ordered_bindings")
                    elif policy == "null":
                        expected_rules.add("schema.valid")
                    self.assertEqual(rules, expected_rules)


class ScopedReviewModeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = scoped_fixtures.ScopedLifecycleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def test_cli_malformed_v3_context_returns_schema_findings_with_active_manifest(self):
        request = self.fixture.request()
        report_path = self.root / "cli-review.json"
        for context in ([], "invalid", True, 1, None, {}):
            for report in ("omitted", "object", "null"):
                with self.subTest(context=context, report=report):
                    malformed = {**request, "context": context}
                    report_path.write_text(json.dumps(
                        self.fixture.review(request) if report == "object" else None
                    ))
                    extra = [] if report == "omitted" else ["--review", str(report_path)]
                    checked = validate_cli(
                        self.root, malformed, self.fixture.caps, "--unit", "ep001", *extra
                    )
                    self.assertEqual(checked.returncode, 1)
                    self.assertEqual(checked.stderr, "")
                    result = json.loads(checked.stdout)
                    self.assertFalse(result["ok"])
                    self.assertTrue(result["findings"])
                    self.assertEqual(
                        {finding["rule_id"] for finding in result["findings"]},
                        {"schema.valid"},
                    )
                    self.assertTrue(all(
                        finding["path"].startswith("context") for finding in result["findings"]
                    ))

    def test_absent_mode_preserves_context_v2_fingerprints(self):
        current = self.fixture.request()
        self.assertEqual(current["context"]["context_version"], 2)
        self.assertEqual(
            current["context"]["effective_sha256"],
            "6341e41ea1c2cef777f03b84f85b38509d6abd87296aea23afc00fb6dcabe398",
        )
        self.assertEqual(
            current["request_sha256"],
            "59df3f44f162d9835d5b8a9bf8ef998f3c9b7dea3f7a391a6f6141827893f1bf",
        )
        self.assertEqual(
            production_context.context_project_sha256(self.root),
            "80f22118a76f799f294318cd5c2d92e8f1351993a014804e39ff616b2373fad2",
        )
        self.assertNotIn("review_mode", production_profiles.resolve_brief({}))

    def test_shared_mode_changes_normalized_digest_and_v3_request(self):
        request = self.fixture.request()
        before = production_context.context_project_sha256(self.root)
        self.fixture.write(
            "project.md",
            "---\napproval_mode: approve_for_me\nreview_mode: strict\n---\nShared story.\n",
        )
        self.assertNotEqual(production_context.context_project_sha256(self.root), before)
        self.assertNotEqual(self.fixture.request()["request_sha256"], request["request_sha256"])
        self.assertTrue(validation.validate_request(
            self.root, request, self.fixture.caps, unit_id="ep001"
        ))

    def test_explicit_unit_override_affects_only_selected_unit(self):
        first = self.fixture.request()
        other = self.fixture.request("ep002")
        shared = production_context.context_project_sha256(self.root)
        self.fixture.write("units/ep001/unit.md", "---\nreview_mode: strict\n---\nUnit story.\n")
        strict = self.fixture.request()
        self.assertNotEqual(first["context"], strict["context"])
        self.assertEqual(other["context"], self.fixture.request("ep002")["context"])
        self.assertEqual(shared, production_context.context_project_sha256(self.root))
        with self.assertRaisesRegex(ValueError, "review"):
            operation_store.prepare_operation(
                self.root, strict, self.fixture.caps, None, [], unit_id="ep001"
            )
        operation_store.prepare_operation(
            self.root, strict, self.fixture.caps, self.fixture.review(strict), [], unit_id="ep001"
        )

    def test_unit_default_override_does_not_waive_shared_canon_strict_review(self):
        self.fixture.write("project.md", "---\nreview_mode: strict\n---\nShared story.\n")
        self.fixture.write("units/ep001/unit.md", "---\nreview_mode: default\n---\nUnit story.\n")
        request = self.fixture.request()
        operation_store.prepare_operation(
            self.root, request, self.fixture.caps, None, [], unit_id="ep001"
        )
        canon = self.fixture.request(production=True)
        with self.assertRaisesRegex(ValueError, "review"):
            operation_store.prepare_operation(
                self.root, canon, self.fixture.caps, None, [], production_scope=True
            )

    def test_profiles_validate_both_sources_without_changing_approval(self):
        for mode in ("default", "strict"):
            settings = production_profiles.resolve_brief(
                {"review_mode": mode, "approval_mode": "ask_for_approval"}
            )
            self.assertEqual(settings["review_mode"], mode)
            self.assertEqual(settings["approval_mode"], "ask_for_approval")
        self.assertNotIn("review_mode", production_profiles.resolve_brief({}))
        self.assertEqual(production_profiles.review_mode({}), "default")
        for shared, unit in (
            ({"review_mode": None}, {"review_mode": "default"}),
            ({"review_mode": "strict"}, {"review_mode": []}),
        ):
            with self.assertRaisesRegex(ValueError, "review_mode"):
                production_profiles.resolve_brief(shared, unit)


class StageReviewModeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = studio_fixtures.UnitStudioTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root

    def gate(self, mode, stage, unit_mode=None):
        text = f"---\napproval_mode: approve_for_me\nreview_mode: {mode}\n---\n"
        self.fixture.write("project.md", text)
        self.fixture.write(
            "units/ep001/unit.md",
            f"---\nreview_mode: {unit_mode}\n---\n" if unit_mode else "# Unit\n",
        )
        context = self.fixture.context()
        studio.init_studio(context)
        with (
            patch.object(studio, "status", return_value={"frames": [], "issues": []}),
            patch.object(studio, "blocking_issues", return_value=[]),
            patch.object(studio, "canon_failures", return_value=[]),
            patch.object(studio, "lock_failures", return_value=[]) as locks,
            patch.object(studio, "delivery_failures", return_value=([], None)),
            patch.object(
                studio, "run_hyperframes",
                return_value=subprocess.CompletedProcess([], 1, stdout="{}", stderr=""),
            ) as check,
        ):
            failures, evidence = studio.stage_gate(context, stage)
        return failures, evidence, check, locks

    def test_default_defers_intermediate_check_but_keeps_placed_take_and_locks(self):
        for stage in ("shot-generation", "assembly-review"):
            failures, evidence, check, locks = self.gate("default", stage)
            check.assert_not_called()
            locks.assert_called_once()
            self.assertFalse(evidence["check_ran"])
            self.assertFalse(evidence["check_ok"])
            self.assertTrue(any("no placed take" in item for item in failures))
            self.assertIsNotNone(evidence["index_sha256"])

    def test_strict_and_delivery_still_run_checks(self):
        for mode, stage in (
            ("strict", "shot-generation"), ("strict", "assembly-review"),
            ("strict", "delivery"), ("default", "delivery"),
        ):
            failures, evidence, check, _ = self.gate(mode, stage)
            check.assert_called_once()
            self.assertTrue(evidence["check_ran"])
            self.assertFalse(evidence["check_ok"])
            self.assertIn("hyperframes check failed", failures)

    def test_unit_override_controls_intermediate_checks(self):
        for shared, unit, ran in (("strict", "default", False), ("default", "strict", True)):
            _, evidence, check, _ = self.gate(shared, "shot-generation", unit)
            self.assertEqual(check.called, ran)
            self.assertEqual(evidence["check_ran"], ran)

    def test_invalid_legacy_mode_fails_without_running_check(self):
        self.fixture.write("production.json", "{}")
        (self.root / "production.json").unlink()
        self.fixture.write("project.md", "---\nreview_mode: invalid\n---\n")
        studio.init_studio(self.root)
        with patch.object(studio, "run_hyperframes") as check:
            failures, evidence = studio.stage_gate(self.root, "shot-generation")
        self.assertTrue(any("review_mode" in item for item in failures), failures)
        check.assert_not_called()
        self.assertFalse(evidence["check_ran"])
        self.assertFalse(evidence["check_ok"])


if __name__ == "__main__":
    unittest.main()
