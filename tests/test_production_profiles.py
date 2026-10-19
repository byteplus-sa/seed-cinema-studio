import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))
from production_profiles import load_profile, resolve_brief


class ProductionProfileTests(unittest.TestCase):
    def test_unspecified_format_uses_general_route_without_creative_defaults(self):
        brief = resolve_brief({})
        self.assertIsNone(brief["format"])
        self.assertEqual(brief["workflow"], "film-production")
        self.assertEqual(brief["production"], {})
        self.assertEqual(brief["delivery"], {})
        self.assertNotIn("market", brief)
        self.assertNotIn("episode", brief)

    def test_non_microdrama_profiles_do_not_impose_creative_defaults(self):
        for format_id in ("cinematic-short", "film", "episodic-show", "custom"):
            with self.subTest(format_id=format_id):
                brief = resolve_brief({}, format_id=format_id)
                self.assertEqual(brief["production"], {})
                self.assertEqual(brief["delivery"], {})
                self.assertTrue(brief["profile"]["planning_outputs"])

    def test_microdrama_requires_explicit_format_or_workflow(self):
        for arguments in ({"format_id": "micro-drama"}, {"workflow": "micro-drama"}):
            brief = resolve_brief({}, **arguments)
            self.assertEqual(brief["format"], "micro-drama")
            self.assertEqual(brief["delivery"]["aspect"], "9:16")
            self.assertEqual(brief["production"]["duration_range_s"], [45, 60])
            self.assertEqual(brief["production"]["beats"], ["hook", "turn", "cliffhanger"])
            self.assertEqual(brief["delivery"]["cards"], ["title", "to-be-continued"])
        self.assertIsNone(resolve_brief({"episode": {"count": 2}})["format"])

    def test_explicit_choices_override_microdrama_defaults(self):
        brief = resolve_brief(
            {
                "production": {"target_duration_s": 120, "beats": [], "scenes": []},
                "delivery": {"aspect": "239:100", "cards": []},
            },
            format_id="micro-drama",
        )
        self.assertEqual(brief["production"]["target_duration_s"], 120)
        self.assertNotIn("duration_range_s", brief["production"])
        self.assertEqual(brief["production"]["beats"], [])
        self.assertEqual(brief["production"]["scenes"], [])
        self.assertEqual(brief["delivery"]["cards"], [])
        self.assertEqual(brief["delivery"]["aspect"], "239:100")

    def test_arbitrary_genre_medium_and_optional_market_are_preserved(self):
        shared = {
            "production": {"genre": "experimental historical comedy", "medium": "ink on glass"},
            "market": {
                "country_region": "Kenya",
                "dialogue_languages": [{"language": "Swahili", "register": "casual"}],
                "subtitle_languages": [],
            },
        }
        brief = resolve_brief(shared, format_id="custom")
        self.assertEqual(brief["production"], shared["production"])
        self.assertEqual(brief["market"], shared["market"])

    def test_legacy_episode_maps_all_existing_fields_without_rewriting(self):
        episode = {
            "count": 5,
            "duration_s": 90,
            "aspect": "16:9",
            "scenes": [{"role": "opening", "duration_s": 30}],
            "max_recurring_cast": 4,
        }
        shared = {"episode": episode}
        before = copy.deepcopy(shared)
        brief = resolve_brief(shared)
        self.assertEqual(brief["episode"], episode)
        self.assertEqual(brief["production"], {
            "unit_count": 5,
            "target_duration_s": 90,
            "scenes": episode["scenes"],
            "max_recurring_cast": 4,
        })
        self.assertEqual(brief["delivery"]["aspect"], "16:9")
        self.assertEqual(shared, before)

    def test_equal_legacy_and_new_fields_are_allowed(self):
        brief = resolve_brief({
            "episode": {"duration_s": 90, "aspect": "16:9"},
            "production": {"target_duration_s": 90},
            "delivery": {"aspect": "16:9"},
        })
        self.assertEqual(brief["production"]["target_duration_s"], 90)

    def test_conflicting_legacy_fields_name_both_paths(self):
        for legacy, group, modern, old, new in (
            ("duration_s", "production", "target_duration_s", 90, 60),
            ("count", "production", "unit_count", 2, 3),
            ("aspect", "delivery", "aspect", "9:16", "16:9"),
            ("scenes", "production", "scenes", [], [{"role": "ending"}]),
            ("max_recurring_cast", "production", "max_recurring_cast", 3, 4),
        ):
            with (
                self.subTest(field=legacy),
                self.assertRaisesRegex(ValueError, rf"episode.{legacy}.*{group}.{modern}"),
            ):
                resolve_brief({"episode": {legacy: old}, group: {modern: new}})

    def test_manifest_format_mirrors_must_agree(self):
        self.assertEqual(
            resolve_brief({"production": {"format": "film"}}, format_id="film")["format"],
            "film",
        )
        for shared, unit in (
            ({"production": {"format": "micro-drama"}}, None),
            ({}, {"production": {"format": "micro-drama"}}),
            ({"format": "micro-drama"}, None),
        ):
            with self.assertRaisesRegex(ValueError, "format.*conflict"):
                resolve_brief(shared, unit, format_id="film")

    def test_legacy_explicit_format_wins_over_workflow_hint(self):
        brief = resolve_brief({"production": {"format": "film"}}, workflow="micro-drama")
        self.assertEqual(brief["format"], "film")
        self.assertEqual(brief["workflow"], "film-production")

    def test_unit_cannot_select_a_different_production_format(self):
        with self.assertRaisesRegex(ValueError, "format.*conflict"):
            resolve_brief(
                {"production": {"format": "film"}},
                {"production": {"format": "custom"}},
            )

    def test_unknown_profiles_and_workflows_fail_explicitly(self):
        for value in ("unknown", "", "../film", 4):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "format"):
                load_profile(value)
        with self.assertRaisesRegex(ValueError, "workflow"):
            resolve_brief({}, workflow="missing-workflow")

    def test_unit_creative_choices_override_shared_including_legacy_aliases(self):
        brief = resolve_brief(
            {"episode": {"duration_s": 60}, "delivery": {"aspect": "16:9", "fps": 24}},
            {"production": {"target_duration_s": 180}, "delivery": {"aspect": "239:100"}},
        )
        self.assertEqual(brief["production"]["target_duration_s"], 180)
        self.assertEqual(brief["delivery"], {"aspect": "239:100", "fps": 24})

    def test_return_values_are_independent_of_inputs_and_other_calls(self):
        shared = {"market": {"subtitle_languages": ["en"]}}
        unit = {"production": {"genre": "comedy"}}
        before = copy.deepcopy((shared, unit))
        brief = resolve_brief(shared, unit, format_id="micro-drama")
        brief["market"]["subtitle_languages"].append("fr")
        brief["profile"]["defaults"]["delivery"]["cards"].clear()
        self.assertEqual((shared, unit), before)
        self.assertTrue(load_profile("micro-drama")["defaults"]["delivery"]["cards"])
        profile = load_profile("micro-drama")
        profile["defaults"].clear()
        self.assertTrue(load_profile("micro-drama")["defaults"])

    def test_invalid_mapping_and_numeric_fields_fail(self):
        for shared in (
            None, [], {"production": []}, {"delivery": None}, {"market": "Kenya"},
            {"episode": []}, {"production": {"target_duration_s": True}},
            {"production": {"target_duration_s": float("nan")}},
            {"production": {"target_duration_s": float("inf")}},
            {"production": {"unit_count": 1.5}}, {"delivery": {"fps": 0}},
            {"delivery": {"aspect": "0:9"}}, {"delivery": {"aspect": "vertical"}},
            {"delivery": {"width": 1919, "height": 1080}},
            {"market": {"dialogue_languages": "English"}},
            {"approval_mode": "automatic"}, {"locked": []},
        ):
            with self.subTest(shared=shared), self.assertRaises(ValueError):
                resolve_brief(shared)

    def test_null_optional_market_and_episode_remain_compatible(self):
        brief = resolve_brief({"market": None, "episode": None})
        self.assertIsNone(brief["market"])
        self.assertIsNone(brief["episode"])

    def test_unit_cannot_replace_shared_authority_or_spending(self):
        for field, shared, unit in (
            ("approval_mode", "ask_for_approval", "approve_for_me"),
            ("rights", {"assets": ["a"]}, {"assets": ["a", "b"]}),
            ("budget", {"cap": 100, "confirmed": 30}, {"cap": 200}),
            ("budget", {"cap": 100, "confirmed": 30}, {"confirmed": 0}),
            ("approval", {"evidence": "accepted"}, {}),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                resolve_brief({field: shared}, {field: unit})
        with self.assertRaisesRegex(ValueError, "rights"):
            resolve_brief({}, {"rights": {"authorized": True}})

    def test_identical_unit_authority_is_allowed(self):
        shared = {"approval_mode": "ask_for_approval", "rights": {"assets": ["a"]}}
        self.assertEqual(resolve_brief(shared, copy.deepcopy(shared))["rights"], shared["rights"])

    def test_tighter_unit_allocation_keeps_shared_budget_totals(self):
        budget = {"cap": 100, "currency": "USD", "confirmed": 30, "unknown": 20}
        brief = resolve_brief({"budget": budget}, {"unit_budget": {"cap": 40, "currency": "USD"}})
        self.assertEqual(brief["budget"], budget)
        self.assertEqual(brief["unit_budget"]["cap"], 40)
        for allocation in (
            {"cap": 101}, {"cap": -1}, {"cap": True}, {"cap": 20, "currency": "EUR"},
            {"cap": 20, "confirmed": 0},
        ):
            with self.subTest(allocation=allocation), self.assertRaisesRegex(ValueError, "unit_budget"):
                resolve_brief({"budget": budget}, {"unit_budget": allocation})
        with self.assertRaisesRegex(ValueError, "budget.cap"):
            resolve_brief({}, {"unit_budget": {"cap": 10}})

    def test_unit_cannot_override_nested_or_dotted_locks(self):
        for locked in ({"delivery": {"aspect": "16:9"}}, {"delivery.aspect": "16:9"}):
            with self.subTest(locked=locked):
                shared = {"locked": locked, "delivery": {"aspect": "16:9"}}
                with self.assertRaisesRegex(ValueError, "locked.*delivery.aspect"):
                    resolve_brief(shared, {"delivery": {"aspect": "9:16"}})
                with self.assertRaisesRegex(ValueError, "locked"):
                    resolve_brief(shared, {"locked": {}})

    def test_lock_is_effective_when_value_was_not_repeated_in_brief(self):
        brief = resolve_brief({"locked": {"delivery.aspect": "16:9"}}, format_id="micro-drama")
        self.assertEqual(brief["delivery"]["aspect"], "16:9")

    def test_confirmed_directorial_axes_are_binding(self):
        for source in ("user_confirmed", "agent_confirmed"):
            shared = {"directorial_axes": {"audio_mode": {"value": "silent", "source": source}}}
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "directorial_axes.audio_mode"):
                resolve_brief(shared, {"directorial_axes": {"audio_mode": {"value": "native"}}})
        brief = resolve_brief(
            {"directorial_axes": {"energy": {"value": "restrained", "source": "proposed"}}},
            {"directorial_axes": {"energy": {"value": "kinetic", "source": "proposed"}}},
        )
        self.assertEqual(brief["directorial_axes"]["energy"]["value"], "kinetic")

    def test_legacy_axis_lock_cannot_be_bypassed_by_directorial_axis(self):
        with self.assertRaisesRegex(ValueError, "locked.*audio_mode"):
            resolve_brief(
                {"locked": {"audio_mode": "silent"}},
                {"directorial_axes": {"audio_mode": {"value": "native", "source": "proposed"}}},
            )

    def test_confirmed_axis_cannot_be_bypassed_by_flat_value_or_lock(self):
        shared = {"directorial_axes": {"audio_mode": {"value": "silent", "source": "user_confirmed"}}}
        for extra in ({"audio_mode": "native"}, {"locked": {"audio_mode": "native"}}):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "audio_mode"):
                resolve_brief({**shared, **extra})
        with self.assertRaisesRegex(ValueError, "audio_mode"):
            resolve_brief(shared, {"audio_mode": "native"})

    def test_locked_delivery_values_are_validated(self):
        for locked in ({"delivery.aspect": "0:9"}, {"production.target_duration_s": -2}):
            with self.subTest(locked=locked), self.assertRaises(ValueError):
                resolve_brief({"locked": locked})

    def test_contradictory_lock_aliases_fail(self):
        for locked in (
            {"delivery.aspect": "16:9", "delivery": {"aspect": "9:16"}},
            {"episode.duration_s": 60, "production.target_duration_s": 180},
        ):
            with self.subTest(locked=locked), self.assertRaisesRegex(ValueError, "locked"):
                resolve_brief({"locked": locked})

    def test_explicit_scenes_do_not_remove_locked_beats(self):
        brief = resolve_brief(
            {"locked": {"production.beats": ["arrival", "departure"]}},
            {"production": {"scenes": [{"role": "arrival"}]}},
            format_id="micro-drama",
        )
        self.assertEqual(brief["production"]["beats"], ["arrival", "departure"])

    def test_explicit_or_locked_duration_does_not_inherit_conflicting_scene_times(self):
        for shared in (
            {"production": {"target_duration_s": 180}},
            {"locked": {"production.target_duration_s": 180}},
        ):
            brief = resolve_brief(shared, format_id="micro-drama")
            self.assertNotIn("duration_range_s", brief["production"])
            self.assertNotIn("scenes", brief["production"])

    def test_tighter_existing_allocation_cannot_be_relaxed(self):
        with self.assertRaisesRegex(ValueError, "unit_budget.cap"):
            resolve_brief(
                {"budget": {"cap": 100}, "unit_budget": {"cap": 20}},
                {"unit_budget": {"cap": 30}},
            )

    def test_explicit_and_locked_ranges_reject_conflicting_unit_targets(self):
        for shared in (
            {"production": {"duration_range_s": [45, 60]}},
            {"locked": {"production.duration_range_s": [45, 60]}},
            {"locked": {"production": {"duration_range_s": [45, 60]}}},
        ):
            for target in (44, 61, 180):
                before = copy.deepcopy(shared)
                with (
                    self.subTest(shared=shared, target=target),
                    self.assertRaisesRegex(ValueError, "target_duration_s.*duration_range_s"),
                ):
                    resolve_brief(
                        shared, {"production": {"target_duration_s": target}},
                        format_id="micro-drama",
                    )
                self.assertEqual(shared, before)

    def test_explicit_and_locked_ranges_survive_compatible_targets(self):
        for shared in (
            {"production": {"duration_range_s": [45, 60]}},
            {"locked": {"production.duration_range_s": [45, 60]}},
        ):
            for target in (45, 50, 60):
                with self.subTest(shared=shared, target=target):
                    brief = resolve_brief(
                        shared, {"production": {"target_duration_s": target}},
                        format_id="micro-drama",
                    )
                    self.assertEqual(brief["production"]["duration_range_s"], [45, 60])
                    self.assertEqual(brief["production"]["target_duration_s"], target)
                    self.assertNotIn("scenes", brief["production"])

    def test_duration_conflicts_fail_in_shared_unit_and_locked_settings(self):
        for shared, unit in (
            ({"production": {"target_duration_s": 180, "duration_range_s": [45, 60]}}, {}),
            ({}, {"production": {"target_duration_s": 180, "duration_range_s": [45, 60]}}),
            ({"locked": {"production.target_duration_s": 180,
                         "production.duration_range_s": [45, 60]}}, {}),
            ({"locked": {"episode.duration_s": 180}},
             {"production": {"duration_range_s": [45, 60]}}),
        ):
            with (
                self.subTest(shared=shared, unit=unit),
                self.assertRaisesRegex(ValueError, "target_duration_s.*duration_range_s"),
            ):
                resolve_brief(shared, unit, format_id="micro-drama")

    def test_format_locks_fail_explicitly_instead_of_being_discarded(self):
        for locked in (
            {"production.format": "micro-drama"},
            {"production": {"format": "micro-drama"}},
            {"format": "micro-drama"},
            {"production.format": "unknown"},
            {"production.format": None},
            {"production.format": {}},
            {"production": {"format": {}}},
            {"format": {}},
            {"production.format": {"id": "micro-drama"}},
        ):
            for format_id in (None, "film", "micro-drama"):
                with (
                    self.subTest(locked=locked, format_id=format_id),
                    self.assertRaisesRegex(ValueError, "Unsupported locked path: .*format"),
                ):
                    resolve_brief({"locked": locked}, format_id=format_id)

    def test_unit_cannot_replace_erase_or_introduce_authorization(self):
        authorization = {"source": "chat", "evidence": "Review each operation."}
        for shared, unit in (
            ({"authorization": authorization}, {"authorization": {"source": "agent"}}),
            ({"authorization": authorization}, {"authorization": {}}),
            ({"authorization": authorization}, {"authorization": None}),
            ({}, {"authorization": authorization}),
        ):
            with self.subTest(unit=unit), self.assertRaisesRegex(ValueError, "authorization"):
                resolve_brief(shared, unit)
        for unit in ({}, {"authorization": copy.deepcopy(authorization)}):
            self.assertEqual(
                resolve_brief({"authorization": authorization}, unit)["authorization"],
                authorization,
            )

    def test_unsupported_locks_alias_fails_in_shared_and_unit(self):
        for locks in ({}, None, [], {"production.target_duration_s": 60}):
            for shared, unit in (({"locks": locks}, {}), ({}, {"locks": locks})):
                with (
                    self.subTest(shared=shared, unit=unit),
                    self.assertRaisesRegex(ValueError, "locks.*unsupported.*locked"),
                ):
                    resolve_brief(shared, unit)

    def test_locked_authority_paths_cannot_introduce_authorization_or_locks(self):
        for path in ("authorization.source", "locks.production.target_duration_s"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Unsupported locked path"):
                resolve_brief({"locked": {path: "unapproved"}})

    def test_explicit_and_locked_ranges_remove_only_inherited_scenes(self):
        for shared, unit in (
            ({"production": {"duration_range_s": [150, 180]}}, {}),
            ({}, {"production": {"duration_range_s": [150, 180]}}),
            ({"locked": {"production.duration_range_s": [150, 180]}}, {}),
        ):
            with self.subTest(shared=shared, unit=unit):
                brief = resolve_brief(shared, unit, format_id="micro-drama")
                self.assertEqual(brief["production"]["duration_range_s"], [150, 180])
                self.assertNotIn("scenes", brief["production"])

    def test_duration_changes_preserve_explicit_legacy_and_locked_scenes(self):
        for scenes in ([], [{"role": "held shot", "duration_s": 50}]):
            for shared in (
                {"production": {"scenes": scenes}},
                {"episode": {"scenes": scenes}},
                {"locked": {"production.scenes": scenes}},
                {"locked": {"episode.scenes": scenes}},
            ):
                for duration in (
                    {"target_duration_s": 180},
                    {"duration_range_s": [150, 180]},
                ):
                    with self.subTest(shared=shared, duration=duration):
                        brief = resolve_brief(
                            shared, {"production": duration}, format_id="micro-drama",
                        )
                        self.assertEqual(brief["production"]["scenes"], scenes)

    def test_equal_and_zero_unit_allocations_remain_valid(self):
        budget = {"cap": 100, "currency": "USD", "confirmed": 30, "unknown": 20}
        shared = {"budget": budget, "unit_budget": {"cap": 20, "currency": "USD"}}
        for cap in (0, 10, 20):
            with self.subTest(cap=cap):
                brief = resolve_brief(shared, {"unit_budget": {"cap": cap}})
                self.assertEqual(brief["budget"], budget)
                self.assertEqual(brief["unit_budget"], {"cap": cap, "currency": "USD"})

    def test_locked_unit_allocations_cannot_bypass_validation(self):
        for allocation in (
            {"cap": 200}, {"cap": -1}, {"cap": True},
            {"cap": float("nan")}, {"cap": float("inf")},
            {"cap": 10, "currency": "EUR"}, {"cap": 10, "confirmed": 0},
            {"cap": 10, "policy": {}}, {"currency": "USD"}, {},
        ):
            for locked in (
                {"unit_budget": allocation},
                {f"unit_budget.{key}": value for key, value in allocation.items()}
                if allocation else {"unit_budget": {}},
            ):
                shared = {"budget": {"cap": 100, "currency": "USD"}, "locked": locked}
                before = copy.deepcopy(shared)
                with (
                    self.subTest(locked=locked),
                    self.assertRaisesRegex(ValueError, "unit_budget"),
                ):
                    resolve_brief(shared)
                self.assertEqual(shared, before)
        with self.assertRaisesRegex(ValueError, "budget.cap"):
            resolve_brief({"locked": {"unit_budget.cap": 10}})

    def test_invalid_shared_allocations_cannot_be_hidden_by_unit_overrides(self):
        for allocation in (
            {"cap": 20, "currency": "EUR"}, {"cap": 200},
            {"cap": 20, "confirmed": 0}, {"cap": -1},
            {"cap": True}, {"cap": float("inf")}, {"currency": "USD"},
            {}, None, [],
        ):
            shared = {"budget": {"cap": 100, "currency": "USD"}, "unit_budget": allocation}
            for unit in ({}, {"unit_budget": {"cap": 10}},
                         {"unit_budget": {"cap": 10, "currency": "USD"}}):
                with (
                    self.subTest(allocation=allocation, unit=unit),
                    self.assertRaisesRegex(ValueError, "unit_budget"),
                ):
                    resolve_brief(shared, unit)

    def test_final_allocation_merges_inherited_currency_and_valid_locks(self):
        for cap in (0, 20, 100):
            for locked in (
                {"unit_budget.cap": cap},
                {"unit_budget": {"cap": cap, "currency": "USD"}},
            ):
                shared = {"budget": {"cap": 100, "currency": "USD"}, "locked": locked}
                unit = {"production": {"genre": "drama"}}
                before = copy.deepcopy((shared, unit))
                brief = resolve_brief(shared, unit)
                self.assertEqual(brief["unit_budget"]["cap"], cap)
                self.assertEqual(brief["budget"], shared["budget"])
                brief["unit_budget"]["cap"] = 999
                self.assertEqual((shared, unit), before)
        shared = {
            "budget": {"cap": 100, "currency": "USD"},
            "unit_budget": {"cap": 20},
            "locked": {"unit_budget.currency": "USD"},
        }
        brief = resolve_brief(shared, {"unit_budget": {"cap": 10}})
        self.assertEqual(brief["unit_budget"], {"cap": 10, "currency": "USD"})
        with self.assertRaisesRegex(ValueError, "unit_budget.currency"):
            resolve_brief({**shared, "locked": {"unit_budget.currency": "EUR"}},
                          {"unit_budget": {"cap": 10}})

    def test_repeated_unit_budget_survives_shared_runtime_updates(self):
        unit = {"budget": {"cap": 100, "currency": "USD", "confirmed": 0}}
        for confirmed in (0, 10):
            shared = {"budget": {"cap": 100, "currency": "USD", "confirmed": confirmed}}
            before = copy.deepcopy((shared, unit))
            brief = resolve_brief(shared, unit)
            self.assertEqual(brief["budget"], shared["budget"])
            brief["budget"]["confirmed"] = 999
            self.assertEqual((shared, unit), before)

    def test_unit_runtime_totals_never_replace_or_introduce_shared_totals(self):
        runtime_fields = (
            "estimated", "confirmed", "unknown", "spent", "estimated_spend",
            "confirmed_spend", "unknown_spend", "reserved", "reservations",
        )
        for field in runtime_fields:
            for shared_runtime in ({}, {field: [{"amount": 10}]} if field == "reservations"
                                   else {field: 10}):
                shared = {"budget": {"cap": 100, "currency": "USD", **shared_runtime}}
                unit = {"budget": {"cap": 100, "currency": "USD", field: 0}}
                with self.subTest(field=field, shared_runtime=shared_runtime):
                    self.assertEqual(resolve_brief(shared, unit)["budget"], shared["budget"])
                    self.assertEqual(
                        resolve_brief(shared, {"budget": {"cap": 100, "currency": "USD"}})["budget"],
                        shared["budget"],
                    )

    def test_unit_budget_policy_must_match_including_unknown_fields(self):
        budget = {
            "cap": 100, "currency": "USD", "confirmed": 10,
            "approval_threshold": {"amount": 20},
        }
        for policy in (
            {"cap": 100, "currency": "USD"},
            {"cap": 200, "currency": "USD", "approval_threshold": {"amount": 20}},
            {"cap": 100, "currency": "EUR", "approval_threshold": {"amount": 20}},
            {"cap": 100, "currency": "USD", "approval_threshold": {"amount": 30}},
            {**budget, "new_policy": True},
            {}, None, [],
        ):
            with self.subTest(policy=policy), self.assertRaisesRegex(ValueError, "unit.budget"):
                resolve_brief({"budget": budget}, {"budget": policy})
        unit = {"budget": {**budget, "confirmed": 0}}
        before = copy.deepcopy((budget, unit))
        brief = resolve_brief({"budget": budget}, unit)
        self.assertEqual(brief["budget"], budget)
        brief["budget"]["approval_threshold"]["amount"] = 999
        self.assertEqual((budget, unit), before)
        for budget in ({}, {"confirmed": 0}, {"cap": 100}):
            with self.subTest(budget=budget), self.assertRaisesRegex(ValueError, "unit.budget"):
                resolve_brief({}, {"budget": budget})

    def test_frontmatter_reader_output_is_consumed_without_file_access(self):
        from validate_request import parse_frontmatter

        shared = parse_frontmatter(
            '---\nproduction:\n  genre: wordless history\n'
            'delivery:\n  aspect: "239:100"\n  fps: 24\n---\nKeep this prose.\n'
        )
        brief = resolve_brief(shared, format_id="cinematic-short")
        self.assertEqual(brief["delivery"], {"aspect": "239:100", "fps": 24})
        self.assertNotIn("beats", brief["production"])


if __name__ == "__main__":
    unittest.main()
