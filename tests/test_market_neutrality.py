import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents" / "skills"
MARKET_PACKS = {"filipino-micro-drama", "seedance-prompt-25-filipino"}
BIASED_TERMS = re.compile(
    r"\b(filipino|philippine|pinoy|tagalog|taglish|manila|morena|teleserye|"
    r"sampal|kabit|abangan|barong)\b",
    re.IGNORECASE,
)
ALLOWED_FILES = {
    SKILLS / "seedance-prompt-25" / "references" / "audio-performance-camera.md",
    SKILLS / "seedance-prompt-25" / "references" / "parameter-reference.md",
    SKILLS / "seedance-prompt-25-dialogue" / "references" / "language-support.md",
    SKILLS / "seedance-prompt-25-dialogue" / "references" / "market-pack-template.md",
    SKILLS / "microdrama-story-formats" / "references" / "market-adaptation.md",
    SKILLS / "film-production" / "SKILL.md",
    SKILLS / "prompt-review" / "SKILL.md",
    SKILLS / "prompt-review" / "references" / "review-checklists.md",
    SKILLS / "prompt-review" / "references" / "creative-quality.md",
    SKILLS / "micro-drama" / "SKILL.md",
    SKILLS / "showcase-html" / "scripts" / "portfolio.py",
    SKILLS / "seedream-prompt" / "references" / "image-generation.md",
    SKILLS / "seedream-prompt" / "references" / "quick-reference.md",
}
PACK_NAME = re.compile(r"(filipino-micro-drama|seedance-prompt-25-filipino)")


def generic_skill_files():
    for path in sorted(SKILLS.glob("*/**/*")):
        if not path.is_file() or path.suffix not in {".md", ".json", ".yaml", ".py"}:
            continue
        skill_name = path.relative_to(SKILLS).parts[0]
        if skill_name in MARKET_PACKS or path in ALLOWED_FILES:
            continue
        yield path


class MarketNeutralityTests(unittest.TestCase):
    def test_generic_skills_do_not_mention_a_specific_market(self):
        offenders = []
        for path in generic_skill_files():
            for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if BIASED_TERMS.search(PACK_NAME.sub("", line)):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
        self.assertEqual(offenders, [], "market-specific terms in generic skills")

    def test_market_card_reference_exists_and_forbids_assumed_market(self):
        card = (SKILLS / "micro-drama" / "references" / "market-card.md").read_text()
        self.assertIn("Never assume a market", card)
        self.assertIn("**optional**", card)
        self.assertIn("no built-in list and no default market", card)

    def test_micro_drama_entrypoint_links_the_market_card(self):
        entrypoint = (SKILLS / "micro-drama" / "SKILL.md").read_text()
        self.assertIn("references/market-card.md", entrypoint)


if __name__ == "__main__":
    unittest.main()
