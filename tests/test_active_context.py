from __future__ import annotations

import dataclasses
import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".agents/scripts"))

import production_context as contexts
import test_production_context as fixtures


class ActiveContextTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ProductionContextTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.write = fixture.write
        self.manifest = fixture.manifest
        self.candidate = fixture.candidate().identity()
        self.write("production.json", json.dumps(self.manifest))

    def test_active_context_keeps_frozen_candidate_unit_identity(self):
        active = contexts.resolve_context(self.root, "ep001")
        self.assertEqual(active.identity(), self.candidate)
        self.assertIsNone(active._candidate_manifest)
        self.assertEqual(len(contexts.discover_unit_shots(active)), 1)
        self.assertEqual(contexts.validate_production(self.root), [])
        with self.assertRaisesRegex(ValueError, "Multiple"):
            contexts.resolve_context(self.root)

    def test_shared_canon_excludes_units_but_binds_shared_authorization(self):
        before = contexts.resolve_production_context(self.root).identity()
        self.assertNotIn("unit_id", before)
        self.write("units/ep002/unit.md", "Unrelated episode revision.")
        self.assertEqual(contexts.resolve_production_context(self.root).identity(), before)
        self.write("project.md", "---\napproval_mode: ask_for_approval\n---\nShared story.\n")
        self.assertNotEqual(contexts.resolve_production_context(self.root).identity(), before)

    def test_production_projection_and_shared_digest_are_frozen(self):
        context = contexts.resolve_production_context(self.root)
        payload = contexts.context_fingerprint_payload(context)
        self.assertEqual(set(payload), {
            "context_version", "kind", "format", "profile", "effective_settings", "shared_inputs",
        })
        self.assertEqual(payload["context_version"], 2)
        expected = "80f22118a76f799f294318cd5c2d92e8f1351993a014804e39ff616b2373fad2"
        self.assertEqual(context.effective_sha256, expected)
        self.assertEqual(contexts.context_project_sha256(self.root), expected)

    def test_normalized_shared_binding_excludes_only_operational_metadata(self):
        before = contexts.context_project_sha256(self.root)
        self.write("project.md", "---\napproval_mode: approve_for_me\n"
                   "billing: {confirmed: 3}\nruntime: {state: running}\n---\nShared story.\n")
        self.assertEqual(contexts.context_project_sha256(self.root), before)
        self.write("project.md", "---\napproval_mode: approve_for_me\n"
                   "story: {secret: changed}\n---\nShared story.\n")
        self.assertNotEqual(contexts.context_project_sha256(self.root), before)

    def test_foreign_stale_and_malformed_record_contexts_fail(self):
        identity = contexts.resolve_context(self.root, "ep001").identity()
        contexts.validate_record_context(self.root, identity, unit_id="ep001", kind="unit")
        for invalid in (None, {}, {**identity, "extra": True}):
            with self.assertRaises(ValueError):
                contexts.validate_record_context(self.root, invalid, unit_id="ep001")
        with self.assertRaises(ValueError):
            contexts.validate_record_context(self.root, identity, unit_id="ep002")
        self.write("units/ep001/unit.md", "Changed.")
        with self.assertRaises(ValueError):
            contexts.validate_record_context(self.root, identity, unit_id="ep001")

    def test_active_manifest_and_unit_root_aliases_fail_closed(self):
        active = self.root / "production.json"
        active.unlink()
        active.symlink_to(self.root / "production.plan.json")
        with self.assertRaises(ValueError):
            contexts.resolve_context(self.root, "ep001")

    def test_internal_unit_and_units_directory_aliases_are_rejected_before_writes(self):
        unit = self.root / "units/ep001"
        shared = self.root / "elements/hero"
        shared.parent.mkdir()
        shutil.move(unit, shared)
        unit.symlink_to(shared, target_is_directory=True)
        self.assertTrue(contexts.validate_production(self.root))
        with self.assertRaises(ValueError):
            contexts.resolve_context(self.root, "ep001")
        self.assertFalse((shared / "studio").exists())
        unit.unlink()
        shutil.move(shared, unit)
        units = self.root / "units"
        renamed = self.root / "shared-units"
        shutil.move(units, renamed)
        units.symlink_to(renamed, target_is_directory=True)
        self.assertTrue(contexts.validate_production(self.root))

    def test_replaced_membership_cannot_discover_foreign_shots(self):
        context = contexts.resolve_context(self.root, "ep001")
        for replaced in (
            dataclasses.replace(context, scene_ids=("scene-002",)),
            dataclasses.replace(context, studio_root=self.root / "elements/hero"),
        ):
            with self.assertRaisesRegex(ValueError, "Stale|context"):
                contexts.discover_unit_shots(replaced)
        (self.root / "production.json").unlink()
        candidate = contexts.resolve_candidate_context(self.root, "production.plan.json", "ep001")
        with self.assertRaisesRegex(ValueError, "Stale|context"):
            contexts.discover_unit_shots(dataclasses.replace(candidate, scene_ids=("scene-002",)))


if __name__ == "__main__":
    unittest.main()
