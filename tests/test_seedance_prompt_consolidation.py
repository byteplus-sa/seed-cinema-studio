import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents/skills"
PROMPT = SKILLS / "seedance-prompt"
RETIRED = ("seedance-prompt-20", "seedance-prompt-25")
sys.path.insert(0, str(ROOT / ".agents/scripts"))

import sync_catalog
import validate_workspace


class SeedancePromptConsolidationTests(unittest.TestCase):
    def test_only_general_prompt_entrypoint_and_alias_remain(self):
        for name in RETIRED:
            with self.subTest(skill=name):
                self.assertFalse((SKILLS / name).exists())
                self.assertFalse((ROOT / ".claude/skills" / name).is_symlink())
        for name in ("seedance-prompt", "seedance-prompt-25-dialogue",
                     "seedance-prompt-25-filipino"):
            alias = ROOT / ".claude/skills" / name
            self.assertTrue(alias.is_symlink())
            self.assertEqual(alias.resolve(), SKILLS / name)
            self.assertTrue((alias / "SKILL.md").is_file())

    def test_active_catalogs_and_rule_owners_resolve_consolidated_skill(self):
        for relative in ("skills-lock.json", ".agents/catalog/skills.json"):
            skills = json.loads((ROOT / relative).read_text())["skills"]
            self.assertIn("seedance-prompt", skills)
            self.assertFalse(set(RETIRED) & set(skills))
        rules = json.loads((ROOT / ".agents/contracts/rules.json").read_text())["rules"]
        for rule in rules:
            self.assertTrue((ROOT / rule["owner_path"]).is_file(), rule["id"])
            self.assertFalse(set(RETIRED) & set(Path(rule["owner_path"]).parts))

    def test_public_metadata_describes_unified_composition_and_editing(self):
        catalog = json.loads((ROOT / ".agents/catalog/skills.json").read_text())
        entry = catalog["skills"]["seedance-prompt"]
        metadata, findings = validate_workspace.validate_skill(PROMPT / "SKILL.md")
        self.assertEqual(findings, [])
        self.assertEqual(entry["description"], metadata["description"])
        ui = validate_workspace.YAML(typ="safe").load(
            (PROMPT / "agents/openai.yaml").read_text()
        )["interface"]
        for text in (entry["readme_summary"], ui["default_prompt"]):
            with self.subTest(text=text):
                for concept in ("2.5-based", "compos", "reference", "edit", "extension"):
                    self.assertIn(concept, text)
        row = f'| **seedance-prompt** | {entry["readme_summary"]} |'
        self.assertEqual((ROOT / "README.md").read_text().count(row), 1)
        for text in (entry["description"], ui["default_prompt"], ui["short_description"]):
            self.assertNotIn("media execution, source-video edits", text)
        self.assertIn("edit", ui["short_description"])
        self.assertIn("extension", ui["short_description"])

    def test_all_mode_references_and_historical_evals_survive(self):
        references = {
            "audio-performance-camera", "keyframes-storyboards-blockouts",
            "parameter-reference", "reference-inputs", "repair-examples",
            "scene-action", "shot-staging", "transitions-and-one-click",
            "video-editing", "video-extension", "worked-examples", "model-boundaries",
        }
        self.assertTrue(references <= {
            path.stem for path in (PROMPT / "references").glob("*.md")
        })
        cases = validate_workspace.load_evaluations(PROMPT / "evals/evals.json")
        self.assertEqual(len(cases), 31)
        self.assertEqual(len({case["id"] for case in cases}), 31)
        self.assertTrue(set(range(1, 13)) <= {case["id"] for case in cases})
        self.assertTrue(set(range(101, 107)) <= {case["id"] for case in cases})
        self.assertTrue(set(range(301, 314)) <= {case["id"] for case in cases})
        creative = validate_workspace.load_evaluations(PROMPT / "evals/creative-freedom.json")
        self.assertEqual({case["id"] for case in creative}, set(range(201, 211)))
        for path in (PROMPT / "evals").glob("*.json"):
            self.assertEqual(json.loads(path.read_text())["skill_name"], "seedance-prompt")

    def test_callers_do_not_route_to_retired_names_or_invent_adapters(self):
        pattern = re.compile(r"(?<![\w-])seedance-prompt-(?:20|25)(?![\w-])")
        documents = [ROOT / "AGENTS.md", ROOT / "README.md"]
        documents += list((ROOT / ".agents/contracts").glob("*.md"))
        documents += list(SKILLS.rglob("*.md"))
        for path in documents:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(pattern.search(path.read_text()), str(path))
        for relative in ("AGENTS.md", ".agents/contracts/routing.md",
                         ".agents/contracts/seedance-execution-profiles.md"):
            self.assertNotRegex(
                (ROOT / relative).read_text(),
                r"retained 2\.0/2\.5 (?:entrypoints|adapters)|applicable versioned adapter",
            )

    def test_source_edit_guidance_preserves_fractional_timing_and_audio_tails(self):
        for name in ("video-editing", "video-extension"):
            text = (PROMPT / f"references/{name}.md").read_text().lower()
            with self.subTest(reference=name):
                for concept in ("fractional", "audio tails", "approval", "unresolved"):
                    self.assertIn(concept, text)
                self.assertNotIn("approximately preserves duration", text)
        parameters = (PROMPT / "references/parameter-reference.md").read_text()
        self.assertNotIn("### Cost ladder", parameters)
        self.assertNotIn("### When to use Seedance 2.0 instead of 2.5", parameters)
        for concept in ("draft_ledger.py", "registry", "expiry", "promotion"):
            self.assertIn(concept, parameters)

    def test_legacy_review_checks_behavior_without_required_templates(self):
        path = SKILLS / "prompt-review/references/checklist-seedance-legacy.md"
        text = " ".join(path.read_text().split())
        for obsolete in (
            "label is reused in every shot",
            "**Task type declared.** One of:",
            "**Per-shot description order.**",
            "**Spatial map present.** Same 6-field format",
        ):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, text)
        for concept in ("ordered", "provisional", "approval", "fractional", "audio tails"):
            self.assertIn(concept, text)

    def test_review_does_not_infer_input_support_or_count_quotas(self):
        review = SKILLS / "prompt-review/references"
        generation = " ".join((review / "checklist-seedance-25.md").read_text().split())
        edits = " ".join((review / "checklist-seedance-edits.md").read_text().split())
        self.assertNotIn("use the full sheet or a first frame", generation)
        self.assertNotIn("A last-frame-only request is rejected", generation)
        self.assertNotIn("More than eight mapped subjects", edits)
        self.assertNotIn('`[Edit Goal] Edit @Video 1 …` present and one-sentence', edits)
        for text in (generation, edits):
            self.assertIn("unresolved", text)
            self.assertIn("authorization", text)
            self.assertIn("exact", text)

    def test_migrated_evals_check_semantics_and_conditional_controls(self):
        cases = {
            case["id"]: case
            for case in validate_workspace.load_evaluations(PROMPT / "evals/evals.json")
        }
        self.assertNotIn("follows the 5-step workflow", cases[302]["expected_output"])
        self.assertNotIn(
            "includes a [Timeline Inheritance] section",
            " ".join(cases[303]["assertions"]),
        )
        for identifier in (305, 309, 313):
            text = " ".join(cases[identifier]["assertions"]).lower()
            with self.subTest(case=identifier):
                self.assertIn("verified", text)
                self.assertIn("unresolved", text)

    def test_dialogue_list_does_not_establish_exact_model_support(self):
        path = SKILLS / "seedance-prompt-25-dialogue/references/language-support.md"
        text = " ".join(path.read_text().split())
        self.assertIn("historical", text)
        self.assertIn("exact model", text)
        self.assertIn("unresolved", text)
        self.assertIn("approved words", text)
        self.assertNotIn("Language is on the list | Native audio", text)
        self.assertNotIn("Keep the unsupported words short", text)

    def test_keyframe_guidance_does_not_promote_board_derivatives(self):
        path = PROMPT / "references/keyframes-storyboards-blockouts.md"
        text = " ".join(path.read_text().split()).lower()
        self.assertIn("planning origin", text)
        self.assertIn("independently authored", text)
        self.assertNotIn("generate a clean keyframe in the final medium", text)

    def test_sync_rejects_retired_skill_even_with_matching_catalogs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".agents/catalog").mkdir(parents=True)
            (root / ".agents/skills").mkdir()
            for name in RETIRED:
                path = root / ".agents/skills" / name / "SKILL.md"
                path.parent.mkdir()
                path.write_text(f"---\nname: {name}\ndescription: Retired fixture.\n---\n")
            (root / "skills-lock.json").write_text(json.dumps({
                "skills": {name: {"sourceType": "local"} for name in RETIRED}
            }))
            (root / ".agents/catalog/skills.json").write_text(json.dumps({
                "skills": {name: {"readme_summary": "Retired fixture."} for name in RETIRED}
            }))
            (root / "README.md").write_text(
                "".join(f"| **{name}** | Retired fixture. |\n" for name in RETIRED)
            )
            (root / "AGENTS.md").write_text("")
            with self.assertRaisesRegex(ValueError, "retired"):
                sync_catalog.desired_outputs(root, refresh_integrity=False)
            (root / ".agents/catalog/integrity.json").write_text(json.dumps({
                "files": validate_workspace.bundle_hashes(root),
            }))
            (root / ".agents/contracts").mkdir()
            (root / ".agents/contracts/rules.json").write_text('{"rules": []}')
            portable = {
                str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
            }
            _, findings = validate_workspace.validate_workspace(root, portable)
            self.assertEqual(
                {finding.path for finding in findings if finding.rule_id == "catalog.retired_skill"},
                set(RETIRED),
            )

    def test_dangling_retired_aliases_cannot_be_synchronized(self):
        for location in (".claude/skills", ".agents/skills"):
            with self.subTest(location=location):
                self.check_dangling_retired_links(location)

    def check_dangling_retired_links(self, location):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".agents/catalog").mkdir(parents=True)
            (root / ".agents/skills").mkdir()
            (root / ".claude/skills").mkdir(parents=True)
            for name in RETIRED:
                (root / location / name).symlink_to("missing-retired-bundle")
            for relative in ("skills-lock.json", ".agents/catalog/skills.json"):
                (root / relative).write_text('{"skills": {}}')
            (root / "README.md").write_text("")
            (root / "AGENTS.md").write_text("")
            with self.assertRaisesRegex(ValueError, "retired"):
                sync_catalog.desired_outputs(root, refresh_integrity=True)
            (root / ".agents/catalog/integrity.json").write_text('{"files": {}}')
            (root / ".agents/contracts").mkdir()
            (root / ".agents/contracts/rules.json").write_text('{"rules": []}')
            _, findings = validate_workspace.validate_workspace(root, set())
            self.assertEqual(
                {finding.path for finding in findings if finding.rule_id == "catalog.retired_skill"},
                set(RETIRED),
            )


if __name__ == "__main__":
    unittest.main()
