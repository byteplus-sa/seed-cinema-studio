import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / ".agents/skills"


class StreamProfiles(unittest.TestCase):
    def test_conform_uses_measured_stream_not_model_name(self):
        for path in (
            "color-grade-palettes/SKILL.md", "film-production/references/production-defaults.md",
            "template-factory/references/long-pins-and-multi-clip.md",
        ):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                for field in ("pix_fmt", "color_range", "color_primaries", "color_transfer", "color_space"):
                    self.assertIn(field, text)
                for scenario in ("unknown", "conflicting", "8-bit", "10-bit", "HDR"):
                    self.assertIn(scenario, text)
                self.assertIn("ffprobe", text)
                self.assertNotIn("Decode 10-bit HEVC finals as limited-range BT.709", text)

    def test_multi_clip_delegate_distinguishes_measured_conform_scenarios(self):
        text = (ROOT / "template-factory/references/long-pins-and-multi-clip.md").read_text()
        scenarios = {
            "Matching 8-bit SDR": ("no forced", "tags"),
            "10-bit limited BT.709": ("matching 8-bit", "reduce", "dither once"),
            "Matching 10-bit target": ("keep", "bit depth", "no 8-bit"),
            "Full-range, different primaries/matrix or HDR": ("approved", "conversion", "tone mapping", "tagging alone"),
            "Missing, unknown or conflicting": ("stop", "authoritative", "inspection", "never assume"),
        }
        for scenario, clauses in scenarios.items():
            with self.subTest(scenario=scenario):
                rows = [line.lower() for line in text.splitlines() if line.startswith("| " + scenario)]
                self.assertEqual(len(rows), 1)
                for clause in clauses:
                    self.assertIn(clause, rows[0])
        self.assertIn("untouched master", text)
        self.assertIn("lossless intermediates", text)
        self.assertIn("codec name or 10-bit HEVC alone", text)


if __name__ == "__main__":
    unittest.main()
