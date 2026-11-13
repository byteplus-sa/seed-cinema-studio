import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / ".agents/skills"


class FamilyContracts(unittest.TestCase):
    def test_restyle_review_preserves_fractional_source_and_denied_probe(self):
        text = (ROOT / "prompt-review/references/checklist-seedance-edits.md").read_text()
        self.assertIn("fractional", text)
        self.assertIn("explicit authorization", text)
        self.assertIn("optional", text)
        self.assertNotIn("whole-second source duration", text)
        self.assertNotIn("request is a 480p probe", text)

    def test_sound_ownership_is_not_inferred_from_absent_dialogue(self):
        for path in (
            "film-production/SKILL.md", "film-production/references/production-defaults.md",
            "template-factory/SKILL.md", "template-factory/references/slot-mapping.md",
        ):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertIn("wordless", text)
                self.assertIn("native", text)
                self.assertIn("exact master", text)
                self.assertIn("silence", text)
                self.assertNotIn("Native only for on-camera dialogue", text)

    def test_pacing_keeps_native_dialogue_without_authorizing_audio_generation(self):
        text = (ROOT / "seedance-pacing-presets/SKILL.md").read_text()
        self.assertIn("does not authorize", text)
        self.assertIn("supplied or explicitly authorized", text)
        self.assertNotIn("lip-sync-critical scenes pair", text)
        self.assertNotIn("with dialogue, generate Seed Audio first", text)

    def test_localization_separates_native_promotion_and_ordinary_preview(self):
        text = (ROOT / "microdrama-localize/references/routes.md").read_text()
        self.assertIn("draft_task_id", text)
        self.assertIn("non-promotable", text)
        self.assertIn("exact", text)

    def test_family_eval_covers_preservation_unknown_and_failure_paths(self):
        data = json.loads((ROOT / "prompt-review/evals/seedance-family.json").read_text())
        cases = " ".join(case["prompt"] for case in data["evals"])
        for term in ("12.48", "probe", "wordless", "unknown", "Premium", "silence"):
            self.assertIn(term, cases)


if __name__ == "__main__":
    unittest.main()
