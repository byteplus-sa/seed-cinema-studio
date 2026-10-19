from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

SCRIPTS = Path(__file__).resolve().parents[1] / ".agents/scripts"
sys.path.insert(0, str(SCRIPTS))

from production_context import (
    context_fingerprint_payload,
    discover_unit_shots,
    reject_active_manifest,
    resolve_candidate_context,
    resolve_context,
    validate_production,
)


class ProductionContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "project"
        self.root.mkdir()
        self.write("project.md", "---\napproval_mode: approve_for_me\n---\nShared story.\n")
        self.manifest = {
            "schema_version": 1,
            "format": "episodic-show",
            "units": [
                {"id": "ep001", "kind": "episode", "brief": "units/ep001/unit.md",
                 "scene_ids": ["scene-001"]},
                {"id": "ep002", "kind": "episode", "brief": "units/ep002/unit.md",
                 "scene_ids": ["scene-002"]},
            ],
            "deliverables": [],
        }
        for number in (1, 2):
            self.write(f"units/ep{number:03}/unit.md", f"# Episode {number}\nA turn.\n")
            self.write(f"scenes/scene-{number:03}/scene.md", f"# Scene {number}\n")
            self.write(f"scenes/scene-{number:03}/s{number:03}_sh010/shot.md",
                       f"---\nshot_id: s{number:03}_sh010\n---\nA shot.\n")
        self.save()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def save(self):
        self.write("production.plan.json", json.dumps(self.manifest))

    def candidate(self, unit="ep001"):
        return resolve_candidate_context(self.root, "production.plan.json", unit)

    def findings(self):
        return validate_production(self.root, manifest="production.plan.json")

    def test_legacy_ignores_candidate_and_is_frozen(self):
        context = resolve_context(self.root)
        self.assertTrue(context.legacy)
        self.assertIsNone(context.unit_id)
        self.assertEqual(context.studio_root, self.root / "studio")
        self.assertEqual(context.stages_path, self.root / "studio/stages.json")
        self.assertEqual(len(discover_unit_shots(context)), 2)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            context.unit_id = "ep001"
        with self.assertRaisesRegex(ValueError, "unit"):
            resolve_context(self.root, "ep001")

    def test_active_manifest_fails_closed_including_dangling_symlink(self):
        active = self.root / "production.json"
        for content in ("{}", "{invalid"):
            active.write_text(content)
            with self.assertRaisesRegex(ValueError, "unsupported.*layout"):
                resolve_context(self.root)
            with self.assertRaisesRegex(ValueError, "unsupported.*layout"):
                reject_active_manifest(self.root)
            self.assertTrue(validate_production(self.root))
        active.unlink()
        active.symlink_to(self.root / "missing.json")
        with self.assertRaisesRegex(ValueError, "unsupported.*layout"):
            reject_active_manifest(self.root)

    def test_candidate_selection_and_order_are_explicit(self):
        self.assertEqual(self.findings(), [])
        with self.assertRaisesRegex(ValueError, "unit"):
            self.candidate(None)
        with self.assertRaisesRegex(ValueError, "unit"):
            self.candidate("unknown")
        context = self.candidate()
        self.assertFalse(context.legacy)
        self.assertEqual(context.scene_ids, ("scene-001",))
        self.assertEqual(context.unit_brief, self.root / "units/ep001/unit.md")
        self.assertEqual(context.studio_root, self.root / "units/ep001/studio")
        self.assertEqual([shot.shot_id for shot in discover_unit_shots(context)],
                         ["s001_sh010"])
        self.manifest["units"][0]["scene_ids"] = ["scene-002", "scene-001"]
        self.manifest["units"].pop()
        self.save()
        context = self.candidate(None)
        self.assertEqual([shot.shot_id for shot in discover_unit_shots(context)],
                         ["s002_sh010", "s001_sh010"])

    def test_duplicate_unit_scene_and_shot_membership_rejected(self):
        cases = ("unit", "scene", "shot", "same-scene")
        original = json.dumps(self.manifest)
        for case in cases:
            with self.subTest(case=case):
                self.manifest = json.loads(original)
                if case == "unit":
                    self.manifest["units"][1]["id"] = "ep001"
                elif case == "scene":
                    self.manifest["units"][1]["scene_ids"] = ["scene-001"]
                elif case == "same-scene":
                    self.manifest["units"][0]["scene_ids"].append("scene-001")
                else:
                    self.write("scenes/scene-002/s002_sh010/shot.md",
                               "---\nshot_id: s001_sh010\n---\n")
                self.save()
                self.assertTrue(self.findings())
                with self.assertRaises(ValueError):
                    self.candidate()

    def test_missing_references_rejected(self):
        for name in ("units/ep001/unit.md", "scenes/scene-001/scene.md"):
            path = self.root / name
            original = path.read_text()
            path.unlink()
            self.assertTrue(self.findings())
            path.write_text(original)
        self.manifest["deliverables"] = [
            {"id": "master", "unit_id": "unknown", "manifest": "deliverables/master.json"}
        ]
        self.save()
        self.assertTrue(self.findings())
        self.manifest["deliverables"][0]["unit_id"] = "ep001"
        self.save()
        self.assertTrue(self.findings())

    def test_malformed_and_unsupported_manifest_are_findings(self):
        for content in ("{", "null", "[]", '{"schema_version": 2}',
                        '{"schema_version": 1, "schema_version": 1}', '{"x": NaN}'):
            with self.subTest(content=content):
                self.write("production.plan.json", content)
                self.assertTrue(self.findings())
        self.save()
        self.manifest["units"] = []
        self.save()
        self.assertTrue(self.findings())

    def test_paths_reject_traversal_absolute_and_windows_spellings(self):
        for path in ("../outside.md", "/tmp/outside.md", "units/../project.md",
                     r"..\outside.md", "C:/outside.md"):
            with self.subTest(path=path):
                self.manifest["units"][0]["brief"] = path
                self.save()
                self.assertTrue(self.findings())
        for path in ("../production.plan.json", str(self.root / "production.plan.json"),
                     "production.json"):
            with self.assertRaises(ValueError):
                resolve_candidate_context(self.root, path, "ep001")

    def test_symlink_and_dangling_escape_rejected_at_each_boundary(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        for name in ("production.plan.json", "project.md", "units/ep001/unit.md",
                     "scenes/scene-001", "units/ep001/studio"):
            for dangling in (False, True):
                with self.subTest(name=name, dangling=dangling):
                    path = self.root / name
                    backup = path.with_name(path.name + ".backup")
                    if path.exists():
                        path.rename(backup)
                    path.symlink_to(outside / "missing" if dangling else outside)
                    self.assertTrue(self.findings())
                    path.unlink()
                    if backup.exists():
                        backup.rename(path)

    def test_ambiguous_layout_scene_aliases_and_unowned_scenes_rejected(self):
        self.write("scenes/scene-01/scene.md", "# Alias\n")
        self.assertTrue(self.findings())
        shutil.rmtree(self.root / "scenes/scene-01")
        self.write("scenes/s001_sh020/shot.md", "---\nshot_id: s001_sh020\n---\n")
        self.assertTrue(self.findings())
        shutil.rmtree(self.root / "scenes/s001_sh020")
        self.write("studio/stages.json", "{}")
        self.assertTrue(self.findings())

    def test_fingerprint_version_one_field_set_and_digest(self):
        context = self.candidate()
        payload = context_fingerprint_payload(context)
        self.assertEqual(set(payload), {
            "context_version", "kind", "unit_id", "format", "unit_brief_sha256",
            "scene_ids", "profile", "effective_settings", "shared_inputs",
        })
        self.assertEqual(payload["context_version"], 1)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode()
        self.assertEqual(context.effective_sha256, hashlib.sha256(encoded).hexdigest())
        schema = json.loads((SCRIPTS.parent / "contracts/schemas/production-context.schema.json")
                            .read_text())
        Draft202012Validator(schema).validate(context.identity())
        for invalid in (
            {**context.identity(), "context_version": 2},
            {**context.identity(), "kind": "production"},
            {**context.identity(), "effective_sha256": "bad"},
        ):
            self.assertFalse(Draft202012Validator(schema).is_valid(invalid))
        Draft202012Validator(schema).validate({
            "context_version": 1, "kind": "production", "effective_sha256": "a" * 64,
        })

    def test_unrelated_units_runtime_billing_and_relocation_do_not_change_hash(self):
        expected = self.candidate().effective_sha256
        self.write("units/ep002/unit.md", "# Unrelated rewrite\n")
        self.write("task_ids.json", '{"billing": 1000}')
        self.write("project.md",
                   "---\napproval_mode: approve_for_me\nupdated_at: tomorrow\n"
                   "billing:\n  confirmed: 900\nruntime:\n  status: rendering\n"
                   "budget:\n  spent: 900\n---\nShared story.\n")
        self.assertEqual(self.candidate().effective_sha256, expected)
        copied = Path(self.temp.name) / "copy"
        shutil.copytree(self.root, copied)
        self.assertEqual(resolve_candidate_context(copied, "production.plan.json", "ep001")
                         .effective_sha256, expected)
        payload = context_fingerprint_payload(self.candidate())
        self.assertNotIn(str(self.root), json.dumps(payload))

    def test_relevant_brief_authorization_and_profile_inputs_change_hash(self):
        expected = self.candidate().effective_sha256
        self.write("units/ep001/unit.md", "# Changed unit story\n")
        self.assertNotEqual(self.candidate().effective_sha256, expected)
        self.write("units/ep001/unit.md", "# Episode 1\nA turn.\n")
        for metadata in ("approval_mode: ask_for_approval", "rights:\n  status: authorized",
                         "budget:\n  cap: 100", "delivery:\n  aspect: '16:9'"):
            self.write("project.md", f"---\n{metadata}\n---\nShared story.\n")
            self.assertNotEqual(self.candidate().effective_sha256, expected)
        self.write("project.md", "---\napproval_mode: approve_for_me\n---\nNew shared story.\n")
        self.assertNotEqual(self.candidate().effective_sha256, expected)

    def test_conflicting_format_authority_rejected(self):
        self.write("project.md", "---\nproduction:\n  format: micro-drama\n---\n")
        self.assertTrue(self.findings())

    def test_cli_validates_legacy_or_explicit_candidate_without_writes(self):
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob("*") if path.is_file()}
        command = [sys.executable, str(SCRIPTS / "production_context.py"),
                   str(self.root)]
        legacy = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(legacy.returncode, 0)
        self.assertTrue(json.loads(legacy.stdout)["ok"])
        result = subprocess.run(command + ["--manifest", "production.plan.json"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(json.loads(result.stdout)["ok"])
        after = {path.relative_to(self.root): path.read_bytes()
                 for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_stale_context_discovery_rejects_changed_unit_brief(self):
        context = self.candidate()
        self.write("units/ep001/unit.md", "# Changed story\n")
        with self.assertRaisesRegex(ValueError, "Stale"):
            discover_unit_shots(context)

    def test_profile_revision_changes_fingerprint(self):
        from production_profiles import load_profile

        expected = self.candidate().effective_sha256
        profile = load_profile("episodic-show")
        profile["revision"] += 1
        with patch("production_profiles.load_profile", return_value=profile):
            self.assertNotEqual(self.candidate().effective_sha256, expected)

    def test_cli_reports_unknown_unit_and_invalid_manifest_without_writes(self):
        command = [sys.executable, str(SCRIPTS / "production_context.py"),
                   str(self.root), "--manifest", "production.plan.json"]
        for extra in (["--unit", "ep001"], ["--unit", "unknown"]):
            result = subprocess.run(command + extra, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0 if extra[-1] == "ep001" else 1)
            self.assertEqual(json.loads(result.stdout)["ok"], extra[-1] == "ep001")
        self.write("production.plan.json", "{invalid")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertFalse((self.root / "production.json").exists())
        self.assertFalse((self.root / "units/ep001/studio").exists())

    def test_unit_incidental_metadata_changes_invalidate_fingerprint(self):
        context = self.candidate()
        self.write("units/ep001/unit.md",
                   "---\nupdated_at: 2026-10-19\nruntime:\n  status: rendering\n"
                   "billing:\n  confirmed: 99\nsource_path: /machine/private/story.md\n"
                   "---\n# Episode 1\nA turn.\n")
        self.assertNotEqual(self.candidate().effective_sha256, context.effective_sha256)
        with self.assertRaisesRegex(ValueError, "Stale"):
            discover_unit_shots(context)

    def test_unit_brief_binds_raw_bytes_including_line_endings_and_yaml_comments(self):
        brief = self.root / "units/ep001/unit.md"
        for before, after in (
            (b"# Episode 1\nA turn.\n", b"# Episode 1\r\nA turn.\r\n"),
            (b"---\nstory: turn\n# First note\n---\nA turn.\n",
             b"---\nstory: turn\n# Second note\n---\nA turn.\n"),
            (b'---\nstory: "A turn."\n---\n', b"---\nstory: 'A turn.'\n---\n"),
        ):
            with self.subTest(before=before):
                brief.write_bytes(before)
                context = self.candidate()
                self.assertEqual(context_fingerprint_payload(context)["unit_brief_sha256"],
                                 hashlib.sha256(before).hexdigest())
                brief.write_bytes(after)
                self.assertNotEqual(self.candidate().effective_sha256, context.effective_sha256)
                with self.assertRaisesRegex(ValueError, "Stale"):
                    discover_unit_shots(context)

    def test_nested_creative_fields_are_bound_without_name_based_exclusions(self):
        def source(group, field, nested_list, value):
            nested = {field: value}
            metadata = {group: {"beats": [nested]} if nested_list else nested}
            return f"---\n{json.dumps(metadata)}\n---\nShared story.\n"

        fields = (
            "secret", "brief", "path", "look_at", "source_path", "updated_at",
            "billing", "runtime", "budget",
        )
        for group in ("story", "creative_intent", "production"):
            for field in fields:
                for nested_list in (False, True):
                    with self.subTest(group=group, field=field, nested_list=nested_list):
                        self.write("project.md", source(group, field, nested_list, "hidden heir"))
                        context = self.candidate()
                        payload = context_fingerprint_payload(context)
                        for scope in ("shared_inputs", "effective_settings"):
                            nested = payload[scope][group]
                            self.assertEqual(
                                (nested["beats"][0] if nested_list else nested)[field],
                                "hidden heir",
                            )
                        self.write("project.md", source(group, field, nested_list, "lost inheritance"))
                        self.assertNotEqual(self.candidate().effective_sha256,
                                            context.effective_sha256)
                        with self.assertRaisesRegex(ValueError, "Stale"):
                            discover_unit_shots(context)

    def test_shared_creative_intent_is_bound_even_when_unit_overrides_it(self):
        self.write("units/ep001/unit.md", "---\ncreative_intent: unit turn\n---\n")
        self.write("project.md", "---\ncreative_intent: shared turn\n---\n")
        context = self.candidate()
        self.write("project.md", "---\ncreative_intent: revised shared turn\n---\n")
        current = self.candidate()
        before = context_fingerprint_payload(context)
        after = context_fingerprint_payload(current)
        self.assertEqual(before["effective_settings"], after["effective_settings"])
        self.assertEqual(after["shared_inputs"].get("creative_intent"), "revised shared turn")
        self.assertNotEqual(current.effective_sha256, context.effective_sha256)
        with self.assertRaisesRegex(ValueError, "Stale"):
            discover_unit_shots(context)

    def test_operational_exclusions_apply_only_at_documented_setting_paths(self):
        self.write("project.md", "---\nbudget:\n  cap: 100\n  currency: USD\n---\n")
        context = self.candidate()
        self.write("project.md",
                   "---\nbudget:\n  cap: 100\n  currency: USD\n"
                   "  confirmed: 50\n  estimated: 10\n  unknown: 5\n  reserved: 20\n"
                   "runtime:\n  source_path: /other/machine\n"
                   "billing:\n  confirmed: 50\nupdated_at: 2026-10-19\n"
                   "credentials:\n  token: synthetic-marker\n---\n")
        current = self.candidate()
        self.assertEqual(current.effective_sha256, context.effective_sha256)
        self.assertEqual(len(discover_unit_shots(context)), 1)
        payload = context_fingerprint_payload(current)
        self.assertNotIn("synthetic-marker", json.dumps(payload))
        for scope in ("shared_inputs", "effective_settings"):
            self.assertEqual(payload[scope]["budget"], {"cap": 100, "currency": "USD"})
            self.assertNotIn("runtime", payload[scope])
            self.assertNotIn("billing", payload[scope])
        self.write("project.md", "---\nbudget:\n  cap: 101\n  currency: USD\n---\n")
        with self.assertRaisesRegex(ValueError, "Stale"):
            discover_unit_shots(context)

    def test_shared_and_unit_brief_symlink_aliases_are_rejected(self):
        shared = self.root / "project.md"
        unit = self.root / "units/ep001/unit.md"
        shared_text, unit_text = shared.read_text(), unit.read_text()
        for alias, target in ((shared, unit), (unit, shared)):
            with self.subTest(alias=alias.relative_to(self.root)):
                alias.unlink()
                alias.symlink_to(target)
                try:
                    self.assertTrue(self.findings())
                    with self.assertRaisesRegex(ValueError, "brief ownership"):
                        self.candidate()
                finally:
                    alias.unlink()
                    shared.write_text(shared_text)
                    unit.write_text(unit_text)

    def test_scene_and_shot_declared_ownership_must_match(self):
        scene = self.root / "scenes/scene-001/scene.md"
        original = scene.read_text()
        scene.write_text("---\nscene_id: scene-002\n---\n")
        self.assertTrue(self.findings())
        scene.write_text(original)
        self.write("scenes/scene-001/s001_sh010/shot.md",
                   "---\nshot_id: s001_sh010\nunit_id: ep002\n---\n")
        self.assertTrue(self.findings())

    def test_unit_studios_cannot_alias_another_unit(self):
        target = self.root / "units/ep002/studio"
        target.mkdir()
        (self.root / "units/ep001/studio").symlink_to(target)
        self.assertTrue(self.findings())

    def test_foreign_unit_and_path_shaped_identity_cannot_be_selected(self):
        for unit in ("../ep001", "/ep001", "EP001", ""):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                self.candidate(unit)

    def test_missing_candidate_and_project_report_findings(self):
        (self.root / "production.plan.json").unlink()
        self.assertTrue(self.findings())
        self.assertTrue(validate_production(self.root / "missing",
                                            manifest="production.plan.json"))

    def test_shot_symlink_escape_and_reserved_id_are_rejected(self):
        shot = self.root / "scenes/scene-001/s001_sh010/shot.md"
        original = shot.read_text()
        shot.unlink()
        shot.symlink_to(Path(self.temp.name) / "missing")
        self.assertTrue(self.findings())
        shot.unlink()
        shot.write_text(original.replace("s001_sh010", "main"))
        self.assertTrue(self.findings())

    def test_legacy_flat_shot_layout_remains_discoverable(self):
        shutil.rmtree(self.root / "scenes")
        self.write("scenes/s01_sh010/shot.md", "---\nshot_id: s01_sh010\n---\n")
        self.assertEqual([shot.shot_id for shot in discover_unit_shots(resolve_context(self.root))],
                         ["s01_sh010"])

    def test_legacy_numeric_alias_folders_keep_explicit_unique_shots(self):
        import studio_project

        self.write("scenes/scene-01/s01_sh020/shot.md",
                   "---\nshot_id: s01_sh020\n---\n")
        self.assertEqual(
            [shot.manifest for shot in discover_unit_shots(resolve_context(self.root))],
            [shot.manifest for shot in studio_project.discover_shots(self.root)],
        )
        self.assertTrue(self.findings())

    def test_legacy_discovery_preserves_both_studio_globs_and_order(self):
        self.write("scenes/scene-opening/shot.md", "---\nshot_id: opening\n---\n")
        self.write("scenes/scene-opening/a/shot.md", "---\nshot_id: opening_a\n---\n")
        self.write("scenes/flat/shot.md", "---\nshot_id: flat\n---\n")
        self.write("scenes/not-a-scene/ignored/shot.md", "---\nshot_id: ignored\n---\n")
        expected = sorted({
            path.relative_to(self.root).as_posix()
            for pattern in ("scenes/scene-*/*/shot.md", "scenes/*/shot.md")
            for path in self.root.glob(pattern)
        })
        self.assertEqual(
            [shot.manifest for shot in discover_unit_shots(resolve_context(self.root))],
            expected,
        )

    def test_candidate_rejects_unowned_nonnumeric_scene_shots(self):
        self.write("scenes/scene-opening/opening/shot.md", "---\nshot_id: opening\n---\n")
        self.assertTrue(self.findings())
        with self.assertRaisesRegex(ValueError, "shot ownership"):
            self.candidate()

    def test_nonnumeric_legacy_shot_symlink_escape_is_rejected(self):
        shot = self.write("scenes/scene-opening/opening/shot.md", "# Shot\n")
        shot.unlink()
        shot.symlink_to(Path(self.temp.name) / "outside.md")
        with self.assertRaises(ValueError):
            discover_unit_shots(resolve_context(self.root))

    def test_fingerprint_canonical_fixture_is_frozen(self):
        profile = {"id": "episodic-show", "revision": 1, "defaults": {}}
        effective = {"format": "episodic-show", "delivery": {"aspect": "16:9"}}
        expected = {
            "context_version": 1,
            "kind": "unit",
            "unit_id": "ep001",
            "format": "episodic-show",
            "unit_brief_sha256": hashlib.sha256(b"# Episode 1\nA turn.\n").hexdigest(),
            "scene_ids": ["scene-001"],
            "profile": profile,
            "effective_settings": effective,
            "shared_inputs": {
                "approval_mode": "approve_for_me",
                "body_sha256": hashlib.sha256(b"Shared story.\n").hexdigest(),
            },
        }
        with (
            patch("production_profiles.load_profile", return_value=profile),
            patch("production_profiles.resolve_brief", return_value=effective),
        ):
            context = self.candidate()
        self.assertEqual(context_fingerprint_payload(context), expected)
        expected_bytes = json.dumps(expected, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()
        self.assertEqual(context.effective_sha256, hashlib.sha256(expected_bytes).hexdigest())
        self.assertEqual(context.effective_sha256,
                         "0032d28600fd5de885f309e6e6e7db75336d8c52398709761de404881ede5dc0")
        payload = context_fingerprint_payload(context)
        payload["scene_ids"].clear()
        self.assertEqual(context_fingerprint_payload(context), expected)

    def test_invalid_yaml_findings_do_not_echo_source_content(self):
        self.write("units/ep001/unit.md", "---\nprivate-marker: [broken\n---\n")
        findings = self.findings()
        self.assertTrue(findings)
        self.assertNotIn("private-marker", json.dumps([dataclasses.asdict(item) for item in findings]))

    def test_schema_identifiers_reject_trailing_newlines(self):
        for filename in ("production.schema.json", "production-context.schema.json"):
            schema = json.loads((SCRIPTS.parent / "contracts/schemas" / filename).read_text())
            Draft202012Validator.check_schema(schema)
            document = json.loads(json.dumps(self.manifest))
            if filename == "production.schema.json":
                document["units"][0]["id"] = "ep001\n"
            else:
                document = {"context_version": 1, "kind": "unit",
                            "unit_id": "ep001\n", "effective_sha256": "a" * 64}
            self.assertFalse(Draft202012Validator(schema).is_valid(document))


if __name__ == "__main__":
    unittest.main()
