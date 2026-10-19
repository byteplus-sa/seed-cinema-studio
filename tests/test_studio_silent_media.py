from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import studio_project as studio


class StudioSilentMediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name).resolve()
        self.shot = self.project / "scenes/scene-001/s001_sh010"
        self.shot.mkdir(parents=True)
        (self.project / "project.md").write_text("---\napproval_mode: approve_for_me\n---\n")
        for name in ("silent.mp4", "audio.mp4"):
            (self.shot / name).write_bytes(name.encode())
        (self.shot / "shot.md").write_text(
            "---\nshot_id: s001_sh010\nduration_s: 1\naspect: '16:9'\n"
            "resolution: 360p\nselected_variant: silent.mp4\n"
            "takes:\n- filename: silent.mp4\n  duration_s: 1\n"
            "- filename: audio.mp4\n  duration_s: 1\n---\n# View\n"
        )
        self.composition = self.project / "studio/compositions/s001_sh010.html"

    def test_new_silent_frame_omits_audio_declaration(self):
        with patch.object(studio, "probe_has_audio", return_value=False):
            studio.sync(self.project, probe=lambda _: 1, size_probe=lambda _: (640, 360))
        self.assertIn('data-has-audio="false"', self.composition.read_text())

    def test_place_updates_audio_flag_and_preserves_manual_edit(self):
        with patch.object(studio, "probe_has_audio", return_value=False):
            studio.sync(self.project, probe=lambda _: 1, size_probe=lambda _: (640, 360))
        text = self.composition.read_text().replace("playsinline", 'data-custom="keep" playsinline')
        self.composition.write_text(text)
        with patch.object(studio, "probe_has_audio", return_value=True):
            studio.place_take(self.project, "s001_sh010", "audio.mp4", probe=lambda _: 1)
        self.assertIn('data-has-audio="true"', self.composition.read_text())
        self.assertIn('data-custom="keep"', self.composition.read_text())
        with patch.object(studio, "probe_has_audio", return_value=False):
            studio.place_take(self.project, "s001_sh010", "silent.mp4", probe=lambda _: 1)
        self.assertIn('data-has-audio="false"', self.composition.read_text())

    def test_unknown_audio_probe_preserves_legacy_default_with_warning(self):
        with patch.object(studio, "probe_has_audio", return_value=None):
            report = studio.sync(self.project, probe=lambda _: 1, size_probe=lambda _: (640, 360))
        self.assertIn('data-has-audio="true"', self.composition.read_text())
        self.assertTrue(any("audio" in warning for warning in report.warnings))

    def test_probe_distinguishes_silent_audio_and_unreadable_media(self):
        for streams, code, expected in (
            ([{"codec_type": "video"}], 0, False),
            ([{"codec_type": "video"}, {"codec_type": "audio"}], 0, True),
            ([], 1, None), ([], 0, None), (None, 0, None),
        ):
            with self.subTest(streams=streams, code=code):
                def runner(argv, code=code, streams=streams, **kwargs):
                    return subprocess.CompletedProcess(argv, code, json.dumps({"streams": streams}))
                self.assertIs(studio.probe_has_audio(self.shot / "silent.mp4", runner), expected)
        for error in (OSError("missing"), subprocess.TimeoutExpired("ffprobe", 1)):
            with self.subTest(error=error):
                def failed_runner(argv, error=error, **kwargs):
                    raise error
                self.assertIsNone(studio.probe_has_audio(self.shot / "silent.mp4", failed_runner))


if __name__ == "__main__":
    unittest.main()
