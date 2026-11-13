import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / ".agents/skills"


class FamilyEvidence(unittest.TestCase):
    def test_optics_and_light_claims_are_scoped_not_family_guarantees(self):
        for path in (
            "seedance-lens-presets/SKILL.md", "seedance-lens-presets/references/optics-repairs.md",
            "seedance-lighting-presets/SKILL.md", "seedance-camera-presets/SKILL.md",
            "seedance-shot-design/SKILL.md", "seedance-prompt-25/references/audio-performance-camera.md",
        ):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                for term in ("model", "operation", "transport", "evidence"):
                    self.assertIn(term, text)
                self.assertIn("authorized", text)
                self.assertNotIn("whatever the focus wording", text)
                self.assertNotIn("timed cues are honoured closely", text)


if __name__ == "__main__":
    unittest.main()
