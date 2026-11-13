import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / ".agents/skills"


class StreamProfiles(unittest.TestCase):
    def test_conform_uses_measured_stream_not_model_name(self):
        for path in ("color-grade-palettes/SKILL.md", "film-production/references/production-defaults.md"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                for field in ("pix_fmt", "color_range", "color_primaries", "color_transfer", "color_space"):
                    self.assertIn(field, text)
                for scenario in ("unknown", "conflicting", "8-bit", "10-bit", "HDR"):
                    self.assertIn(scenario, text)
                self.assertIn("ffprobe", text)
                self.assertNotIn("Decode 10-bit HEVC finals as limited-range BT.709", text)


if __name__ == "__main__":
    unittest.main()
