from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".agents/skills"
sys.path.insert(0, str(ROOT / ".agents/scripts"))

import evaluate_skill_quality as quality
import production_profiles
import validate_request


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split()).lower()


class CreativeDefaultsTests(unittest.TestCase):
    def test_compiler_and_review_do_not_soften_body_energy_by_default(self):
        for relative in (
            "seedance-prompt-25/references/scene-action.md",
            "prompt-review/references/checklist-seedance-legacy.md",
            "prompt-review/references/checklist-seedance-25.md",
        ):
            with self.subTest(path=relative):
                text = normalized(SKILLS / relative)
                self.assertNotRegex(text, r"prefer[s]? slow, gentle")
                self.assertNotIn("at most once per shot", text)
                self.assertIn("intent", text)

    def test_speech_is_a_readability_requirement_not_an_energy_cap(self):
        for relative in (
            "seedance-shot-design/SKILL.md",
            "seedance-shot-design/references/coverage-patterns.md",
            "seedance-prompt-25/references/shot-staging.md",
            "micro-drama/SKILL.md",
            "prompt-review/references/checklist-seedance-25.md",
        ):
            with self.subTest(path=relative):
                text = normalized(SKILLS / relative)
                self.assertNotRegex(
                    text,
                    r"only for shots without spoken lines|kinetic is for shots without"
                    r"|keep moves slow while|keep their moves quiet|large moves there are minor",
                )
                self.assertIn("readab", text)

    def test_shot_fields_do_not_require_timing_turn_or_wow_quotas(self):
        text = normalized(SKILLS / "seedance-shot-design/references/shot-plan-format.md")
        for forbidden in (
            "lengths are uneven", "`true` on exactly one shot",
            "`true` on one shot per clip", "each sequence has 2-3 shots",
        ):
            self.assertNotIn(forbidden, text)
        for field in ("turn", "wow"):
            self.assertRegex(text, rf"\| `{field}` \| optional")

    def test_review_rules_do_not_penalize_intentional_repetition(self):
        text = normalized(SKILLS / "prompt-review/references/checklist-seedance-25.md")
        self.assertNotIn("major when the clip repeats one framing", text)
        self.assertNotIn("at most one `performance_hold`", text)
        rules = json.loads((ROOT / ".agents/contracts/rules.json").read_text())["rules"]
        variety = next(rule for rule in rules if rule["id"] == "shot.variety")
        self.assertNotIn("at least two", variety["summary"])
        self.assertNotIn("uneven shot lengths", variety["summary"])

    def test_intake_resolves_attention_ending_and_early_sound_intent(self):
        text = normalized(SKILLS / "brief-intake/SKILL.md")
        for phrase in ("attention", "ending", "unresolved", "editorial intent"):
            self.assertIn(phrase, text)
        self.assertNotIn("propose a sequence structure: about six", text)

    def test_eval_expectations_do_not_restore_removed_quotas(self):
        for name in (
            "brief-intake", "film-production", "seedance-shot-design", "seedance-prompt-25",
        ):
            path = SKILLS / name / "evals/evals.json"
            for case in json.loads(path.read_text())["evals"]:
                with self.subTest(skill=name, case=case["id"]):
                    expectations = " ".join(
                        [case["expected_output"], *case.get("assertions", case.get("expectations", []))]
                    ).lower()
                    self.assertNotRegex(
                        expectations,
                        r"exactly one wow|flags one shot as the turn|"
                        r"shot lengths are uneven|plans about six 5 s|"
                        r"proposes about five or six|adjacent shots differ in at least two",
                    )

    def test_shot_density_estimates_are_not_request_or_rhythm_gates(self):
        for relative in (
            "film-production/references/stage-contracts.md",
            "film-production/references/production-defaults.md",
            "seedance-shot-design/SKILL.md",
            "seedance-shot-design/references/coverage-patterns.md",
            "seedance-shot-design/evals/evals.json",
            "seedance-pacing-presets/SKILL.md",
            "seedance-pacing-presets/references/assembly-cuts.md",
            "seedance-pacing-presets/references/cut-transitions.md",
            "seedance-pacing-presets/evals/evals.json",
            "seedance-prompt-25/SKILL.md",
            "seedance-prompt-20/SKILL.md",
            "seedance-prompt-25/references/shot-staging.md",
            "prompt-review/references/checklist-seedance-25.md",
            "prompt-review/references/checklist-seedance-legacy.md",
            "prompt-review/references/author-self-check.md",
            "template-factory/references/long-pins-and-multi-clip.md",
        ):
            with self.subTest(path=relative):
                text = normalized(SKILLS / relative)
                self.assertNotRegex(
                    text,
                    r"0\.8|shot ceiling|at most about (?:7|6.7)|"
                    r"more than about seven|at least ~1 second|"
                    r"generate each side as its own clip, never in one prompt|"
                    r"never demand impossible frequencies|4 tightly related shots|"
                    r"30s single-pass or native extension only for",
                )
                self.assertIn("provisional", text)

    def test_dialogue_timing_uses_delivery_and_response_not_fixed_quotas(self):
        paths = [ROOT / ".agents/contracts/rules.json"] + [
            SKILLS / relative for relative in (
                "seedance-shot-design/SKILL.md",
                "seedance-acting-console/SKILL.md",
                "seedance-prompt-25/references/shot-staging.md",
                "prompt-review/references/checklist-seedance-25.md",
                "prompt-review/references/checklist-seedance-legacy.md",
                "micro-drama/references/episode-structure.md",
                "micro-drama/references/production-recipe.md",
                "micro-drama/evals/evals.json",
                "film-production/references/production-defaults.md",
                "seedance-prompt-20/SKILL.md",
            )
        ]
        for path in paths:
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = normalized(path)
                self.assertNotRegex(text, r"0\.5.1\.5|0\.4 s|words / 2\.2 \+ 1")
                self.assertNotRegex(
                    text, r"(?:at most|no more than) two (?:visible )?state changes"
                    r"|avoid three state changes",
                )
                self.assertIn("provisional", text)
        rules = json.loads(paths[0].read_text())["rules"]
        rule = next(rule for rule in rules if rule["id"] == "dialogue.speech_budget")
        self.assertEqual(rule["severity"], "error")
        self.assertIn("required response", rule["summary"])

    def test_minimal_framing_and_compound_template_camera_remain_valid(self):
        text = normalized(SKILLS / "template-factory/references/slot-mapping.md")
        self.assertNotIn("\u22642 moves per shot", text)
        self.assertIn("coherent", text)
        text = normalized(SKILLS / "film-production/references/production-defaults.md")
        self.assertNotIn("and depth layers (foreground, subject, background)", text)
        self.assertIn("minimal framing", text)

    def test_behavioral_cases_cover_contrasting_intents_without_media_claims(self):
        path = ROOT / "tests/fixtures/creative_defaults_cases.json"
        self.assertTrue(path.is_file())
        cases = json.loads(path.read_text())["cases"]
        self.assertEqual(len(cases), 8)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertTrue(case["prompt"].strip())
                self.assertTrue(case["criteria"])
                self.assertTrue(case["walkthrough"].strip())
                self.assertEqual(case["evidence_status"], "hypothetical; no media generated")
                self.assertNotRegex(
                    case["walkthrough"], re.compile(r"proved improvement", re.IGNORECASE)
                )

    def test_supporting_references_preserve_blocking_and_readable_timing(self):
        checks = {
            "seedance-shot-design/references/framing.md": (
                "size follows importance", "stage the height difference",
                "at a lower or higher level than the foreground character",
            ),
            "seedance-camera-presets/SKILL.md": (
                "use only when the two characters are at different heights",
                "cover it with a shot of the looker before",
                "**at most 2 per shot.**",
            ),
            "scene-board-sheet/SKILL.md": ("the turn shot differs in length",),
            "seedance-pacing-presets/SKILL.md": (
                "slow the movement so the crossing takes about 1.5",
                "sequence bar plans it as about 5 s",
            ),
        }
        for relative, forbidden_phrases in checks.items():
            with self.subTest(path=relative):
                text = normalized(SKILLS / relative)
                for phrase in forbidden_phrases:
                    self.assertNotIn(phrase, text)

    def test_legacy_and_shared_summaries_do_not_restore_creative_gates(self):
        checks = {
            SKILLS / "seedance-prompt-20/SKILL.md": ("guide prefers slow",),
            ROOT / ".agents/contracts/seedance-reference.md": (
                "keep \u22642 moves per shot", "1\u20132 camera moves per shot",
            ),
            SKILLS / "micro-drama/evals/evals.json": (
                "using the three-scene structure", "uses three scene clips of about 15/20/15",
            ),
            SKILLS / "micro-drama/references/series-production.md": (
                "the ladder lists, per episode, the hook, the turn, the cliffhanger",
            ),
            SKILLS / "seedance-shot-design/evals/evals.json": (
                "the plan records which framing replaces it",
            ),
            ROOT / "tests/fixtures/creative_quality_shot_design_cases.json": (
                "each short shot has a distinct camera setup and move",
                "the clip's most emphasized moment",
            ),
        }
        for path, forbidden_phrases in checks.items():
            with self.subTest(path=str(path.relative_to(ROOT))):
                text = normalized(path)
                for phrase in forbidden_phrases:
                    self.assertNotIn(phrase, text)

    def test_walkthroughs_roundtrip_existing_blind_harness_without_approval(self):
        cases = json.loads(
            (ROOT / "tests/fixtures/creative_defaults_cases.json").read_text()
        )
        outputs = {"outputs": {case["id"]: case["walkthrough"] for case in cases["cases"]}}
        pack, key = quality.blind_pairs(cases, outputs, outputs, 28)
        self.assertEqual(len(pack["cases"]), 8)
        judgments = {
            "pack_sha256": quality.digest(pack),
            "cases": [
                {
                    "id": case["id"],
                    "ratings": {
                        label: {
                            "criteria": {
                                criterion: {
                                    "score": 2,
                                    "evidence": "Synthetic harness check only: " + case["walkthrough"],
                                }
                                for criterion in case["criteria"]
                            },
                            "hard_failures": [],
                        }
                        for label in ("A", "B")
                    },
                }
                for case in cases["cases"]
            ],
        }
        summary = quality.summarize(pack, key, judgments)
        self.assertEqual(summary["counts"]["tie"], 8)
        judgments["cases"][0]["ratings"]["A"]["hard_failures"] = [
            "Synthetic negative control: locked words were changed."
        ]
        judgments["cases"][0]["ratings"]["B"]["hard_failures"] = [
            "Synthetic negative control: required listener response was removed."
        ]
        self.assertEqual(quality.summarize(pack, key, judgments)["counts"]["neither"], 1)
        judgments["cases"][0]["ratings"]["A"]["criteria"] = {}
        with self.assertRaises(ValueError):
            quality.summarize(pack, key, judgments)

    def test_optional_microdrama_template_keeps_resolver_and_source_locks(self):
        general = production_profiles.resolve_brief({})
        self.assertNotIn("beats", general["production"])
        selected = production_profiles.resolve_brief({}, format_id="micro-drama")
        self.assertEqual(selected["production"]["beats"], ["hook", "turn", "cliffhanger"])
        source = {
            "production": {"scenes": [], "beats": []},
            "delivery": {"cards": [], "aspect": "16:9"},
            "locked": {"delivery.aspect": "16:9"},
            "approval_mode": "ask_for_approval",
        }
        before = json.dumps(source, sort_keys=True)
        resolved = production_profiles.resolve_brief(source, format_id="micro-drama")
        self.assertEqual(resolved["production"]["scenes"], [])
        self.assertEqual(resolved["production"]["beats"], [])
        self.assertEqual(resolved["delivery"]["cards"], [])
        self.assertEqual(resolved["approval_mode"], "ask_for_approval")
        self.assertEqual(json.dumps(source, sort_keys=True), before)
        with self.assertRaises(ValueError):
            production_profiles.resolve_brief(
                source, {"delivery": {"aspect": "9:16"}}, format_id="micro-drama"
            )

    def test_missing_or_failed_creative_review_evidence_is_not_a_pass(self):
        request_hash = "a" * 64
        review = {
            "schema_version": 1,
            "request_sha256": request_hash,
            "reviewer_status": "complete",
            "checks": [{
                "rule_id": "shot.variety",
                "status": "pass",
                "evidence": "Synthetic declaration: repeated wide holds preserve the requested waiting.",
            }],
        }
        self.assertEqual(validate_request.validate_review(review, request_hash, ["shot.variety"]), [])
        for status, evidence in (("fail", "Critical response hidden."), ("pass", ""), ("pass", " ")):
            review["checks"][0].update(status=status, evidence=evidence)
            self.assertTrue(validate_request.validate_review(review, request_hash, ["shot.variety"]))


if __name__ == "__main__":
    unittest.main()
