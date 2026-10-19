from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import deliverables
import studio_project as studio
import test_unit_studio as unit_fixtures


class DeliverableTests(unittest.TestCase):
    approval_mode = "approve_for_me"
    actor = "agent"

    def setUp(self):
        self.fixture = unit_fixtures.UnitStudioTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.write = self.fixture.write
        project = self.root / "project.md"
        project.write_text(project.read_text().replace("approve_for_me", self.approval_mode))
        self.spec = {
            "schema_version": 1, "id": "ep001-en-master", "unit_id": "ep001",
            "cut_id": "main", "kind": "master", "language": "en",
            "spec": {
                "width": 1920, "height": 1080, "fps": "25/1",
                "audio": {"required": False}, "subtitles": [],
            },
        }
        self.add_delivery(self.spec)
        self.context = self.fixture.context()
        self.stream_patch = patch.object(
            studio.selection_service(), "probe_media_streams", return_value={"video"},
        )
        self.stream_patch.start()
        self.addCleanup(self.stream_patch.stop)
        self.fixture.select_shots(self.context, self.actor)
        self.media = {
            "duration_s": 4.0,
            "streams": [{"codec_type": "video", "width": 1920, "height": 1080,
                         "r_frame_rate": "25/1"}],
        }
        self.probe_patch = patch.object(deliverables, "probe_media", return_value=self.media)
        self.decode_patch = patch.object(deliverables, "verify_decode")
        self.probe = self.probe_patch.start()
        self.decode = self.decode_patch.start()
        self.addCleanup(self.probe_patch.stop)
        self.addCleanup(self.decode_patch.stop)
        self.record = studio.render(self.context, "master", "delivery", self.fixture.runner)

    def add_delivery(self, spec):
        self.write(f"deliverables/{spec['id']}.json", json.dumps(spec))
        self.fixture.manifest["deliverables"].append({
            "id": spec["id"], "unit_id": spec["unit_id"],
            "manifest": f"deliverables/{spec['id']}.json",
        })
        self.write("production.json", json.dumps(self.fixture.manifest))

    def status(self, identifier="ep001-en-master"):
        return deliverables.status(self.root, identifier)

    def bind(self, identifier="ep001-en-master", record=None, revision=None):
        return deliverables.bind(
            self.root, identifier, record or self.record,
            expected_revision=revision or self.status(identifier)["revision"],
        )

    def prepare_stages(self):
        service = studio.selection_service()
        with patch.object(service, "probe_media_streams", return_value={"video"}):
            for stage in studio.STAGES:
                if stage == "delivery":
                    studio.start_stage(self.context, stage)
                    break
                if stage in studio.OPTIONAL_STAGES:
                    studio.skip_stage(self.context, stage, "Synthetic wordless fixture")
                    continue
                studio.start_stage(self.context, stage)
                if stage == "assembly-review":
                    output = json.loads(self.record.read_text())["output"]["path"]
                    studio.record_lock(self.context, self.fixture.decision(
                        self.context, output, "picture", kind="picture", actor=self.actor,
                    ))
                studio.complete_stage(self.context, stage, self.fixture.runner)

    def decision(self, identifier="ep001-en-master", actor=None, name="final-choice"):
        state = self.status(identifier)
        version = json.loads((self.root / state["binding"]["path"]).read_text())
        decision = self.fixture.decision(
            self.fixture.context(self.spec["unit_id"]),
            version["output"]["path"], name, kind="final_master", actor=actor or self.actor,
        )
        decision["upstream_sha256"][state["binding"]["path"]] = state["binding"]["sha256"]
        return decision

    def lock(self, identifier="ep001-en-master", decision=None):
        return deliverables.lock(
            self.root, identifier, decision or self.decision(identifier),
            expected_revision=self.status(identifier)["revision"], runner=self.fixture.runner,
        )

    def test_explicit_binding_does_not_pick_newest_render(self):
        newer = studio.render(self.context, "newer", "delivery", self.fixture.runner)
        result = self.bind()
        version = json.loads((self.root / result["binding"]["path"]).read_text())
        self.assertEqual(version["render_record"]["path"], self.record.relative_to(self.root).as_posix())
        self.assertNotEqual(version["render_record"]["path"], newer.relative_to(self.root).as_posix())
        self.decode.assert_called_once()
        self.assertEqual(version["media"], self.media)
        self.assertIsNone(result["lock"])

    def test_unknown_id_and_alternate_cut_rejected_without_binding(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.bind("unknown")
        path = self.root / "deliverables/ep001-en-master.json"
        for field, value in (("cut_id", "trailer"), ("unit_id", "ep002")):
            spec = {**self.spec, field: value}
            path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError):
                self.bind()
        self.assertFalse(list(path.parent.glob("*.v*.json")))

    def test_wrong_unit_missing_output_and_manual_render_fail(self):
        second = self.fixture.context("ep002")
        self.fixture.select_shots(second)
        foreign = studio.render(second, "foreign", "delivery", self.fixture.runner)
        with self.assertRaises(ValueError):
            self.bind(record=foreign)
        record = json.loads(self.record.read_text())
        record["produced_by"] = "manual"
        self.record.write_text(json.dumps(record))
        with self.assertRaises(ValueError):
            self.bind()
        record["produced_by"] = "render"
        self.record.write_text(json.dumps(record))
        (self.root / record["output"]["path"]).unlink()
        with self.assertRaises(ValueError):
            self.bind()

    def test_probe_spec_and_decode_failures_never_commit(self):
        before = (self.root / "deliverables/ep001-en-master.json").read_bytes()
        for field, value in (("width", 1280), ("height", 720), ("r_frame_rate", "24/1")):
            with self.subTest(field=field):
                media = copy.deepcopy(self.media)
                media["streams"][0][field] = value
                self.probe.return_value = media
                with self.assertRaises(ValueError):
                    self.bind()
                self.assertEqual((self.root / "deliverables/ep001-en-master.json").read_bytes(), before)
        self.probe.return_value = self.media
        self.decode.side_effect = ValueError("decode failed")
        with self.assertRaisesRegex(ValueError, "decode"):
            self.bind()

    def test_expected_revision_and_parallel_bind_are_serialized(self):
        revision = self.status()["revision"]
        def bind_once(_):
            try:
                return self.bind(revision=revision)
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(bind_once, range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(len(self.status()["versions"]), 1)
        with self.assertRaisesRegex(ValueError, "revision"):
            self.bind(revision=revision)

    def test_binding_history_is_immutable_and_artifact_not_overwritten(self):
        first = self.bind()
        path = self.root / first["binding"]["path"]
        snapshot = path.read_bytes()
        second = self.bind()
        self.assertEqual(path.read_bytes(), snapshot)
        self.assertEqual(len(second["versions"]), 2)
        self.assertNotEqual(first["binding"]["path"], second["binding"]["path"])
        path.write_text("{}")
        self.assertTrue(self.status()["findings"])
        with self.assertRaises(ValueError):
            self.bind()

    def test_source_drift_preserves_history_and_unrelated_episode_does_not_stale(self):
        bound = self.bind()
        version_path = self.root / bound["binding"]["path"]
        before = version_path.read_bytes()
        self.write("units/ep002/unit.md", "# Changed unrelated episode\n")
        self.assertFalse(self.status()["findings"])
        self.write("units/ep001/unit.md", "# Changed selected episode\n")
        state = self.status()
        self.assertTrue(state["findings"])
        self.assertEqual(state["binding"], bound["binding"])
        self.assertEqual(version_path.read_bytes(), before)

    def test_output_record_and_tree_drift_are_reported(self):
        self.bind()
        output = self.root / json.loads(self.record.read_text())["output"]["path"]
        for path in (output, self.record, self.context.studio_root / "index.html"):
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            self.assertTrue(self.status()["findings"], path)
            path.write_bytes(original)
            self.assertFalse(self.status()["findings"], path)

    def test_lock_requires_full_prerequisites_and_v2_final_master_decision(self):
        self.bind()
        with self.assertRaises(ValueError):
            self.lock()
        self.prepare_stages()
        for field, value in (("schema_version", 1), ("lock_kind", "picture"),
                             ("context", self.fixture.context("ep002").identity()),
                             ("result", "rejected")):
            decision = self.decision()
            decision[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.lock(decision=decision)
        result = self.lock()
        self.assertIsNotNone(result["lock"])
        self.assertNotIn("final_master", studio.stage_entry(
            studio.read_stages(self.context), "delivery").get("locks", {}))

    def test_required_stage_cannot_be_marked_skipped_to_lock_delivery(self):
        self.prepare_stages()
        self.bind()
        ledger = studio.read_stages(self.context)
        stage = studio.stage_entry(ledger, "scene-breakdown")
        stage.update(status="skipped", reason="Invalid required-stage bypass")
        studio.write_stages(self.context, ledger)
        with self.assertRaisesRegex(ValueError, "skipped|required"):
            self.lock()

    def test_proxy_language_and_episode_never_displace_locked_master(self):
        self.prepare_stages()
        self.bind()
        locked = self.lock()
        before = (self.root / "deliverables/ep001-en-master.json").read_bytes()
        for identifier, kind, language, unit in (
            ("ep001-proxy", "proxy", "en", "ep001"),
            ("ep001-fr-master", "master", "fr", "ep001"),
            ("ep002-en-master", "master", "en", "ep002"),
        ):
            spec = {**self.spec, "id": identifier, "kind": kind, "language": language, "unit_id": unit}
            self.add_delivery(spec)
            record = self.record
            if unit == "ep002":
                second = self.fixture.context(unit)
                self.fixture.select_shots(second)
                record = studio.render(second, "other", "delivery", self.fixture.runner)
            self.bind(identifier, record)
            self.assertEqual((self.root / "deliverables/ep001-en-master.json").read_bytes(), before)
        self.assertEqual(self.status()["lock"], locked["lock"])
        self.assertFalse(self.status()["findings"])

    def test_new_binding_keeps_old_lock_and_agent_cannot_replace_user_lock(self):
        self.prepare_stages()
        self.bind()
        locked = self.lock(decision=self.decision(actor="user"))
        old_lock = (self.root / locked["lock"]["path"]).read_bytes()
        bound = self.bind()
        self.assertEqual(bound["lock"], locked["lock"])
        with self.assertRaisesRegex(ValueError, "user"):
            self.lock(decision=self.decision(name="new-agent-choice"))
        self.assertEqual((self.root / locked["lock"]["path"]).read_bytes(), old_lock)

    def test_changed_review_or_authorization_stales_lock_without_erasing_it(self):
        self.prepare_stages()
        self.bind()
        decision = self.decision()
        locked = self.lock(decision=decision)
        review = self.root / decision["review_path"]
        review.write_text(review.read_text() + "\n")
        self.assertTrue(self.status()["findings"])
        self.assertEqual(self.status()["lock"], locked["lock"])

    def test_subtitles_are_bound_and_audio_requirements_are_checked(self):
        spec = copy.deepcopy(self.spec)
        spec["spec"]["audio"] = {"required": True, "channels": 2, "sample_rate": 48000}
        spec["spec"]["subtitles"] = [{
            "language": "en", "mode": "sidecar", "path": "subtitles/master.en.srt",
        }]
        self.write("deliverables/ep001-en-master.json", json.dumps(spec))
        self.write("subtitles/master.en.srt", "1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        with self.assertRaises(ValueError):
            self.bind()
        self.media["streams"].append({
            "codec_type": "audio", "channels": 2, "sample_rate": "48000",
        })
        record = json.loads(self.record.read_text())
        record["output"]["probe"] = self.media
        self.record.write_text(json.dumps(record))
        self.bind()
        self.write("subtitles/master.en.srt", "Changed\n")
        self.assertTrue(self.status()["findings"])

    def test_cli_status_and_validate_are_read_only(self):
        output = io.StringIO()
        before = (self.root / "deliverables/ep001-en-master.json").read_bytes()
        for command in ("validate", "status"):
            with contextlib.redirect_stdout(output):
                self.assertEqual(deliverables.main([command, str(self.root), self.spec["id"]]), 0)
        self.assertEqual((self.root / "deliverables/ep001-en-master.json").read_bytes(), before)

    def test_decode_command_uses_full_audio_video_decode_and_fails_closed(self):
        self.probe_patch.stop()
        self.decode_patch.stop()
        runner = unittest.mock.Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        deliverables.verify_decode(self.root / "video.mp4", runner=runner)
        arguments = runner.call_args.args[0]
        self.assertIn("-xerror", arguments)
        self.assertIn("0:v", arguments)
        self.assertIn("0:a?", arguments)
        runner.return_value = subprocess.CompletedProcess([], 1, "", "bad media")
        with self.assertRaises(ValueError):
            deliverables.verify_decode(self.root / "video.mp4", runner=runner)

    def test_changed_approval_mode_and_missing_review_block_lock(self):
        self.prepare_stages()
        self.bind()
        decision = self.decision()
        (self.root / decision["review_path"]).unlink()
        with self.assertRaises(ValueError):
            self.lock(decision=decision)
        decision = self.decision()
        project = self.root / "project.md"
        project.write_text(project.read_text().replace("approve_for_me", "ask_for_approval"))
        with self.assertRaises(ValueError):
            self.lock(decision=decision)
        self.assertIsNone(self.status()["lock"])

    def test_symlinks_and_traversal_are_rejected(self):
        alias = self.write("alias.json", "{}")
        alias.unlink()
        alias.symlink_to(self.record)
        for record in ("../outside.json", alias):
            with self.subTest(record=record), self.assertRaises(ValueError):
                self.bind(record=record)
        manifest = self.root / "deliverables/ep001-en-master.json"
        contents = manifest.read_text()
        manifest.unlink()
        other = self.write("original.json", contents)
        manifest.symlink_to(other)
        with self.assertRaises(ValueError):
            self.bind()

    def test_interrupted_commit_retains_journal_and_recovers_without_overwriting(self):
        revision = self.status()["revision"]
        service = studio.selection_service()
        recover = service.recover_selection
        calls = 0
        def interrupted(root):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Synthetic interrupted commit")
            return recover(root)
        with (
            patch.object(service, "recover_selection", side_effect=interrupted),
            self.assertRaises(ValueError),
        ):
            self.bind(revision=revision)
        self.assertTrue((self.root / ".selection-journal.json").exists())
        with self.assertRaisesRegex(ValueError, "revision"):
            self.bind(revision=revision)
        self.assertFalse((self.root / ".selection-journal.json").exists())
        self.assertEqual(len(self.status()["versions"]), 1)

    def test_binding_rejects_source_change_during_decode(self):
        before = (self.root / "deliverables/ep001-en-master.json").read_bytes()
        self.decode.side_effect = lambda *args: self.write(
            "units/ep001/unit.md", "# Concurrent source edit\n",
        )
        with self.assertRaises(ValueError):
            self.bind()
        self.assertEqual((self.root / "deliverables/ep001-en-master.json").read_bytes(), before)

    def test_existing_version_filename_is_never_overwritten(self):
        existing = self.write("deliverables/ep001-en-master.v000001.json", "Preserve me")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.bind()
        self.assertEqual(existing.read_text(), "Preserve me")

    def test_rebound_current_output_reports_old_version_as_history_only(self):
        first = self.bind()
        index = self.context.studio_root / "index.html"
        index.write_text(index.read_text() + "\n<!-- Revised edit -->\n")
        record = studio.render(self.context, "revised", "delivery", self.fixture.runner)
        second = self.bind(record=record)
        self.assertTrue(second["ok"])
        self.assertTrue(second["history_findings"])
        self.assertEqual(second["versions"][0], first["binding"])


@unittest.skipUnless(os.environ.get("DELIVERABLES_MEDIA_SMOKE") == "1",
                     "Set DELIVERABLES_MEDIA_SMOKE=1 for real FFmpeg decode")
class DeliverableMediaSmokeTests(unittest.TestCase):
    def test_real_media_probe_decode_and_truncated_output_rejection(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("FFmpeg and ffprobe are required")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "smoke.mp4"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                 "color=c=black:s=320x180:r=24:d=0.25", "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", str(output)],
                check=True, capture_output=True, timeout=30,
            )
            media = deliverables.probe_media(output)
            self.assertGreater(media["duration_s"], 0)
            self.assertEqual(media["streams"][0]["width"], 320)
            deliverables.verify_decode(output)
            output.write_bytes(output.read_bytes()[:100])
            with self.assertRaises(ValueError):
                deliverables.verify_decode(output)


class DeliverableProbeTests(unittest.TestCase):
    def test_malformed_streams_fail_with_validation_error(self):
        runner = unittest.mock.Mock(return_value=subprocess.CompletedProcess(
            [], 0, '{"format": {"duration": 1}, "streams": [null]}', "",
        ))
        with self.assertRaises(ValueError):
            deliverables.probe_media(Path("synthetic.mp4"), runner)


class PrimaryDeliveryTests(unittest.TestCase):
    setUp = DeliverableTests.setUp
    add_delivery = DeliverableTests.add_delivery
    status = DeliverableTests.status
    bind = DeliverableTests.bind
    prepare_stages = DeliverableTests.prepare_stages
    decision = DeliverableTests.decision
    lock = DeliverableTests.lock
    approval_mode = "approve_for_me"
    actor = "agent"

    def select_primary(self, *identifiers):
        for entry in self.fixture.manifest["deliverables"]:
            entry["primary"] = entry["id"] in identifiers
        self.write("production.json", json.dumps(self.fixture.manifest))

    def gate(self):
        return studio.stage_gate(self.context, "delivery", self.fixture.runner)

    def complete(self):
        return studio.complete_stage(self.context, "delivery", self.fixture.runner)

    def test_primary_named_lock_completes_without_legacy_lock_and_survives_newer_outputs(self):
        self.select_primary(self.spec["id"])
        service = studio.selection_service()
        with patch.object(service, "probe_media_streams", return_value={"video"}):
            self.prepare_stages()
            self.bind()
            locked = self.lock()
            result = self.complete()
            evidence = studio.stage_entry(result, "delivery")["evidence"]
            self.assertEqual(evidence["primary_deliverable_id"], self.spec["id"])
            self.assertEqual(evidence["delivery_binding"], locked["binding"])
            self.assertEqual(evidence["delivery_lock"], locked["lock"])
            for identifier, kind, language in (
                ("ep001-proxy", "proxy", "en"), ("ep001-fr-master", "master", "fr"),
            ):
                self.add_delivery({**self.spec, "id": identifier, "kind": kind, "language": language})
                newer = studio.render(self.context, identifier, "delivery", self.fixture.runner)
                self.bind(identifier, newer)
                failures, current = self.gate()
                self.assertEqual(failures, [])
                self.assertEqual(current, evidence)
                self.complete()
            self.assertEqual(studio.stage_entry(studio.read_stages(self.context), "delivery")
                             .get("locks", {}), {})
            self.assertTrue(all(stage["status"] == "pending"
                                for stage in studio.read_stages(self.fixture.context("ep002"))["stages"]))

    def test_missing_ambiguous_or_foreign_primary_never_falls_back_to_legacy_lock(self):
        service = studio.selection_service()
        with patch.object(service, "probe_media_streams", return_value={"video"}):
            self.prepare_stages()
            output = json.loads(self.record.read_text())["output"]["path"]
            studio.record_lock(self.context, self.fixture.decision(
                self.context, output, "legacy-final", kind="final_master", actor=self.actor,
            ))
            other = {**self.spec, "id": "ep001-fr-master", "language": "fr"}
            self.add_delivery(other)
            foreign = {**self.spec, "id": "ep002-master", "unit_id": "ep002"}
            self.add_delivery(foreign)
            for identifiers in ((), (self.spec["id"], other["id"]), (foreign["id"],)):
                with self.subTest(identifiers=identifiers):
                    self.select_primary(*identifiers)
                    before = self.context.stages_path.read_bytes()
                    with self.assertRaisesRegex(ValueError, "primary"):
                        self.complete()
                    self.assertEqual(self.context.stages_path.read_bytes(), before)

    def test_primary_requires_binding_and_lock_for_current_version(self):
        self.select_primary(self.spec["id"])
        service = studio.selection_service()
        with patch.object(service, "probe_media_streams", return_value={"video"}):
            self.prepare_stages()
            with self.assertRaisesRegex(ValueError, "bind|binding"):
                self.complete()
            self.bind()
            with self.assertRaisesRegex(ValueError, "lock"):
                self.complete()
            self.lock()
            self.bind()
            with self.assertRaisesRegex(ValueError, "current binding"):
                self.complete()
            self.lock(decision=self.decision(name="rebound-final"))
            self.complete()

    def test_stale_spec_review_and_output_block_primary_completion_without_writes(self):
        self.select_primary(self.spec["id"])
        service = studio.selection_service()
        with patch.object(service, "probe_media_streams", return_value={"video"}):
            self.prepare_stages()
            self.bind()
            decision = self.decision()
            self.lock(decision=decision)
            self.complete()
            spec_path = self.root / f"deliverables/{self.spec['id']}.json"
            changed = json.loads(spec_path.read_text())
            changed["spec"]["fps"] = "24/1"
            for path, content in (
                (spec_path, json.dumps(changed).encode()),
                (self.root / decision["review_path"], b"{}"),
                (self.root / decision["subject_path"], b"changed output"),
            ):
                with self.subTest(path=path.name):
                    original = path.read_bytes()
                    ledger = self.context.stages_path.read_bytes()
                    path.write_bytes(content)
                    self.assertTrue(self.gate()[0])
                    with self.assertRaises(ValueError):
                        self.complete()
                    self.assertEqual(self.context.stages_path.read_bytes(), ledger)
                    path.write_bytes(original)
                    self.assertEqual(self.gate()[0], [])

    def test_primary_preserves_audio_lock_requirement_when_preparation_skipped(self):
        self.select_primary(self.spec["id"])
        service = studio.selection_service()
        with patch.object(service, "probe_media_streams", return_value={"video"}):
            self.prepare_stages()
            self.bind()
            self.lock()
        with (
            patch.object(service, "probe_media_streams", return_value={"video", "audio"}),
            self.assertRaisesRegex(ValueError, "audio lock is required"),
        ):
            self.complete()


class UserPrimaryDeliveryTests(PrimaryDeliveryTests):
    approval_mode = "ask_for_approval"
    actor = "user"


if __name__ == "__main__":
    unittest.main()
