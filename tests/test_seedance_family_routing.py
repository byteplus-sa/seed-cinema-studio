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

    def test_versioned_adapters_keep_exact_ids_and_neutral_relationship(self):
        for version, identifier in (
            ("20", "dreamina-seedance-2-0-260128"),
            ("25", "dreamina-seedance-2-5-260628"),
        ):
            text = (ROOT / f"seedance-prompt-{version}/SKILL.md").read_text()
            self.assertIn(identifier, text)
            self.assertIn("`seedance-prompt`", text)

    def test_review_resolves_model_and_operation_before_genre(self):
        text = (ROOT / "prompt-review/references/checklist-seedance-25.md").read_text()
        self.assertIn("selected model and operation", text)
        self.assertIn("before genre or language", text)
        self.assertIn("standard", text)
        self.assertIn("Premium", text)
        self.assertNotIn("where native Draft is unavailable", text)


if __name__ == "__main__":
    unittest.main()
