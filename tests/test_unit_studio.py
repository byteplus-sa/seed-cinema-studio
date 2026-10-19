from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import production_context as contexts
import studio_project as studio


class UnitStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.write("project.md", "---\napproval_mode: approve_for_me\n"
                   "delivery:\n  aspect: '16:9'\n  resolution: 1080p\n  fps: 25\n---\nShared.\n")
        self.manifest = {
            "schema_version": 1, "format": "episodic-show",
            "units": [
                {"id": "ep001", "kind": "episode", "brief": "units/ep001/unit.md",
                 "scene_ids": ["scene-003", "scene-001"]},
                {"id": "ep002", "kind": "episode", "brief": "units/ep002/unit.md",
                 "scene_ids": ["scene-002"]},
            ], "deliverables": [],
        }
        for number in (1, 2):
            self.write(f"units/ep{number:03}/unit.md", f"# Episode {number}\n")
        for number in (1, 2, 3):
            self.write(f"scenes/scene-{number:03}/scene.md", "# Scene\n")
            self.write(f"scenes/scene-{number:03}/s{number:03}_sh010/shot.md",
                       f"---\nshot_id: s{number:03}_sh010\nduration_s: 2\n"
                       "aspect: '9:16'\nresolution: 480p\n---\n# Shot\n")
        self.write("production.json", json.dumps(self.manifest))

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def context(self, unit="ep001"):
        return contexts.resolve_context(self.root, unit)

    def decision(self, context, subject, identifier, *, kind=None, shot=None, actor="agent"):
        digest = studio.sha256_file(self.root / subject)
        review = {
            "schema_version": 1, "artifact_path": subject, "artifact_sha256": digest,
            "status": "pass", "inspection_method": "Full temporal playback and listening",
            "coverage": "Entire synthetic fixture", "checks": [
                {"criterion": "fixture", "status": "pass", "evidence": "mock inspection"}
            ], "observations": ["Synthetic fixture"], "limitations": [],
            "recommendation": "Approve",
        }
        review_path = self.write(f"review/{identifier}.json", json.dumps(review))
        decision = {
            "schema_version": 2, "context": context.identity(), "decision_id": identifier,
            "decision_type": "stage_lock" if kind else "variant_selection",
            "subject_path": subject, "subject_sha256": digest, "actor": actor,
            "approval_mode": studio.project_mode_snapshot(self.root)[0],
            "project_sha256": contexts.context_project_sha256(self.root),
            "result": "approved", "review_path": review_path.relative_to(self.root).as_posix(),
            "review_sha256": studio.sha256_file(review_path),
            "upstream_sha256": {
                context.unit_brief.relative_to(self.root).as_posix():
                    studio.sha256_file(context.unit_brief)
            } if context.unit_brief else {},
            "reason": "Synthetic passing evidence", "decided_at": datetime.now(UTC).isoformat(),
        }
        if kind:
            decision.update(lock_kind=kind, stage_id=studio.STAGE_LOCKS[kind])
        else:
            decision.pop("subject_sha256")
            decision.update(
                asset_id=shot, selected_variant=Path(subject).name, selected_sha256=digest,
            )
        if actor == "user":
            decision["authorization"] = {"source": "chat", "evidence": "Approve this fixture take"}
        return decision

    @staticmethod
    def runner(argv, **kwargs):
        if "render" in argv:
            Path(argv[argv.index("--output") + 1]).write_bytes(b"synthetic render")
            return subprocess.CompletedProcess(argv, 0, "", "")
        if "check" in argv:
            return subprocess.CompletedProcess(
                argv, 0, '{"ok": true, "browserSkipped": false}', "",
            )
        return subprocess.CompletedProcess(argv, 0, json.dumps({
            "format": {"duration": "4"},
            "streams": [{"codec_type": "video", "width": 1920, "height": 1080,
                         "r_frame_rate": "25/1"}],
        }), "")

    def select_shots(self, context, actor="agent"):
        for shot in studio.discover_shots(context):
            subject = f"{shot.directory}/{shot.shot_id}_t01_v01.mp4"
            self.write(subject, "synthetic shot")
            studio.sync(context, {shot.shot_id: Path(subject).name}, probe=lambda _: 2)
            studio.record_selection(context, shot.shot_id, self.decision(
                context, subject, f"select-{shot.shot_id}", shot=shot.shot_id, actor=actor,
            ))

    def finish_unit(self, context, actor):
        self.select_shots(context, actor)
        service = studio.selection_service()
        with patch.object(service, "probe_media_streams", return_value={"video"}):
            for stage in studio.STAGES:
                if stage in studio.OPTIONAL_STAGES:
                    studio.skip_stage(context, stage, "Wordless synthetic fixture")
                    continue
                studio.start_stage(context, stage)
                if stage in ("assembly-review", "delivery"):
                    name = "cut" if stage == "assembly-review" else "master"
                    quality = "draft" if name == "cut" else "delivery"
                    record_path = studio.render(context, name, quality, self.runner)
                    output = json.loads(record_path.read_text())["output"]["path"]
                    kind = "picture" if name == "cut" else "final_master"
                    studio.record_lock(context, self.decision(
                        context, output, f"{context.unit_id}-lock-{kind}", kind=kind, actor=actor,
                    ))
                studio.complete_stage(context, stage, self.runner)

    def test_ordered_discovery_and_profile_canvas_do_not_create_root_studio(self):
        context = self.context()
        self.assertEqual([shot.shot_id for shot in studio.discover_shots(context)],
                         ["s003_sh010", "s001_sh010"])
        studio.sync(context)
        self.assertEqual(studio.canvas_dimensions(context), (1920, 1080))
        self.assertIn('data-fps="25"', (context.studio_root / "index.html").read_text())
        self.assertFalse((self.root / "studio").exists())
        self.assertFalse(self.context("ep002").studio_root.exists())
        adapter = contexts._brief(context.studio_root / "BRIEF.md")[0]
        self.assertEqual(adapter["context"], context.identity())
        self.assertEqual(adapter["source_sha256"]["units/ep001/unit.md"],
                         studio.sha256_file(context.unit_brief))

    def test_stages_are_independent_and_foreign_ledger_is_rejected(self):
        first, second = self.context(), self.context("ep002")
        studio.init_studio(first)
        studio.init_studio(second)
        studio.start_stage(first, "brief-development")
        studio.complete_stage(first, "brief-development")
        self.assertEqual(studio.read_stages(second)["stages"][0]["status"], "pending")
        second.stages_path.write_bytes(first.stages_path.read_bytes())
        with self.assertRaisesRegex(ValueError, "context|scope"):
            studio.read_stages(second)

    def test_user_authored_and_modified_adapters_are_preserved(self):
        context = self.context()
        adapter = self.write("units/ep001/studio/BRIEF.md", "# My own brief\n")
        with self.assertRaisesRegex(ValueError, "BRIEF|brief"):
            studio.init_studio(context)
        self.assertEqual(adapter.read_text(), "# My own brief\n")
        adapter.unlink()
        studio.init_studio(context)
        adapter.write_text(adapter.read_text() + "My edit\n")
        with self.assertRaisesRegex(ValueError, "BRIEF|brief"):
            studio.sync(context)
        self.assertTrue(adapter.read_text().endswith("My edit\n"))

    def test_candidate_context_cannot_mutate_studio(self):
        (self.root / "production.json").rename(self.root / "production.plan.json")
        context = contexts.resolve_candidate_context(self.root, "production.plan.json", "ep001")
        with self.assertRaisesRegex(ValueError, "candidate|read.only"):
            studio.init_studio(context)
        self.assertFalse(context.studio_root.exists())

    def test_cli_requires_unit_for_mutations_and_aggregates_status(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(studio.main(["init", str(self.root)]), 1)
        self.assertFalse((self.root / "studio").exists())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(studio.main(["status", str(self.root)]), 0)
        self.assertEqual(set(json.loads(output.getvalue())["units"]), {"ep001", "ep002"})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(studio.main(["init", str(self.root), "--unit", "ep001"]), 0)

    def test_manual_compositions_survive_sync_and_foreign_shots_fail(self):
        context = self.context()
        studio.sync(context)
        index = context.studio_root / "index.html"
        index.write_text(index.read_text() + "\n<!-- manual edit -->\n")
        before = index.read_bytes()
        studio.sync(context)
        self.assertEqual(index.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, "Unknown shot"):
            studio.candidates(context, "s002_sh010")

    def test_render_has_scope_and_order_and_foreign_render_cannot_gate(self):
        context = self.context()
        studio.sync(context)
        def runner(argv, **kwargs):
            if "render" in argv:
                Path(argv[argv.index("--output") + 1]).write_bytes(b"synthetic render")
                return subprocess.CompletedProcess(argv, 0, "", "")
            return subprocess.CompletedProcess(argv, 0, json.dumps({
                "format": {"duration": "2"},
                "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
            }), "")
        record_path = studio.render(context, quality="draft", runner=runner)
        record = json.loads(record_path.read_text())
        self.assertEqual(record["schema_version"], 2)
        self.assertEqual(record["context"], context.identity())
        self.assertEqual(record["scene_ids"], ["scene-003", "scene-001"])
        self.assertTrue(record["output"]["path"].startswith("units/ep001/studio/"))
        second = self.context("ep002")
        studio.sync(second)
        failures, _ = studio.delivery_gate(second, render_record=record_path)
        self.assertTrue(failures)

    def test_shared_canon_sync_reuses_source_without_rewriting_decisions(self):
        for number in (1, 2):
            self.write(f"units/ep{number:03}/unit.md",
                       f"---\nelements: [hero]\n---\n# Episode {number}\n")
        self.write("elements/hero/element.md",
                   "---\nstatus: review\n"
                   "variants: [hero_v01.png]\n---\n")
        self.write("elements/hero/hero_v01.png", "synthetic image")
        studio.init_studio(self.context())
        context = contexts.resolve_production_context(self.root)
        decision = self.decision(
            context, "elements/hero/hero_v01.png", "canon-hero", shot="hero",
        )
        studio.record_element_lock(self.root, "hero", decision)
        before = (self.root / "decisions/canon-hero.json").read_bytes()
        for unit in ("ep001", "ep002"):
            context = self.context(unit)
            studio.init_studio(context)
            studio.sync_elements(context)
            self.assertEqual((context.studio_root / "assets/LOCKED_hero_v01.png").read_text(),
                             "synthetic image")
        self.assertFalse((self.root / "studio").exists())
        self.assertEqual((self.root / "decisions/canon-hero.json").read_bytes(), before)
        copy = self.context().studio_root / "assets/LOCKED_hero_v01.png"
        copy.write_text("manual edit")
        with self.assertRaisesRegex(ValueError, "manual"):
            studio.sync_elements(self.context())
        self.assertEqual(copy.read_text(), "manual edit")

    def test_canon_sync_ignores_unrelated_broken_approvals_and_uses_explicit_membership(self):
        self.write("scenes/scene-003/scene.md", "---\nelements: [hero]\n---\n")
        self.write("elements/hero/element.md",
                   "---\nstatus: review\nvariants: [hero_v01.png]\n---\n")
        self.write("elements/hero/hero_v01.png", "synthetic image")
        studio.init_studio(self.context())
        production = contexts.resolve_production_context(self.root)
        studio.record_element_lock(self.root, "hero", self.decision(
            production, "elements/hero/hero_v01.png", "canon-hero", shot="hero",
        ))
        self.write("elements/other/element.md", "---\nstatus: approved\n"
                   "selected_variant: other_v01.png\n---\n")
        self.write("elements/other/other_v01.png", "unreviewed image")
        first, second = self.context(), self.context("ep002")
        studio.sync(first)
        studio.sync(second)
        self.assertEqual(studio.sync_elements(first)["locked"], ["LOCKED_hero_v01.png"])
        self.assertEqual(studio.sync_elements(second)["locked"], [])
        before = studio.tree_digest(first)
        self.write("elements/other/other_v01.png", "changed unrelated image")
        studio.sync_elements(first)
        self.assertEqual(studio.tree_digest(first), before)

    def test_required_canon_gate_rejects_missing_and_unapproved_elements(self):
        self.write("units/ep001/unit.md", "---\nrequired_elements: [missing]\n---\n")
        first, second = self.context(), self.context("ep002")
        studio.sync(first)
        studio.sync(second)
        failures, _ = studio.stage_gate(first, "canon-elements")
        self.assertTrue(any("missing" in failure for failure in failures), failures)
        self.assertEqual(studio.stage_gate(second, "canon-elements")[0], [])

    def test_explicit_canon_declarations_include_scene_shot_plan_and_shot_manifest(self):
        self.write("scenes/scene-003/scene.md", "---\nshot_plan:\n  shots:\n"
                   "    - id: s003_sh010_a\n      elements: [hero]\n---\n")
        path = self.root / "scenes/scene-001/s001_sh010/shot.md"
        path.write_text(path.read_text().replace("duration_s: 2", "elements: [room]\nduration_s: 2"))
        self.assertEqual(studio.required_element_ids(self.context()), {"hero", "room"})
        self.assertEqual(studio.required_element_ids(self.context("ep002")), set())

    def test_invalid_canon_declarations_fail_closed(self):
        for value in ("null", "hero", "[../hero]", "[1]", "{}"):
            with self.subTest(value=value):
                self.write("scenes/scene-003/scene.md", f"---\nelements: {value}\n---\n")
                with self.assertRaisesRegex(ValueError, "elements"):
                    studio.sync(self.context())

    def test_fenced_scene_shot_plan_declares_required_canon(self):
        self.write("scenes/scene-003/scene.md", "# Scene\n\n## Shot plan\n\n"
                   "```yaml\nshot_plan:\n  shots:\n    - id: s003_sh010_a\n"
                   "      duration_s: 2\n      elements: [hero]\n```\n")
        self.assertEqual(studio.required_element_ids(self.context()), {"hero"})

    def test_episode_one_delivered_while_episode_two_stays_planned_in_both_modes(self):
        for mode, actor in (("approve_for_me", "agent"), ("ask_for_approval", "user")):
            with self.subTest(mode=mode):
                if mode == "ask_for_approval":
                    self.setUp()
                    path = self.root / "project.md"
                    path.write_text(path.read_text().replace("approve_for_me", mode))
                first, second = self.context(), self.context("ep002")
                studio.sync(second)
                second_before = (second.studio_root / "index.html").read_bytes()
                self.finish_unit(first, actor)
                self.assertEqual(studio.read_stages(first)["stages"][-1]["status"], "complete")
                self.assertTrue(all(item["status"] == "pending"
                                    for item in studio.read_stages(second)["stages"]))
                self.assertEqual((second.studio_root / "index.html").read_bytes(), second_before)
                first_ledger = first.stages_path.read_bytes()
                self.finish_unit(second, actor)
                self.assertEqual(studio.read_stages(second)["stages"][-1]["status"], "complete")
                self.assertEqual(first.stages_path.read_bytes(), first_ledger)
                with patch.object(studio.selection_service(), "probe_media_streams", return_value={"video"}):
                    self.assertEqual(studio.stage_gate(first, "delivery", self.runner)[0], [])
                self.assertFalse((self.root / "studio").exists())

    def test_parallel_unit_mutations_preserve_each_ledger_and_shared_selections(self):
        for mode, actor in (("approve_for_me", "agent"), ("ask_for_approval", "user")):
            with self.subTest(mode=mode):
                if mode == "ask_for_approval":
                    self.setUp()
                    path = self.root / "project.md"
                    path.write_text(path.read_text().replace("approve_for_me", mode))
                first, second = self.context(), self.context("ep002")
                with ThreadPoolExecutor(max_workers=2) as executor:
                    list(executor.map(partial(self.select_shots, actor=actor), (first, second)))
                for context in (first, second):
                    self.assertTrue(studio.status(context)["ok"])
                    studio.start_stage(context, "brief-development")
                self.assertNotEqual(first.stages_path, second.stages_path)
                for context in (first, second):
                    for shot in studio.discover_shots(context):
                        self.assertTrue((self.root / f"decisions/select-{shot.shot_id}.json").is_file())
                selections = json.loads((self.root / "selection.json").read_text())["selections"]
                self.assertEqual(set(selections), {"s001_sh010", "s002_sh010", "s003_sh010"})

    def test_foreign_selection_and_stale_context_cannot_change_unit_state(self):
        first = self.context()
        self.select_shots(first)
        shot = studio.discover_shots(first)[0]
        subject = f"{shot.directory}/{shot.shot_id}_t01_v01.mp4"
        decision = self.decision(first, subject, "foreign", shot=shot.shot_id)
        decision["context"] = self.context("ep002").identity()
        before = (self.root / shot.manifest).read_bytes()
        with self.assertRaises(ValueError):
            studio.record_selection(first, shot.shot_id, decision)
        self.assertEqual((self.root / shot.manifest).read_bytes(), before)
        first.unit_brief.write_text("# Changed first episode\n")
        with self.assertRaisesRegex(ValueError, "Stale"):
            studio.sync(first)

    def test_changed_brief_reopens_only_its_ledger_with_history(self):
        first, second = self.context(), self.context("ep002")
        studio.init_studio(first)
        studio.start_stage(first, "brief-development")
        studio.complete_stage(first, "brief-development")
        old = first.stages_path.read_bytes()
        first.unit_brief.write_text("# Revised episode\n")
        current = self.context()
        with self.assertRaisesRegex(ValueError, "context"):
            studio.read_stages(current)
        studio.reopen_stage(current, "brief-development")
        self.assertEqual(studio.read_stages(current)["context"], current.identity())
        histories = list((current.studio_root / "stage-history").glob("*.json"))
        self.assertEqual(len(histories), 1)
        self.assertEqual(histories[0].read_bytes(), old)
        self.assertTrue(all(entry["status"] == "pending"
                            for entry in studio.read_stages(second)["stages"]))

    def test_sync_does_not_overwrite_a_concurrent_manual_timeline_edit(self):
        context = self.context()
        studio.sync(context)
        shot = studio.discover_shots(context)[0]
        self.write(f"{shot.directory}/take.mp4", "synthetic")
        index = context.studio_root / "index.html"
        def probe(_):
            index.write_text(index.read_text() + "<!-- concurrent edit -->")
            return 2
        with self.assertRaisesRegex(ValueError, "changed during"):
            studio.sync(context, {shot.shot_id: "take.mp4"}, probe=probe)
        self.assertTrue(index.read_text().endswith("<!-- concurrent edit -->"))

    def test_sync_preserves_editor_changes_during_audio_probe(self):
        context = self.context()
        studio.sync(context)
        shot = studio.discover_shots(context)[0]
        self.write(f"{shot.directory}/take.mp4", "synthetic")
        for name in ("index.html", "STORYBOARD.md", f"compositions/{shot.shot_id}.html"):
            with self.subTest(name=name):
                target = context.studio_root / name
                before = target.read_text() if target.exists() else ""
                def audio_probe(_, target=target, before=before):
                    target.write_text(before + "\n<!-- concurrent editor change -->")
                    return False
                with (
                    patch.object(studio, "probe_has_audio", side_effect=audio_probe),
                    self.assertRaisesRegex(ValueError, "changed during"),
                ):
                    studio.sync(context, {shot.shot_id: "take.mp4"}, probe=lambda _: 2)
                self.assertEqual(target.read_text(), before + "\n<!-- concurrent editor change -->")
                if before:
                    target.write_text(before)
                else:
                    target.unlink()

    def test_stored_decisions_use_full_validation_without_rejecting_existing_ids(self):
        first = self.context()
        self.select_shots(first)
        service = studio.selection_service()
        with patch.object(service, "validated_decision", wraps=service.validated_decision) as validate:
            self.assertTrue(studio.status(first)["ok"])
        self.assertTrue(validate.call_args_list)
        self.assertTrue(all(call.kwargs.get("allow_existing") for call in validate.call_args_list))

    def test_place_preserves_storyboard_edit_during_take_probe(self):
        context = self.context()
        self.select_shots(context)
        shot = studio.discover_shots(context)[0]
        self.write(f"{shot.directory}/take.mp4", "new synthetic take")
        storyboard = context.studio_root / "STORYBOARD.md"
        original = storyboard.read_text()
        composition = context.studio_root / f"compositions/{shot.shot_id}.html"
        old_composition = composition.read_bytes()
        def probe(_):
            storyboard.write_text(original + "\nMy new editorial note\n")
            return 2
        with self.assertRaisesRegex(ValueError, "changed during"):
            studio.place_take(context, shot.shot_id, "take.mp4", probe=probe)
        self.assertEqual(storyboard.read_text(), original + "\nMy new editorial note\n")
        self.assertEqual(composition.read_bytes(), old_composition)

    def test_picture_lock_cannot_approve_render_from_an_old_edit(self):
        context = self.context()
        self.select_shots(context)
        record = studio.render(context, "cut", "draft", self.runner)
        output = json.loads(record.read_text())["output"]["path"]
        index = context.studio_root / "index.html"
        index.write_text(index.read_text() + "<!-- revised edit -->")
        self.assertIsNotNone(studio.lock_subject_problem(context, "picture", output))

    def test_native_audio_requires_audio_lock_even_when_preparation_was_skipped(self):
        context = self.context()
        self.finish_unit(context, "agent")
        service = studio.selection_service()
        for stage in ("assembly-review", "delivery"):
            with (
                self.subTest(stage=stage),
                patch.object(service, "probe_media_streams", return_value={"video", "audio"}),
                self.assertRaisesRegex(ValueError, "audio lock is required"),
            ):
                studio.complete_stage(context, stage, self.runner)
        studio.reopen_stage(context, "assembly-review")
        audio = "units/ep001/studio/renders/mix.wav"
        self.write(audio, "synthetic reviewed audio")
        with patch.object(service, "probe_media_streams", return_value={"video", "audio"}):
            studio.record_lock(context, self.decision(
                context, "units/ep001/studio/renders/cut.mp4", "native-picture", kind="picture",
            ))
            studio.record_lock(context, self.decision(context, audio, "native-audio", kind="audio"))
            studio.complete_stage(context, "assembly-review", self.runner)
            studio.start_stage(context, "delivery")
            studio.record_lock(context, self.decision(
                context, "units/ep001/studio/renders/master.mp4", "native-final", kind="final_master",
            ))
            studio.complete_stage(context, "delivery", self.runner)
        self.assertEqual(studio.read_stages(context)["stages"][-1]["status"], "complete")

    def test_unknown_scoped_streams_cannot_be_treated_as_silent(self):
        context = self.context()
        self.finish_unit(context, "agent")
        service = studio.selection_service()
        with patch.object(service, "probe_media_streams", return_value=set()):
            failures, _ = studio.stage_gate(context, "assembly-review", self.runner)
        self.assertTrue(any("stream" in failure for failure in failures), failures)

    def test_audio_added_in_render_requires_lock_even_when_placed_takes_are_silent(self):
        context = self.context()
        self.finish_unit(context, "agent")
        service = studio.selection_service()
        def streams(path):
            return {"video", "audio"} if path.parent.name == "renders" else {"video"}
        with patch.object(service, "probe_media_streams", side_effect=streams):
            failures, _ = studio.stage_gate(context, "delivery", self.runner)
        self.assertTrue(any("audio lock is required" in failure for failure in failures), failures)


if __name__ == "__main__":
    unittest.main()
