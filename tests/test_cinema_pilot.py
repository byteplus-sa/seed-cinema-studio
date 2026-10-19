from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import editorial
import production_post
import studio_project as studio
from production_context import context_project_sha256, resolve_context
from production_profiles import resolve_brief
from validate_request import parse_frontmatter


@unittest.skipUnless(os.environ.get("STUDIO_SMOKE") == "1", "set STUDIO_SMOKE=1 for local render pilot")
class CinemaPilotTests(unittest.TestCase):
    def test_silent_landscape_short_renders_without_microdrama_structure(self):
        self.run_pilot(active=False)

    def test_scoped_render_and_named_binding_leave_second_episode_untouched(self):
        self.run_pilot(active=True)

    def run_pilot(self, *, active):
        with tempfile.TemporaryDirectory(prefix="seed-cinema-pilot-") as temporary:
            project = Path(temporary).resolve()
            brief = (
                "---\napproval_mode: approve_for_me\nproduction:\n"
                "  format: cinematic-short\n  genre: observational\n"
                "  medium: synthetic test footage\n  target_duration_s: 3\n"
                "delivery:\n  aspect: '16:9'\n  resolution: 360p\n  fps: 24\n"
                "  cards: []\nlocked:\n  audio_mode: silent\n---\n"
                "# A Quiet Return\n\nThree held views end with a resolved empty frame.\n"
                "This fixture verifies technical assembly, not creative quality.\n"
            )
            if active:
                brief = brief.replace("cinematic-short", "episodic-show")
            (project / "project.md").write_text(brief)
            effective = resolve_brief(parse_frontmatter(brief))
            self.assertEqual(effective["workflow"], "film-production")
            self.assertNotIn("beats", effective["production"])
            self.assertEqual(effective["delivery"]["cards"], [])
            originals = {}
            for scene_number, color in enumerate(("red", "green", "blue"), 1):
                scene = project / f"scenes/scene-{scene_number:03}"
                shot_id = f"s{scene_number:03}_sh010"
                directory = scene / shot_id
                directory.mkdir(parents=True)
                (scene / "scene.md").write_text(
                    f"# Held View {scene_number}\n\n"
                    "Static camera preserves the duration of an uninterrupted look.\n"
                )
                media = directory / f"{shot_id}_t01_v01.mp4"
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                     f"color=c={color}:s=640x360:r=24:d=1", "-an", "-c:v",
                     "libx264", "-pix_fmt", "yuv420p", str(media)],
                    check=True, capture_output=True, timeout=60,
                )
                digest = studio.sha256_file(media)
                originals[media] = digest
                selection = "active_take" if active else "selected_variant"
                state = "review" if active else "approved"
                (directory / "shot.md").write_text(
                    f"---\nshot_id: {shot_id}\nstatus: {state}\nduration_s: 1\n"
                    f"aspect: '16:9'\nresolution: 360p\n{selection}: {media.name}\n"
                    f"takes:\n- filename: {media.name}\n  sha256: {digest}\n"
                    "  duration_s: 1\n---\n# Held View\n\n"
                    "## Action\nA steady field holds without dialogue or titles.\n"
                )
            if active:
                self.prepare_units(project)
            context = resolve_context(project, "ep001" if active else None)
            studio.init_studio(context, "16:9", "360p")
            requested = {path.parent.name: path.name for path in originals} if active else None
            report = studio.sync(context, requested)
            self.assertEqual(report.added, ["s001_sh010", "s002_sh010", "s003_sh010"])
            if active:
                self.record_synthetic_selections(context)
            index = context.studio_root / "index.html"
            edited = index.read_text().replace(
                '<div id="s001_sh010"', '<div data-label="Preserved pilot label" id="s001_sh010"'
            )
            index.write_text(edited)
            studio.sync(context)
            self.assertEqual(index.read_text(), edited)
            checked = studio.run_hyperframes(context, ["check", "--json"])
            self.assertTrue(studio.check_passed(checked), checked.stdout + checked.stderr)
            sidecar = studio.render(context, "technical-pilot", "standard")
            record = json.loads(sidecar.read_text())
            output = project / record["output"]["path"]
            self.assertEqual(record["produced_by"], "render")
            self.assertEqual(record["output"]["sha256"], studio.sha256_file(output))
            video = next(
                stream for stream in record["output"]["probe"]["streams"]
                if stream["codec_type"] == "video"
            )
            self.assertEqual((video["width"], video["height"]), (640, 360))
            self.assertAlmostEqual(record["output"]["probe"]["duration_s"], 3, delta=0.1)
            decoded = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"],
                check=True, capture_output=True, timeout=60,
            )
            self.assertEqual(decoded.stderr, b"")
            self.assertEqual({path: studio.sha256_file(path) for path in originals}, originals)
            if active:
                self.verify_post_snapshot(context, edited)
                self.verify_named_binding(project, sidecar, context)
            else:
                self.assertFalse((project / "decisions").exists())
                self.assertFalse((project / "production.json").exists())
            self.assertFalse((project / "task_ids.json").exists())

    def verify_post_snapshot(self, context, studio_html):
        project = context.production_root
        relative = "editorial/ep001/snapshots/technical-v01.json"
        snapshot = editorial.export_edit(context, relative)
        self.assertEqual(editorial.check_edit(context, relative), [])
        record = json.loads(snapshot.read_text())
        self.assertEqual([entry["shot_id"] for entry in record["entries"]],
                         ["s001_sh010", "s002_sh010", "s003_sh010"])
        self.assertAlmostEqual(record["duration_s"], 3, delta=0.1)
        main = editorial.reconcile_edit(context, relative, expected_revision=None)
        cues = {
            "schema_version": 1, "unit_id": "ep001", "cut_id": "main",
            "duration_s": record["duration_s"],
            "edit": {"path": main.relative_to(project).as_posix(),
                     "sha256": studio.sha256_file(main)},
            "cues": [{"id": "silent-hold", "kind": "silence", "start_s": 0,
                      "end_s": record["duration_s"], "gain_db": 0,
                      "intent": "Intentional silent synthetic technical fixture."}],
            "listening": {"status": "not_applicable", "evidence": [],
                          "note": "FFmpeg sources and output contain no audio stream."},
        }
        self.assertEqual(production_post.validate_sound(project, cues, unit_id="ep001"), [])
        sound = project / "sound/ep001/cues.json"
        sound.parent.mkdir(parents=True)
        sound.write_text(json.dumps(cues))
        self.assertEqual((context.studio_root / "index.html").read_text(), studio_html)
        self.assertEqual(main.read_bytes(), snapshot.read_bytes())

    def prepare_units(self, project):
        units = []
        for number, scenes in ((1, ["scene-001", "scene-002", "scene-003"]),
                               (2, ["scene-004"])):
            unit_id = f"ep{number:03}"
            brief = project / f"units/{unit_id}/unit.md"
            brief.parent.mkdir(parents=True)
            brief.write_text(f"# Synthetic episode {number}\n")
            units.append({"id": unit_id, "kind": "episode",
                          "brief": brief.relative_to(project).as_posix(), "scene_ids": scenes})
        planned = project / "scenes/scene-004"
        planned.mkdir(parents=True)
        (planned / "scene.md").write_text("# Planned later episode\n")
        (project / "deliverables").mkdir()
        for identifier, kind in (("ep001-master", "master"), ("ep001-proxy", "proxy")):
            (project / f"deliverables/{identifier}.json").write_text(json.dumps({
                "schema_version": 1, "id": identifier, "unit_id": "ep001",
                "cut_id": "main", "kind": kind, "language": "und",
                "spec": {"width": 640, "height": 360, "fps": 24,
                         "audio": {"required": False}, "subtitles": []},
            }))
        (project / "production.json").write_text(json.dumps({
            "schema_version": 1, "format": "episodic-show", "units": units,
            "deliverables": [
                {"id": identifier, "unit_id": "ep001", "manifest": f"deliverables/{identifier}.json"}
                for identifier in ("ep001-master", "ep001-proxy")
            ],
        }))

    def record_synthetic_selections(self, context):
        project = context.production_root
        for shot in studio.discover_shots(context):
            filename = shot.active_take
            subject = studio.take_path(shot, filename)
            digest = studio.sha256_file(project / subject)
            review_path = project / f"review/{shot.shot_id}.json"
            review_path.parent.mkdir(exist_ok=True)
            review_path.write_text(json.dumps({
                "schema_version": 1, "artifact_path": subject, "artifact_sha256": digest,
                "status": "pass", "inspection_method": "Synthetic temporal inspection fixture",
                "coverage": "Synthetic color source only",
                "checks": [{"criterion": "fixture", "status": "pass",
                            "evidence": "FFmpeg generated the declared silent color source"}],
                "observations": ["Synthetic decision used to exercise scoped gates"],
                "limitations": ["Not creative approval or human playback evidence"],
                "recommendation": "Use only in this isolated technical test",
            }))
            studio.record_selection(context, shot.shot_id, {
                "schema_version": 2, "context": context.identity(),
                "decision_id": f"synthetic-{shot.shot_id}", "decision_type": "variant_selection",
                "asset_id": shot.shot_id, "subject_path": subject,
                "selected_variant": filename, "selected_sha256": digest,
                "actor": "agent", "approval_mode": "approve_for_me",
                "project_sha256": context_project_sha256(project), "result": "approved",
                "review_path": review_path.relative_to(project).as_posix(),
                "review_sha256": studio.sha256_file(review_path),
                "upstream_sha256": {
                    context.unit_brief.relative_to(project).as_posix():
                        studio.sha256_file(context.unit_brief),
                },
                "reason": "Synthetic test decision, not a production or creative approval",
                "decided_at": "2026-10-19T00:00:00Z",
            })

    def verify_named_binding(self, project, sidecar, context):
        import deliverables

        bindings = {}
        for identifier in ("ep001-master", "ep001-proxy"):
            spec = project / f"deliverables/{identifier}.json"
            result = deliverables.bind(
                project, identifier, sidecar, expected_revision=studio.sha256_file(spec),
            )
            self.assertTrue(result["ok"], result["findings"])
            self.assertIsNone(result["lock"])
            bindings[identifier] = spec.read_bytes()
        self.assertEqual((project / "deliverables/ep001-master.json").read_bytes(),
                         bindings["ep001-master"])
        self.assertEqual(json.loads(sidecar.read_text())["context"], context.identity())
        second = resolve_context(project, "ep002")
        self.assertFalse(second.studio_root.exists())
        self.assertTrue(all(stage["status"] == "pending"
                            for stage in studio.read_stages(second)["stages"]))
        self.assertFalse((project / "studio").exists())


if __name__ == "__main__":
    unittest.main()
