import shlex
import sys
import unittest
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents/skills"
sys.path.insert(0, str(ROOT / ".agents/scripts"))

import studio_project


def read_document(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class CinemaRoutingTests(unittest.TestCase):
    def test_narrative_and_unspecified_formats_route_to_available_orchestrator(self):
        for path in (
            ".agents/contracts/routing.md",
            ".agents/skills/hyperframes/SKILL.md",
        ):
            document = read_document(path)
            for intent in (
                "Cinematic short, film, episodic show, or custom narrative production",
                "Unspecified production format",
            ):
                with self.subTest(path=path, intent=intent):
                    row = next(
                        (line for line in document.splitlines() if f"| {intent} |" in line),
                        "",
                    )
                    self.assertIn("`film-production`", row)
                    self.assertNotIn("general-video", row)
                    self.assertTrue((SKILLS / "film-production/SKILL.md").is_file())

    def test_explicit_microdrama_keeps_its_available_workflow(self):
        for path in (
            ".agents/contracts/routing.md",
            ".agents/skills/hyperframes/SKILL.md",
        ):
            with self.subTest(path=path):
                document = read_document(path)
                row = next(
                    (
                        line
                        for line in document.splitlines()
                        if "| Explicit micro-drama format |" in line
                    ),
                    "",
                )
                self.assertIn("`micro-drama`", row)
        self.assertTrue((SKILLS / "micro-drama/SKILL.md").is_file())
        microdrama = read_document(".agents/skills/micro-drama/SKILL.md")
        self.assertIn("microdrama-story-formats", microdrama)
        self.assertIn("to-be-continued card", microdrama)

    def test_hyperframes_overlay_precedes_upstream_state_and_intake(self):
        document = read_document(".agents/skills/hyperframes/SKILL.md")
        self.assertIn("## Workspace production routing", document)
        self.assertLess(
            document.index("## Workspace production routing"),
            document.index("## 1. Start from project state"),
        )
        self.assertNotRegex(document, r"\|\s*[^|\n]*\|\s*`/general-video`")
        self.assertNotIn("always executes in `/general-video`", document)
        self.assertNotIn("`/general-video` +", document)
        self.assertIn("Do not install `general-video`", document)

    def test_general_defaults_follow_script_not_episode_formula(self):
        document = read_document(
            ".agents/skills/film-production/references/production-defaults.md"
        )
        self.assertIn("## 3. Structure from the confirmed brief", document)
        self.assertNotIn("default Hook, Turn and Cliffhanger", document)
        self.assertIn("Only an explicit micro-drama", document)
        self.assertIn("held shots", document)
        self.assertIn("Wordless work", document)
        self.assertNotIn("overlays, end card and mix only", document)

    def test_brief_and_profile_contracts_are_shared_references(self):
        for path in (
            "README.md",
            "AGENTS.md",
            ".agents/contracts/routing.md",
            ".agents/skills/film-production/SKILL.md",
            ".agents/skills/brief-intake/SKILL.md",
        ):
            with self.subTest(path=path):
                document = read_document(path)
                self.assertIn("production-brief.md", document)
                self.assertIn("production-profiles.json", document)
        intake = read_document(".agents/skills/brief-intake/SKILL.md")
        self.assertIn("Format, genre, medium, audience, language and delivery", intake)
        self.assertIn("project.md", intake)
        self.assertIn("not a second editable brief", intake)

    def test_readiness_describes_supported_units_without_automatic_migration(self):
        for path in ("README.md", "AGENTS.md"):
            with self.subTest(path=path):
                document = " ".join(read_document(path).split())
                self.assertIn("Seed Cinema Studio", document)
                self.assertIn("validated `production.json`", document)
                self.assertIn("units/<unit>/studio/", document)
                self.assertIn("--unit", document)
                self.assertIn("no automatic migration", document.lower())
                self.assertIn("no automatic repository or checkout rename", document.lower())
                self.assertIn("not creative-pilot approval", document)
                self.assertIn("synthetic decision fixtures", document)
                self.assertIn("Feature-length readiness requires measured trials", document)
                self.assertNotIn("Unit-scoped production is not enabled", document)
                self.assertIn("studio_project.py", document)
                self.assertIn("projects/", document)
        agents = read_document("AGENTS.md")
        self.assertIn("Only for an explicit micro-drama", agents)
        self.assertTrue((ROOT / "CLAUDE.md").is_symlink())

    def test_documented_forwarding_commands_select_unit_before_project(self):
        examples = (
            (
                "studio_project.py hf --unit ep001 PROJECT preview --no-open --json",
                ["preview", "--no-open", "--json"],
            ),
            (
                "studio_project.py record-render --unit ep001 PROJECT FILE ...",
                ["..."],
            ),
        )
        document = " ".join(read_document("README.md").split())
        for command, forwarded in examples:
            with self.subTest(command=command):
                self.assertIn(f"`{command}`", document)
                parsed = studio_project.build_parser().parse_args(shlex.split(command)[1:])
                self.assertEqual(parsed.unit, "ep001")
                self.assertEqual(parsed.project, Path("PROJECT"))
                self.assertEqual(parsed.hyperframes_arguments, forwarded)

    def test_scoped_contracts_do_not_retain_disabled_foundation_claims(self):
        for path in (
            ".agents/contracts/production-policy.md",
            ".agents/contracts/production-versions.md",
            ".agents/contracts/production-brief.md",
            ".agents/contracts/routing.md",
            ".agents/skills/film-production/SKILL.md",
            ".agents/skills/hyperframes/SKILL.md",
        ):
            with self.subTest(path=path):
                document = " ".join(read_document(path).split())
                self.assertIn("production.json", document)
                for obsolete in (
                    "unit-scoped production are not enabled",
                    "Unit-scoped production is not enabled",
                    "all scoped operations are disabled",
                    "New unit layouts remain inactive",
                    "Active manifests are rejected during",
                    "adapters and independent unit stages remain disabled",
                    "unit-scoped production are deferred",
                ):
                    self.assertNotIn(obsolete, document)

    def test_general_capabilities_have_explicit_routes_and_legacy_entries_remain(self):
        capabilities = (
            "story-development", "series-continuity", "editorial-review",
            "sound-post", "subtitle-sidecars", "production-localize",
        )
        for path in (
            "README.md",
            ".agents/contracts/routing.md",
            ".agents/skills/film-production/SKILL.md",
        ):
            with self.subTest(path=path):
                document = read_document(path)
                for name in capabilities:
                    self.assertIn(name, document)
                    self.assertTrue((SKILLS / name / "SKILL.md").is_file())
        for name in ("microdrama-subtitles", "microdrama-localize"):
            self.assertIn(name, read_document(".agents/contracts/routing.md"))
            self.assertTrue((SKILLS / name / "SKILL.md").is_file())

    def test_skill_frontmatter_remains_loadable_and_identifies_orchestrators(self):
        for name in ("film-production", "brief-intake", "hyperframes"):
            with self.subTest(name=name):
                document = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
                frontmatter = document.split("---", 2)[1]
                metadata = YAML(typ="safe").load(frontmatter)
                self.assertEqual(metadata["name"], name)
                self.assertIsInstance(metadata["description"], str)
                self.assertTrue(metadata["description"].strip())
                self.assertNotIn(": ", metadata["description"])
                if name != "brief-intake":
                    self.assertRegex(metadata["description"].lower(), r"orchestrat")


if __name__ == "__main__":
    unittest.main()
