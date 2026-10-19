from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import editorial
import production_context as contexts
import production_post
import studio_project as studio


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.write("project.md", "---\napproval_mode: approve_for_me\n---\nSynthetic film\n")
        self.probe = patch.object(studio, "probe_media", return_value={
            "duration_s": 6.0, "streams": [{"codec_type": "video"}],
        })
        self.probe.start()
        self.addCleanup(self.probe.stop)
        self.audio = patch.object(studio, "probe_has_audio", return_value=False)
        self.audio.start()
        self.addCleanup(self.audio.stop)
        self.context = contexts.resolve_context(self.root)
        self.add_shot("s001_sh010", "scene-001")
        self.add_shot("s002_sh010", "scene-002")
        self.context = contexts.resolve_context(self.root)
        self.select_shots()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def add_shot(self, shot, scene):
        self.write(f"scenes/{scene}/scene.md", "# Scene\n")
        self.write(f"scenes/{scene}/{shot}/shot.md",
                   f"---\nshot_id: {shot}\nduration_s: 4\n"
                   "aspect: '16:9'\nresolution: 720p\n---\nShot\n")
        self.write(f"scenes/{scene}/{shot}/{shot}.mp4", f"synthetic {shot}")

    def select_shots(self):
        context = self.context
        for shot in studio.discover_shots(context):
            filename = f"{shot.shot_id}.mp4"
            subject = f"{shot.directory}/{filename}"
            digest = studio.sha256_file(self.root / subject)
            studio.sync(context, {shot.shot_id: filename}, probe=lambda _: 4)
            review = self.write(f"review/{shot.shot_id}.json", json.dumps({
                "schema_version": 1, "artifact_path": subject, "artifact_sha256": digest,
                "status": "pass", "inspection_method": "Synthetic temporal playback fixture",
                "coverage": "Entire fixture", "checks": [
                    {"criterion": "fixture", "status": "pass", "evidence": "Synthetic only"},
                ], "observations": ["Synthetic"], "limitations": ["No creative claim"],
                "recommendation": "Approve fixture",
            }))
            decision = {
                "schema_version": 1 if context.legacy else 2,
                "decision_id": f"select-{shot.shot_id}", "decision_type": "variant_selection",
                "subject_path": subject, "selected_variant": filename,
                "selected_sha256": digest, "asset_id": shot.shot_id,
                "actor": "agent", "approval_mode": "approve_for_me",
                "project_sha256": studio.sha256_file(self.root / "project.md")
                if context.legacy else contexts.context_project_sha256(self.root),
                "result": "approved", "review_path": review.relative_to(self.root).as_posix(),
                "review_sha256": studio.sha256_file(review), "upstream_sha256": {},
                "reason": "Synthetic fixture", "decided_at": datetime.now(UTC).isoformat(),
            }
            if not context.legacy:
                decision["context"] = context.identity()
                decision["upstream_sha256"] = {
                    context.unit_brief.relative_to(self.root).as_posix():
                        studio.sha256_file(context.unit_brief),
                }
            studio.record_selection(context, shot.shot_id, decision)

    @property
    def output(self):
        return f"editorial/{self.context.unit_id or 'main'}/cut-v01.json"

    @property
    def index(self):
        return self.context.studio_root / "index.html"

    def export(self, output=None):
        return editorial.export_edit(self.context, output or self.output)

    def test_export_reads_actual_order_trims_gaps_and_measured_duration(self):
        text = self.index.read_text()
        text = text.replace('data-start="0" data-duration="4"', 'data-start="5" data-duration="3"')
        text = text.replace('data-start="4" data-duration="4"', 'data-start="1" data-duration="2"')
        self.index.write_text(text + "\n<!-- preserve my manual edit -->\n")
        frame = self.context.studio_root / "compositions/s001_sh010.html"
        frame.write_text(frame.read_text().replace('data-start="0"', 'data-start="0.5" data-media-start="2"'))
        before = self.files()
        path = self.export()
        document = json.loads(path.read_text())
        self.assertEqual([entry["shot_id"] for entry in document["entries"]],
                         ["s002_sh010", "s001_sh010"])
        entry = document["entries"][1]
        self.assertEqual((entry["timeline_start_s"], entry["source_in_s"],
                          entry["source_out_s"], entry["source_duration_s"]),
                         (5.5, 2, 4.5, 6))
        self.assertEqual(document["runtime"]["tree_sha256"], studio.tree_digest(self.context))
        self.assertEqual(document["source_edit"]["path"], "studio/index.html")
        self.assertEqual(production_post.validate_editorial(self.root, document), [])
        self.assertEqual(editorial.check_edit(self.context, self.output), [])
        for name, content in before.items():
            self.assertEqual((self.root / name).read_bytes(), content, name)

    def test_export_is_immutable_and_main_requires_explicit_reconciliation(self):
        path = self.export()
        original = path.read_bytes()
        self.assertEqual(self.export(), path)
        self.index.write_text(self.index.read_text() + "<!-- new revision -->")
        with self.assertRaisesRegex(ValueError, "immutable|exists"):
            self.export()
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "reconcile"):
            self.export("editorial/main/main.json")

    def test_reconcile_is_compare_and_swap_and_preserves_prior_snapshots(self):
        first = self.export()
        first_bytes = first.read_bytes()
        main = editorial.reconcile_edit(self.context, self.output, expected_revision=None)
        revision = studio.sha256_file(main)
        self.index.write_text(self.index.read_text() + "<!-- revised -->")
        second_name = "editorial/main/cut-v02.json"
        second = self.export(second_name)
        before = self.files()
        for stale in (None, "0" * 64):
            with self.assertRaisesRegex(ValueError, "revision"):
                editorial.reconcile_edit(self.context, second_name, expected_revision=stale)
            self.assertEqual(self.files(), before)
        editorial.reconcile_edit(self.context, second_name, expected_revision=revision)
        self.assertEqual(main.read_bytes(), second.read_bytes())
        self.assertEqual(first.read_bytes(), first_bytes)
        self.assertEqual(editorial.check_edit(self.context, "editorial/main/main.json"), [])

    def test_check_detects_forged_order_and_trim_even_with_current_file_hashes(self):
        path = self.export()
        document = json.loads(path.read_text())
        document["entries"][0]["source_in_s"] = 1
        document["entries"][0]["source_out_s"] = 5
        path.write_text(json.dumps(document))
        findings = editorial.check_edit(self.context, self.output)
        self.assertIn("edit", {finding.code for finding in findings})
        document["entries"].reverse()
        path.write_text(json.dumps(document))
        self.assertIn("order", {finding.code for finding in editorial.check_edit(self.context, self.output)})

    def test_stale_tree_selection_decision_and_take_are_rejected(self):
        self.export()
        changes = [
            (self.index, "<!-- edit -->"),
            (self.root / "decisions/select-s001_sh010.json", "\n"),
            (self.root / "scenes/scene-001/s001_sh010/s001_sh010.mp4", "changed"),
            (self.root / "review/s001_sh010.json", "\n"),
        ]
        for path, extra in changes:
            with self.subTest(path=path):
                before = path.read_bytes()
                path.write_bytes(before + extra.encode())
                self.assertTrue(editorial.check_edit(self.context, self.output))
                path.write_bytes(before)

    def test_unsupported_edits_fail_without_any_project_writes(self):
        (self.root / ".selection.lock").unlink()
        original = self.index.read_text()
        edits = [
            original.replace('data-start="4"', 'data-start="2"'),
            original.replace(studio.FRAMES_MARKER, '<p>Overlay</p>'),
            original.replace('id="s001_sh010"', 'data-hidden="true" id="s001_sh010"'),
            original.replace('tl.seek(0);', 'tl.to("#root", {opacity: 0});'),
            original.replace('id="s001_sh010"', 'data-media-start="1" id="s001_sh010"'),
            original.replace('id="s001_sh010"', 'style="display:none" id="s001_sh010"'),
            original.replace('id="s001_sh010"', 'data-variable-values="{}" id="s001_sh010"'),
            original.replace('id="s001_sh010"', 'id="duplicate" id="s001_sh010"'),
        ]
        for text in edits:
            with self.subTest(text=text):
                self.index.write_text(text)
                before = self.files()
                with self.assertRaises(ValueError):
                    self.export()
                self.assertEqual(self.files(), before)
        self.index.write_text(original)

    def test_invalid_media_timing_and_unmeasurable_sources_fail_closed(self):
        frame = self.context.studio_root / "compositions/s001_sh010.html"
        original = frame.read_text()
        for attribute in ('data-media-start="5"', 'data-media-start="-1"',
                          'data-media-start="NaN"', 'data-playback-rate="2"',
                          'data-automation="{}"', 'loop'):
            frame.write_text(original.replace("<video ", f"<video {attribute} "))
            before = self.files()
            with self.assertRaises(ValueError):
                self.export()
            self.assertEqual(self.files(), before)
        frame.write_text(original)
        with (
            patch.object(studio, "probe_media", return_value={"duration_s": 6, "streams": []}),
            self.assertRaisesRegex(ValueError, "video"),
        ):
            self.export()

    def test_paths_symlinks_and_expected_tree_fail_without_writes(self):
        for output in ("../outside.json", "/tmp/outside.json",
                       "studio/index.html", "editorial/foreign/cut.json"):
            with self.subTest(output=output):
                before = self.files()
                with self.assertRaises(ValueError):
                    self.export(output)
                self.assertEqual(self.files(), before)
        before = self.files()
        with self.assertRaisesRegex(ValueError, "tree|revision"):
            editorial.export_edit(self.context, self.output, "0" * 64)
        self.assertEqual(self.files(), before)
        (self.root / "editorial").symlink_to(self.context.studio_root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.export()

    def test_manual_change_during_probe_is_preserved_and_export_aborts(self):
        def probe(_):
            self.index.write_text(self.index.read_text() + "<!-- concurrent -->")
            return {"duration_s": 6, "streams": [{"codec_type": "video"}]}
        with (
            patch.object(studio, "probe_media", side_effect=probe),
            self.assertRaisesRegex(ValueError, "changed|tree"),
        ):
            self.export()
        self.assertIn("<!-- concurrent -->", self.index.read_text())
        self.assertFalse((self.root / "editorial").exists())

    def test_foreign_and_forged_contexts_are_rejected(self):
        for context in (replace(self.context, studio_root=self.root),
                        replace(self.context, scene_ids=("scene-999",)),
                        replace(self.context, _candidate_manifest="production.plan.json")):
            with self.subTest(context=context):
                before = self.files()
                with self.assertRaises(ValueError):
                    editorial.export_edit(context, self.output)
                self.assertEqual(self.files(), before)

    def test_cli_export_and_check_and_failure_are_structured(self):
        for arguments in (
            ["export", str(self.root), "--output", self.output],
            ["check", str(self.root), "--record", self.output],
            ["reconcile", str(self.root), "--record", self.output,
             "--expected-revision", "absent"],
            ["check", str(self.root), "--record", "editorial/main/main.json"],
        ):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(editorial.main(arguments), 0)
            self.assertTrue(json.loads(stdout.getvalue())["valid"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(editorial.main(["check", str(self.root), "--record", "missing.json"]), 2)

    def test_parallel_reconciliation_allows_only_one_expected_revision(self):
        self.export()
        main = editorial.reconcile_edit(self.context, self.output, expected_revision=None)
        revision = studio.sha256_file(main)
        self.index.write_text(self.index.read_text() + "<!-- new -->")
        second = "editorial/main/cut-v02.json"
        self.export(second)
        def reconcile(_):
            try:
                editorial.reconcile_edit(self.context, second, expected_revision=revision)
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(reconcile, range(2))), [False, True])

    def test_cli_real_probe_smoke(self):
        self.probe.stop()
        for source in self.root.glob("scenes/*/*/*.mp4"):
            result = subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                "color=c=black:s=32x32:r=24:d=6", "-c:v", "libx264", "-y", str(source),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
        for shot in studio.discover_shots(self.context):
            source = self.root / shot.directory / f"{shot.shot_id}.mp4"
            asset = studio.asset_name(studio.sha256_file(source), source.name)
            (self.context.studio_root / "assets" / asset).write_bytes(source.read_bytes())
            frame = self.context.studio_root / "compositions" / f"{shot.shot_id}.html"
            frame.write_text(studio.frame_html(shot.shot_id, asset, 4, 1, 1280, 720, False))
            (self.root / f"decisions/select-{shot.shot_id}.json").unlink()
        self.select_shots()
        command = [sys.executable, str(Path(editorial.__file__)), "export",
                   str(self.root), "--output", self.output]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["valid"])

    def activate_units(self):
        self.root = self.root / "scoped"
        self.write("project.md", "---\napproval_mode: approve_for_me\n---\nShared film\n")
        for number in (1, 2, 3):
            self.add_shot(f"s{number:03}_sh010", f"scene-{number:03}")
        for unit in ("ep001", "ep002"):
            self.write(f"units/{unit}/unit.md", f"# {unit}\n")
        self.write("production.json", json.dumps({
            "schema_version": 1, "format": "episodic-show",
            "units": [
                {"id": "ep001", "kind": "episode", "brief": "units/ep001/unit.md",
                 "scene_ids": ["scene-003", "scene-001"]},
                {"id": "ep002", "kind": "episode", "brief": "units/ep002/unit.md",
                 "scene_ids": ["scene-002"]},
            ],
        }))
        self.context = contexts.resolve_context(self.root, "ep001")
        self.select_shots()

    def test_unit_cli_binds_scope_and_unrelated_unit_does_not_invalidate(self):
        self.activate_units()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(editorial.main([
                "export", str(self.root), "--unit", "ep001", "--output", self.output,
            ]), 0)
        path = self.root / json.loads(stdout.getvalue())["snapshot"]
        document = json.loads(path.read_text())
        self.assertEqual(document["runtime"]["context"], self.context.identity())
        self.assertEqual(document["runtime"]["scene_ids"], ["scene-003", "scene-001"])
        self.assertEqual([entry["shot_id"] for entry in document["entries"]],
                         ["s003_sh010", "s001_sh010"])
        self.assertEqual(document["source_edit"]["path"], "units/ep001/studio/index.html")
        self.write("units/ep002/unit.md", "# Unrelated revision\n")
        self.assertEqual(editorial.check_edit(self.context, self.output), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(editorial.main([
                "check", str(self.root), "--unit", "ep001", "--record", self.output,
            ]), 0)
            self.assertEqual(editorial.main([
                "export", str(self.root), "--output", self.output,
            ]), 2)
        self.assertFalse((self.root / "studio").exists())

    def test_unit_membership_brief_foreign_decision_and_foreign_snapshot_fail(self):
        self.activate_units()
        self.export()
        foreign = contexts.resolve_context(self.root, "ep002")
        self.assertTrue(editorial.check_edit(foreign, self.output))
        decision_path = self.root / "decisions/select-s003_sh010.json"
        decision = json.loads(decision_path.read_text())
        decision["context"] = foreign.identity()
        original = decision_path.read_bytes()
        decision_path.write_text(json.dumps(decision))
        self.assertTrue(editorial.check_edit(self.context, self.output))
        decision_path.write_bytes(original)
        self.write("units/ep001/unit.md", "# Revised first unit\n")
        before = self.files()
        with self.assertRaisesRegex(ValueError, "Stale|stale"):
            self.export("editorial/ep001/cut-v02.json")
        self.assertEqual(self.files(), before)
        current = contexts.resolve_context(self.root, "ep001")
        self.assertTrue(editorial.check_edit(current, self.output))
        manifest = json.loads((self.root / "production.json").read_text())
        manifest["units"][0]["scene_ids"].reverse()
        self.write("production.json", json.dumps(manifest))
        self.assertTrue(editorial.check_edit(current, self.output))

    def test_unselected_and_missing_selection_evidence_cannot_export(self):
        manifest = self.root / "scenes/scene-001/s001_sh010/shot.md"
        original = manifest.read_text()
        for field in ("selected_variant:", "selection_evidence:"):
            manifest.write_text(original.replace(field, f"unbound_{field}"))
            before = self.files()
            with self.assertRaises(ValueError):
                self.export()
            self.assertEqual(self.files(), before)

    def test_main_edit_during_reconcile_probe_is_not_overwritten(self):
        self.export()
        main = editorial.reconcile_edit(self.context, self.output, expected_revision=None)
        revision = studio.sha256_file(main)
        calls = 0
        def probe(_):
            nonlocal calls
            calls += 1
            if calls == 3:
                main.write_text(main.read_text() + "\n")
            return {"duration_s": 6, "streams": [{"codec_type": "video"}]}
        with (
            patch.object(studio, "probe_media", side_effect=probe),
            self.assertRaisesRegex(ValueError, "revision"),
        ):
            editorial.reconcile_edit(self.context, self.output, expected_revision=revision)
        self.assertTrue(main.read_bytes().endswith(b"\n\n"))

    def test_review_change_during_last_probe_aborts_export(self):
        calls = 0
        def probe(_):
            nonlocal calls
            calls += 1
            if calls == 4:
                review = self.root / "review/s001_sh010.json"
                review.write_text(review.read_text() + "\n")
            return {"duration_s": 6, "streams": [{"codec_type": "video"}]}
        with (
            patch.object(studio, "probe_media", side_effect=probe),
            self.assertRaises(ValueError),
        ):
            self.export()
        self.assertFalse((self.root / self.output).exists())

    def test_snapshot_change_during_check_is_reported_without_rewriting_it(self):
        path = self.export()
        def probe(_):
            path.write_text(path.read_text() + "\n")
            return {"duration_s": 6, "streams": [{"codec_type": "video"}]}
        with patch.object(studio, "probe_media", side_effect=probe):
            findings = editorial.check_edit(self.context, self.output)
        self.assertTrue(any("changed during check" in finding.message for finding in findings))
        self.assertTrue(path.read_bytes().endswith(b"\n\n\n"))

    def test_overlapping_hosts_are_unsupported_even_when_videos_do_not_overlap(self):
        self.index.write_text(self.index.read_text().replace('data-start="4"', 'data-start="2"'))
        first = self.context.studio_root / "compositions/s001_sh010.html"
        first.write_text(first.read_text().replace('data-duration="4"', 'data-duration="2"'))
        before = self.files()
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.export()
        self.assertEqual(self.files(), before)

    def test_split_take_reuse_preserves_independent_host_ids_and_ranges(self):
        text = self.index.read_text()
        extra = studio.host_html("s001_sh010", 8, 2, 1280, 720).replace(
            'id="s001_sh010" ', 'id="split-second" ', 1,
        )
        text = text.replace(studio.FRAMES_MARKER, studio.FRAMES_MARKER + extra)
        self.index.write_text(studio.with_root_duration(text, 10))
        document = json.loads(self.export().read_text())
        self.assertEqual([entry["host_id"] for entry in document["entries"]],
                         ["s001_sh010", "s002_sh010", "split-second"])
        self.assertEqual(document["entries"][-1]["source_out_s"], 2)

    def test_reconciliation_archives_exact_previous_bytes_and_uses_shared_transaction(self):
        self.export()
        main = editorial.reconcile_edit(self.context, self.output, expected_revision=None)
        main.write_bytes(main.read_bytes().replace(b"\n", b"\r\n"))
        previous = main.read_bytes()
        revision = studio.sha256_file(main)
        service = studio.selection_service()
        with patch.object(service, "commit_targets", wraps=service.commit_targets) as commit:
            editorial.reconcile_edit(self.context, self.output, expected_revision=revision)
        self.assertEqual(commit.call_count, 1)
        archive = self.root / f"editorial/main/snapshots/{revision}.json"
        self.assertEqual(archive.read_bytes(), previous)

    def test_pending_transaction_and_malformed_snapshot_are_read_only_failures(self):
        self.export()
        journal = self.write(".selection-journal.json", '{"version":1,"files":{}}')
        before = self.files()
        with self.assertRaisesRegex(ValueError, "transaction"):
            self.export()
        self.assertEqual(self.files(), before)
        journal.unlink()
        path = self.root / self.output
        for text in ("null", "{}", "[]", "invalid"):
            path.write_text(text)
            before = self.files()
            self.assertTrue(editorial.check_edit(self.context, self.output))
            self.assertEqual(self.files(), before)

    def test_interrupted_export_requires_explicit_shared_transaction_recovery(self):
        service = studio.selection_service()
        with (
            patch.object(service, "recover_selection", side_effect=OSError("Interrupted fixture")),
            self.assertRaisesRegex(ValueError, "interrupted"),
        ):
            self.export()
        before = self.files()
        with self.assertRaisesRegex(ValueError, "transaction"):
            self.export()
        self.assertEqual(self.files(), before)
        with service.writer_lock(self.root):
            self.assertTrue(service.recover_selection(self.root))
        self.assertEqual(self.export(), self.root / self.output)
        self.assertEqual(editorial.check_edit(self.context, self.output), [])

    def test_legacy_post_schema_stays_valid_but_runtime_check_requires_export_binding(self):
        path = self.export()
        document = json.loads(path.read_text())
        del document["runtime"]
        for entry in document["entries"]:
            for key in ("host_id", "selection_decision", "shot_manifest"):
                del entry[key]
        self.assertEqual(production_post.validate_editorial(self.root, document), [])
        path.write_text(json.dumps(document))
        self.assertEqual([finding.code for finding in editorial.check_edit(self.context, self.output)],
                         ["runtime"])

    def test_foreign_host_empty_timeline_and_escaped_media_fail_closed(self):
        self.activate_units()
        original = self.index.read_text()
        foreign = studio.host_html("s002_sh010", 8, 4, 1280, 720)
        self.index.write_text(studio.with_root_duration(
            original.replace(studio.FRAMES_MARKER, studio.FRAMES_MARKER + foreign), 12,
        ))
        before = self.files()
        with self.assertRaisesRegex(ValueError, "foreign"):
            self.export()
        self.assertEqual(self.files(), before)
        self.index.write_text(studio.root_html(1280, 720, 24))
        with self.assertRaisesRegex(ValueError, "empty"):
            self.export()
        self.index.write_text(original)
        asset = next((self.context.studio_root / "assets").glob("*.mp4"))
        content = asset.read_bytes()
        outside = self.write("outside-studio.mp4", content.decode())
        asset.unlink()
        asset.symlink_to(outside)
        before = self.files()
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
