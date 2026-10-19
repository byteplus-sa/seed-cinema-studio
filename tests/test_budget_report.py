from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import test_scoped_lifecycle as fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import budget_report
import operation_store
import prepare_request


class BudgetReportTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ScopedLifecycleTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root, self.write = fixture.root, fixture.write
        self.write("units/ep002/studio/index.html", "<html></html>")
        self.write("units/ep002/studio/hyperframes.json", "{}")

    def budget(self, cap=100, unit_cap=None, currency="USD"):
        self.write("project.md", "---\napproval_mode: approve_for_me\n"
                   f"budget:\n  cap: {cap}\n  currency: {currency}\n---\nShared story.\n")
        if unit_cap is not None:
            self.write("units/ep001/unit.md", f"---\nunit_budget:\n  cap: {unit_cap}\n---\nStory.\n")

    def request(self, unit="ep001", estimate=None):
        request = self.fixture.request(unit)
        request["cost"]["estimated"] = estimate
        return request

    def register(self, request):
        self.fixture.register(request, unit=request["context"]["unit_id"])

    def test_report_aggregates_units_and_keeps_uncertain_reservations(self):
        self.budget()
        first, second = self.request(estimate=20), self.request("ep002", 30)
        first.update(submission_status="terminal", provider_status="succeeded",
                     provider_task_id="first")
        first["cost"]["confirmed"] = 15
        second.update(submission_status="submission_unknown")
        canon = self.fixture.request(production=True)
        canon["operation_id"] = canon["asset_id"] = "canon"
        canon["cost"]["estimated"] = 5
        tasks = [first, second, canon]
        before = copy.deepcopy(tasks)
        report = budget_report.budget_report(self.root, tasks)
        totals = report["production"]["currencies"]["USD"]
        self.assertEqual(totals["estimated"], 55)
        self.assertEqual(totals["confirmed"], 15)
        self.assertEqual(totals["reserved"], 35)
        self.assertEqual(totals["exposure"], 50)
        self.assertEqual(totals["unknown_operations"], [])
        self.assertEqual(report["units"]["ep002"]["currencies"]["USD"]["reserved"], 30)
        self.assertEqual(tasks, before)

    def test_unknown_is_not_zero_and_failed_provider_is_not_a_refund(self):
        first, second = self.request(estimate=None), self.request("ep002", 10)
        second.update(submission_status="terminal", provider_status="failed", provider_task_id="failed")
        totals = budget_report.budget_report(self.root, [first, second])["production"]["currencies"]["USD"]
        self.assertIsNone(totals["exposure"])
        self.assertEqual(totals["unknown_operations"], [first["operation_id"]])
        self.assertEqual(totals["reserved"], 10)
        second["cost"]["confirmed"] = 0
        totals = budget_report.budget_report(self.root, [second])["production"]["currencies"]["USD"]
        self.assertEqual(totals["exposure"], 0)

    def test_cap_requires_estimate_and_preserves_no_budget_cases(self):
        request = self.request()
        self.register(request)
        self.assertEqual(len(operation_store.read_registry(self.root / "task_ids.json")["tasks"]), 1)
        self.budget()
        request = self.request("ep002")
        before = (self.root / "task_ids.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "estimate|unknown"):
            self.register(request)
        self.assertEqual((self.root / "task_ids.json").read_bytes(), before)

    def test_shared_and_tighter_unit_caps_are_enforced(self):
        self.budget(cap=100, unit_cap=20)
        with self.assertRaisesRegex(ValueError, "ep001"):
            self.register(self.request(estimate=21))
        self.assertFalse((self.root / "task_ids.json").exists())
        self.register(self.request(estimate=20))
        with self.assertRaisesRegex(ValueError, "production"):
            self.register(self.request("ep002", 81))
        self.register(self.request("ep002", 80))

    def test_prepared_and_unknown_tasks_reserve_budget_concurrently(self):
        self.budget(cap=10)
        requests = [self.request(unit, 7) for unit in ("ep001", "ep002")]

        def attempt(request):
            try:
                self.register(request)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(sorted(workers.map(attempt, requests)), [False, True])
        task = operation_store.read_registry(self.root / "task_ids.json")["tasks"][0]
        operation_store.transition_operation(self.root, task["operation_id"], "prepared", "submitting")
        operation_store.transition_operation(self.root, task["operation_id"], "submitting", "submission_unknown")
        other = next(request for request in requests if request["operation_id"] != task["operation_id"])
        with self.assertRaises(ValueError):
            self.register(other)

    def test_submitting_rechecks_current_shared_spending_without_double_counting(self):
        self.budget(cap=10)
        first, second = self.request(estimate=5), self.request("ep002", 5)
        self.register(first)
        self.register(second)
        registry = operation_store.read_registry(self.root / "task_ids.json")
        registry["tasks"][1]["cost"]["confirmed"] = 8
        operation_store.replace_registry(self.root / "task_ids.json", registry)
        before = (self.root / "task_ids.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "cap"):
            operation_store.transition_operation(self.root, first["operation_id"], "prepared", "submitting")
        self.assertEqual((self.root / "task_ids.json").read_bytes(), before)

    def test_stale_review_snapshot_cannot_erase_confirmed_billing(self):
        self.budget(cap=10)
        request = self.request(estimate=5)
        self.fixture.complete(request, "known")
        path = self.root / "task_ids.json"
        billing, review = operation_store.read_registry(path), operation_store.read_registry(path)
        billing["tasks"][0]["cost"]["confirmed"] = 10
        operation_store.replace_registry(path, billing)
        before = path.read_bytes()
        review["tasks"][0]["review_status"] = "rejected"
        with self.assertRaisesRegex(ValueError, "[Ss]tale|revision"):
            operation_store.replace_registry(path, review)
        self.assertEqual(path.read_bytes(), before)
        totals = budget_report.budget_report(self.root)["production"]["currencies"]["USD"]
        self.assertEqual(totals["confirmed"], 10)
        with self.assertRaisesRegex(ValueError, "cap"):
            self.register(self.request("ep002", 1))
        fresh = operation_store.read_registry(path)
        fresh["tasks"][0]["review_status"] = "rejected"
        operation_store.replace_registry(path, fresh)
        self.assertEqual(operation_store.read_registry(path)["tasks"][0]["cost"]["confirmed"], 10)

    def test_stale_never_submitted_cancellation_releases_reservation_without_rebinding(self):
        self.budget(cap=10)
        request = self.request(estimate=10)
        self.register(request)
        self.write("units/ep001/unit.md", "Revised before any submission.")
        path = self.root / "task_ids.json"
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            operation_store.transition_operation(
                self.root, request["operation_id"], "prepared", "submitting")
        self.assertEqual(path.read_bytes(), before)
        operation_store.transition_operation(
            self.root, request["operation_id"], "prepared", "terminal",
            provider_status="cancelled_before_submission")
        stored = operation_store.read_registry(path)["tasks"][0]
        expected = copy.deepcopy(request)
        expected.update(submission_status="terminal", provider_status="cancelled_before_submission")
        self.assertEqual(stored, expected)
        totals = budget_report.budget_report(self.root)["production"]["currencies"]["USD"]
        self.assertEqual(totals["estimated"], 10)
        self.assertEqual(totals["reserved"], 0)
        self.assertEqual(totals["exposure"], 0)
        self.assertIsNone(stored["cost"]["confirmed"])
        self.register(self.request("ep002", 10))
        with self.assertRaises(ValueError):
            operation_store.transition_operation(
                self.root, request["operation_id"], "terminal", "submitting")

    def test_cancellation_rejects_any_submission_or_billing_evidence(self):
        self.budget(cap=10)
        request = self.request(estimate=10)
        self.register(request)
        cases = [
            {"submission_status": "submitting"},
            {"submission_status": "submission_unknown"},
            {"submission_status": "acknowledged", "provider_task_id": "known"},
            {"submission_status": "terminal", "provider_status": "failed"},
            {"provider_task_id": "known"},
            {"provider_task_id": ""},
            {"provider_status": "running"},
            {"review_status": "review"},
            {"cost": {**request["cost"], "confirmed": 0}},
            {"cost": {**request["cost"], "usage": {}}},
        ]
        path = self.root / "task_ids.json"
        for changes in cases:
            with self.subTest(changes=changes):
                record = {**request, **changes}
                self.write("task_ids.json", json.dumps({"schema_version": 1, "tasks": [record]}))
                before = path.read_bytes()
                with self.assertRaises(ValueError):
                    operation_store.transition_operation(
                        self.root, request["operation_id"], record["submission_status"], "terminal",
                        provider_status="cancelled_before_submission")
                self.assertEqual(path.read_bytes(), before)
                replacement = operation_store.read_registry(path)
                replacement["tasks"][0].update(
                    submission_status="terminal", provider_status="cancelled_before_submission")
                with self.assertRaises(ValueError):
                    operation_store.replace_registry(path, replacement)
                self.assertEqual(path.read_bytes(), before)
                totals = budget_report.budget_report(self.root)["production"]["currencies"]["USD"]
                self.assertEqual(totals["reserved"], 10)

    def test_prepared_closure_requires_explicit_cancellation_without_a_provider_id(self):
        self.register(self.request(estimate=10))
        path = self.root / "task_ids.json"
        before = path.read_bytes()
        for values in (
            {},
            {"provider_status": "failed"},
            {"provider_status": "cancelled_before_submission", "provider_task_id": "known"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                operation_store.transition_operation(
                    self.root, "ep001-draft", "prepared", "terminal", **values)
            self.assertEqual(path.read_bytes(), before)

    def test_cancellation_with_missing_estimate_releases_unknown_exposure_only(self):
        request = self.request()
        self.register(request)
        operation_store.transition_operation(
            self.root, request["operation_id"], "prepared", "terminal",
            provider_status="cancelled_before_submission")
        self.budget(cap=10)
        totals = budget_report.budget_report(self.root)["production"]["currencies"]["USD"]
        self.assertEqual(totals["exposure"], 0)
        self.assertEqual(totals["unknown_operations"], [])
        self.assertEqual(totals["missing_estimates"], [request["operation_id"]])
        self.register(self.request("ep002", 10))

    def test_provider_cancelled_or_uncertain_tasks_keep_reservations(self):
        request = self.request(estimate=10)
        for changes in (
            {"submission_status": "terminal", "provider_status": "cancelled"},
            {"submission_status": "submission_unknown"},
            {"submission_status": "terminal", "provider_status": "cancelled_before_submission",
             "provider_task_id": "known"},
        ):
            with self.subTest(changes=changes):
                totals = budget_report.currency_totals([{**request, **changes}])["USD"]
                self.assertEqual(totals["reserved"], 10)

    def test_cancellation_and_submission_race_has_only_one_winner(self):
        self.budget(cap=10)
        request = self.request(estimate=10)
        self.register(request)
        barrier = Barrier(2)

        def attempt(status):
            barrier.wait(timeout=5)
            try:
                operation_store.transition_operation(
                    self.root, request["operation_id"], "prepared", status,
                    provider_status="cancelled_before_submission" if status == "terminal" else None)
                return status
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(attempt, ("terminal", "submitting")))
        winners = [value for value in results if value is not None]
        self.assertEqual(len(winners), 1)
        stored = operation_store.read_registry(self.root / "task_ids.json")["tasks"][0]
        self.assertEqual(stored["submission_status"], winners[0])
        totals = budget_report.budget_report(self.root)["production"]["currencies"]["USD"]
        self.assertEqual(totals["reserved"], 0 if winners[0] == "terminal" else 10)

    def test_adoption_records_existing_spend_even_when_over_cap(self):
        self.budget(cap=0)
        request = self.request(estimate=10)
        operation_store.adopt_submitted_operation(
            self.root, request, self.fixture.caps, self.fixture.review(request),
            ["fixture"], "already-submitted", "succeeded", True, unit_id="ep001")
        record = operation_store.read_registry(self.root / "task_ids.json")["tasks"][0]
        self.assertEqual(record["provider_task_id"], "already-submitted")
        self.assertEqual(record["submission_status"], "terminal")
        totals = budget_report.budget_report(self.root)["production"]["currencies"]["USD"]
        self.assertEqual(totals["reserved"], 10)

    def test_currency_mismatch_and_nonfinite_estimates_fail_closed(self):
        self.budget()
        for estimate, currency in ((10, "EUR"), (float("inf"), "USD"), (float("nan"), "USD")):
            with self.subTest(estimate=estimate, currency=currency):
                request = self.request(estimate=estimate)
                request["cost"]["currency"] = currency
                with self.assertRaises(ValueError):
                    self.register(request)
                self.assertFalse((self.root / "task_ids.json").exists())

    def test_report_cli_is_read_only_and_keeps_currencies_separate(self):
        first, second = self.request(estimate=2), self.request("ep002", 3)
        second["cost"]["currency"] = "EUR"
        self.write("task_ids.json", json.dumps({"schema_version": 1, "tasks": [first, second]}))
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        result = subprocess.run(
            [sys.executable, str(Path(budget_report.__file__)), str(self.root)],
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        currencies = json.loads(result.stdout)["production"]["currencies"]
        self.assertEqual(currencies["USD"]["exposure"], 2)
        self.assertEqual(currencies["EUR"]["exposure"], 3)
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()})

    def test_preparation_cli_accepts_estimate_and_blocks_over_cap_before_writing(self):
        self.budget(cap=10)
        command = [
            sys.executable, str(Path(prepare_request.__file__)),
            "--project", str(self.root), "--unit", "ep001",
            "--asset", "cli-draft", "--model", "seedance-2-5",
            "--operation", "generate", "--prompt", "scenes/scene-001/prompt.md",
            "--expected-output", "scenes/scene-001/cli.mp4", "--write",
        ]
        for estimate in (None, "11"):
            arguments = command + (["--estimated-cost", estimate] if estimate else [])
            result = subprocess.run(arguments, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse((self.root / "requests/request_cli-draft.json").exists())
        result = subprocess.run(command + ["--estimated-cost", "10", "--currency", "USD"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        request = json.loads((self.root / "requests/request_cli-draft.json").read_text())
        self.assertEqual(request["cost"], {"estimated": 10, "confirmed": None, "currency": "USD"})

    def test_zero_cap_accepts_explicit_zero_but_not_missing_estimate(self):
        self.budget(cap=0)
        with self.assertRaises(ValueError):
            self.register(self.request())
        self.register(self.request(estimate=0))

    def test_decimal_boundary_does_not_round_up_and_partial_billing_retains_reservation(self):
        self.budget(cap=0.3)
        first, second = self.request(estimate=0.1), self.request("ep002", 0.2)
        self.register(first)
        self.register(second)
        first.update(submission_status="submission_unknown")
        first["cost"]["confirmed"] = 0.03
        totals = budget_report.budget_report(self.root, [first])["production"]["currencies"]["USD"]
        self.assertEqual(totals["confirmed"], 0.03)
        self.assertEqual(totals["reserved"], 0.07)
        self.assertEqual(totals["exposure"], 0.1)

    def test_missing_currency_and_unknown_existing_exposure_block_capped_scope(self):
        request = self.request()
        self.register(request)
        self.budget()
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.register(self.request("ep002", 1))
        self.write("project.md", "---\napproval_mode: approve_for_me\nbudget:\n  cap: 100\n---\nShared story.\n")
        with self.assertRaisesRegex(ValueError, "currency"):
            self.register(self.request("ep002", 1))

    def test_large_integer_cap_is_compared_without_float_rounding(self):
        self.budget(cap=9007199254740992)
        with self.assertRaisesRegex(ValueError, "cap"):
            self.register(self.request(estimate=9007199254740993))
        self.assertFalse((self.root / "task_ids.json").exists())
        self.register(self.request(estimate=9007199254740992))
        with self.assertRaisesRegex(ValueError, "cap"):
            self.register(self.request("ep002", 0.1))


if __name__ == "__main__":
    unittest.main()
