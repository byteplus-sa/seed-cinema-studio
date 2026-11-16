import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / ".agents/skills"


class FamilyRouting(unittest.TestCase):
    def test_general_craft_composes_with_neutral_leaf(self):
        for name in (
            "seedance-acting-console", "seedance-camera-presets",
            "seedance-fight-choreography", "seedance-lens-presets",
            "seedance-lighting-presets", "seedance-pacing-presets", "seedance-shot-design",
        ):
            with self.subTest(skill=name):
                text = (ROOT / name / "SKILL.md").read_text()
                self.assertIn("`seedance-prompt`", text)
                self.assertIn("selected model", text)

    def test_consolidated_parameter_reference_keeps_exact_ids_and_boundaries(self):
        text = (ROOT / "seedance-prompt/references/parameter-reference.md").read_text()
        for identifier in (
            "dreamina-seedance-2-0-260128",
            "dreamina-seedance-2-5-260628",
            "dreamina-seedance-2-5-premium-260915",
        ):
            self.assertIn(identifier, text)
        self.assertIn("historical", text)
        self.assertIn("`seedance-prompt`", text)
        self.assertIn("never", text.lower())

    def test_review_resolves_model_and_operation_before_genre(self):
        text = (ROOT / "prompt-review/references/checklist-seedance-25.md").read_text()
        self.assertIn("selected model and operation", text)
        self.assertIn("before genre or language", text)
        self.assertIn("standard", text)
        self.assertIn("Premium", text)
        self.assertNotIn("where native Draft is unavailable", text)


if __name__ == "__main__":
    unittest.main()
