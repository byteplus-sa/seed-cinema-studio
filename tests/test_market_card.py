import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))
import studio_project as studio
import validate_request as validation


class MarketCardTests(unittest.TestCase):
    def problems(self, metadata):
        return validation.market_card_problems(metadata)

    def test_absent_card_is_valid(self):
        self.assertEqual(self.problems({"approval_mode": "approve_for_me"}), [])

    def test_free_form_market_in_any_language_is_valid(self):
        metadata = {
            "market": {
                "country_region": "Kenya",
                "dialogue_languages": [{"language": "Swahili", "variety": "Nairobi"}],
                "subtitle_languages": ["English", "Swahili"],
                "content_limits": ["no weapons"],
            },
            "episode": {"count": 5, "duration_s": 90, "aspect": "16:9"},
        }
        self.assertEqual(self.problems(metadata), [])

    def test_partial_card_is_valid(self):
        self.assertEqual(self.problems({"market": {"platform": "any"}}), [])
        self.assertEqual(self.problems({"market": {}}), [])

    def test_malformed_blocks_are_reported(self):
        metadata = {
            "market": {
                "dialogue_languages": "Swahili",
                "subtitle_languages": "English",
            },
            "episode": {"duration_s": 0, "aspect": "vertical", "count": True},
        }
        found = " ".join(self.problems(metadata))
        for fragment in (
            "dialogue_languages",
            "subtitle_languages",
            "episode.duration_s",
            "episode.aspect",
            "episode.count",
        ):
            self.assertIn(fragment, found)

    def test_non_mapping_blocks_are_reported(self):
        self.assertEqual(
            self.problems({"market": "Kenya", "episode": [1]}),
            ["market must be a mapping", "episode must be a mapping"],
        )

    def test_brief_development_gate_ignores_absent_card_and_rejects_bad_card(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            project_file = project / "project.md"
            project_file.write_text("---\napproval_mode: approve_for_me\n---\n")
            failures, _ = studio.stage_gate(project, "brief-development", ledger={})
            self.assertEqual(failures, [])
            project_file.write_text(
                "---\napproval_mode: approve_for_me\nepisode:\n  aspect: tall\n---\n"
            )
            failures, _ = studio.stage_gate(project, "brief-development", ledger={})
            self.assertEqual(failures, ["episode.aspect must look like 9:16"])


if __name__ == "__main__":
    unittest.main()
