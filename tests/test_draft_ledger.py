import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))
import draft_ledger as ledger


def task(operation_id, params, provider_task_id=None):
    return {
        "operation_id": operation_id,
        "params": params,
        "provider_task_id": provider_task_id,
        "prompt_sha256": "a" * 64,
        "request_sha256": "b" * 64,
    }


class DraftLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.write_registry(
            [
                task("op-draft", {"draft": True, "resolution": "480p"}, "cgt-1"),
                task("op-plain", {"resolution": "480p"}, "cgt-2"),
                task("op-final", {"draft_task_id": "cgt-1", "resolution": "1080p"}),
                task("op-other-final", {"draft_task_id": "cgt-9"}),
            ]
        )

    def write_registry(self, tasks):
        (self.project / "task_ids.json").write_text(
            json.dumps({"schema_version": 1, "tasks": tasks})
        )

    def record(self, **overrides):
        values = {
            "project": self.project,
            "asset": "s01_sh010",
            "operation_id": "op-draft",
            "draft_task_id": "cgt-1",
            "submitted": date(2026, 10, 1),
        }
        values.update(overrides)
        return ledger.record_draft(**values)

    def test_record_sets_seven_day_expiry_and_copies_hashes(self):
        entry = self.record()
        self.assertEqual(entry["expires"], "2026-10-08")
        self.assertEqual(entry["status"], "drafted")
        self.assertEqual(entry["prompt_sha256"], "a" * 64)
        self.assertEqual(
            json.loads((self.project / "drafts.json").read_text())["drafts"][0][
                "draft_task_id"
            ],
            "cgt-1",
        )

    def test_recording_twice_updates_one_entry(self):
        self.record()
        self.record(take="takes/s01_sh010_t01_v01.mp4", status="approved")
        drafts = ledger.read_ledger(self.project)["drafts"]
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["status"], "approved")
        self.assertEqual(drafts[0]["take"], "takes/s01_sh010_t01_v01.mp4")

    def test_operation_must_be_a_registered_draft(self):
        with self.assertRaises(ValueError):
            self.record(operation_id="missing")
        with self.assertRaises(ValueError):
            self.record(operation_id="op-plain", draft_task_id="cgt-2")

    def test_draft_task_id_must_match_the_registered_provider_task(self):
        with self.assertRaises(ValueError):
            self.record(draft_task_id="cgt-other")

    def test_blank_draft_task_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.record(draft_task_id="  ")

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValueError):
            self.record(status="done")

    def test_final_operation_marks_promoted_and_must_reference_the_draft(self):
        self.record()
        with self.assertRaises(ValueError):
            self.record(final_operation_id="op-other-final")
        entry = self.record(final_operation_id="op-final")
        self.assertEqual(entry["status"], "promoted")
        self.assertEqual(entry["final_operation_id"], "op-final")

    def test_report_flags_expiring_and_expired_drafts_but_not_promoted(self):
        self.record(submitted=date(2026, 10, 1))
        rows = ledger.report(self.project, date(2026, 10, 7))
        self.assertEqual(rows[0]["days_left"], 1)
        self.assertTrue(rows[0]["expiring_soon"])
        rows = ledger.report(self.project, date(2026, 10, 9))
        self.assertEqual(rows[0]["status"], "expired")
        self.record(final_operation_id="op-final")
        rows = ledger.report(self.project, date(2026, 10, 9))
        self.assertEqual(rows[0]["status"], "promoted")
        self.assertFalse(rows[0]["expiring_soon"])

    def test_corrupt_ledger_is_reported_not_overwritten(self):
        (self.project / "drafts.json").write_text('{"schema_version": 2}')
        with self.assertRaises(ValueError):
            self.record()
        self.assertEqual(
            (self.project / "drafts.json").read_text(), '{"schema_version": 2}'
        )

    def test_cli_list_exit_code_signals_expiring_drafts(self):
        self.record(submitted=date(2026, 10, 1))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = ledger.main(["list", str(self.project), "--today", "2026-10-07"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())[0]["asset"], "s01_sh010")
        with contextlib.redirect_stdout(io.StringIO()):
            code = ledger.main(["list", str(self.project), "--today", "2026-10-02"])
        self.assertEqual(code, 0)

    def test_cli_record_reports_errors_with_nonzero_exit(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            code = ledger.main(
                [
                    "record",
                    str(self.project),
                    "--asset",
                    "s01_sh010",
                    "--operation-id",
                    "missing",
                    "--draft-task-id",
                    "cgt-1",
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("not in task_ids.json", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
