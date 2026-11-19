from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents/scripts"))
sys.path.insert(0, str(ROOT / ".agents/skills/showcase-html/scripts"))

import portfolio
import studio_project as studio


class AudioPolicyTests(unittest.TestCase):
    def test_alignment_preserves_native_audio_without_finishing_work(self):
        text = (ROOT / ".agents/contracts/audio-video-alignment.md").read_text()
        self.assertIn("Native generated audio is sufficient unchanged", text)
        self.assertIn("explicitly requests or approves", text)
        self.assertIn("independent audio tails", text)
        self.assertIn("unavailable", text)
        self.assertNotIn("Normalize every delivered master", text)
        self.assertNotIn("pad short audio", text)

    def test_no_mandatory_carve_or_muted_source_policy(self):
        audio = (ROOT / ".agents/skills/hyperframes-audio/SKILL.md").read_text()
        self.assertNotIn("Carve by default", audio)
        self.assertNotIn("required whenever music plays under a voice", audio)
        self.assertIn("explicitly requested", audio)
        rules = json.loads((ROOT / ".agents/contracts/rules.json").read_text())
        self.assertNotIn("v2v.muted_source", json.dumps(rules))
        self.assertIn("v2v.audio_preservation", json.dumps(rules))

    def test_callers_and_evaluations_do_not_restore_removed_finishing_rules(self):
        forbidden = (
            "Normalize every delivered", "normalise delivery masters",
            "Carve by default", "required whenever music plays under a voice",
            "Submit the muted master", "v2v.muted_source",
            "Silent output. Sound is added in post.",
            "Dialogue fixes are word-scoped", "Audio fixes are word-scoped",
            "build the bed in post, because",
            "Silent footage or b-roll:", "Silent footage and b-roll:",
            "silent footage and b-roll is `muted",
            "add `muted` for silent footage or b-roll",
        )
        paths = [ROOT / "AGENTS.md"]
        for directory in ("contracts", "skills"):
            paths.extend((ROOT / ".agents" / directory).rglob("*.md"))
            paths.extend((ROOT / ".agents" / directory).rglob("*.json"))
        for path in paths:
            text = " ".join(path.read_text().split())
            for phrase in forbidden:
                with self.subTest(path=str(path.relative_to(ROOT)), phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_showreel_rejects_removed_processing_flags(self):
        for flag in ("--target-lufs", "--limit"):
            with self.subTest(flag=flag), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    portfolio.main(["out", "project", flag, "1"])
                self.assertEqual(error.exception.code, 2)

    def test_native_audio_never_requires_a_separate_mix_lock(self):
        for status in ("pending", "review", "complete", "skipped"):
            ledger = {"stages": [
                {"id": "audio-preparation", "status": status},
                {"id": "assembly-review", "locks": {}},
            ]}
            with self.subTest(status=status):
                self.assertEqual(studio.required_locks(ledger, "assembly-review"), ["picture"])

    def test_supplied_audio_locks_still_require_validation(self):
        ledger = {"stages": [
            {"id": "audio-preparation", "status": "skipped"},
            {"id": "assembly-review", "locks": {"audio": {"artifact_path": "mix.wav"}}},
        ]}
        self.assertEqual(studio.required_locks(ledger, "assembly-review"), ["picture", "audio"])
        self.assertEqual(studio.required_locks(ledger, "delivery"), ["final_master"])

    def test_audible_final_requires_listening_without_preparation_evidence(self):
        service = studio.selection_service()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "native.mp4").write_bytes(b"synthetic media")
            with (
                patch.object(service, "probe_media_streams", return_value={"video", "audio"}),
                self.assertRaisesRegex(ValueError, "listening"),
            ):
                service.validate_stage_media(
                    root, "final_master", "native.mp4", {"inspection_method": "playback"},
                )


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class ShowreelPreservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def clip(self, name, *, audio=True, audio_duration=1, volume=1):
        path = self.root / name
        command = [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            "color=black:size=72x128:rate=24:duration=1",
        ]
        if audio:
            command += [
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={audio_duration}",
                "-af", f"volume={volume}", "-c:a", "aac",
            ]
        subprocess.run([*command, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
        return {"slug": name, "master": path, "master_sha256": portfolio.sha256(path)}

    def packets(self, path):
        result = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "a", "-show_packets",
            "-show_data_hash", "sha256", "-show_entries", "packet=data_hash",
            "-of", "json", str(path),
        ], check=True, capture_output=True, text=True)
        return [packet["data_hash"] for packet in json.loads(result.stdout)["packets"]]

    def test_showreel_preserves_every_audio_packet_and_source_hash(self):
        entries = [
            self.clip("quiet 'source.mp4", volume=0.05),
            self.clip("loud.mp4", volume=0.5, audio_duration=1.25),
        ]
        expected = [packet for entry in entries for packet in self.packets(entry["master"])]
        output = self.root / "showreel.mp4"
        record = portfolio.build_showreel(entries, output)
        self.assertEqual(self.packets(output), expected)
        self.assertEqual(record["audio_processing"], "stream-copy")
        self.assertNotIn("target_lufs", record)
        self.assertNotIn("gain_db", record["inputs"][0])
        for entry in entries:
            self.assertEqual(portfolio.sha256(entry["master"]), entry["master_sha256"])
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"], check=True)

    def test_silent_inputs_remain_silent(self):
        entries = [self.clip("one.mp4", audio=False), self.clip("two.mp4", audio=False)]
        output = self.root / "silent.mp4"
        portfolio.build_showreel(entries, output)
        self.assertEqual(self.packets(output), [])

    def test_mixed_stream_layout_requires_explicit_editing(self):
        entries = [self.clip("sound.mp4"), self.clip("silent.mp4", audio=False)]
        output = self.root / "invalid.mp4"
        with self.assertRaisesRegex(ValueError, "compatible"):
            portfolio.build_showreel(entries, output)
        self.assertFalse(output.exists())

    def test_empty_missing_changed_and_alias_inputs_fail_without_overwriting(self):
        entry = self.clip("source.mp4")
        output = self.root / "invalid.mp4"
        for entries in ([], [{**entry, "master": self.root / "missing.mp4"}],
                        [{**entry, "master_sha256": "0" * 64}]):
            with self.subTest(entries=entries), self.assertRaises((ValueError, OSError)):
                portfolio.build_showreel(entries, output)
        with self.assertRaises(ValueError):
            portfolio.build_showreel([entry], entry["master"])
        self.assertEqual(portfolio.sha256(entry["master"]), entry["master_sha256"])
        self.assertFalse(output.exists())

    def test_missing_probe_is_not_permission_to_process_audio(self):
        entry = self.clip("source.mp4")
        with (
            patch.object(portfolio.subprocess, "run", side_effect=FileNotFoundError("ffprobe")),
            self.assertRaises(FileNotFoundError),
        ):
            portfolio.build_showreel([entry], self.root / "invalid.mp4")

    def test_invalid_stream_metadata_fails_before_rendering(self):
        entry = self.clip("source.mp4")
        for document in ([], {}, {"streams": []}, {"streams": [None]},
                         {"streams": [{"codec_type": "video"}]}):
            result = subprocess.CompletedProcess([], 0, json.dumps(document), "")
            with (
                self.subTest(document=document),
                patch.object(portfolio.subprocess, "run", return_value=result) as run,
                self.assertRaises(ValueError),
            ):
                portfolio.build_showreel([entry], self.root / "invalid.mp4")
            self.assertTrue(all(call.args[0][0] == "ffprobe" for call in run.call_args_list))

    def test_build_record_symlink_is_rejected_without_writing(self):
        entry = self.clip("source.mp4")
        target = self.root / "unrelated.json"
        (self.root / "showreel.json").symlink_to(target)
        with self.assertRaises(ValueError):
            portfolio.build_showreel([entry], self.root / "showreel.mp4")
        self.assertFalse(target.exists())
        self.assertFalse((self.root / "showreel.mp4").exists())


if __name__ == "__main__":
    unittest.main()
