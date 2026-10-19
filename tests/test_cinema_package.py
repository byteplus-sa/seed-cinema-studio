import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CinemaPackageTests(unittest.TestCase):
    def test_local_package_and_lock_use_cinema_identity(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        self.assertEqual(project["name"], "seed-cinema-studio-tools")
        packages = tomllib.loads((ROOT / "uv.lock").read_text())["package"]
        local = [item for item in packages if item.get("source") == {"virtual": "."}]
        self.assertEqual([item["name"] for item in local], [project["name"]])

    def test_legacy_entrypoints_and_relative_links_remain_available(self):
        for script in ("studio_project.py", "prepare_request.py", "draft_ledger.py"):
            self.assertTrue((ROOT / ".agents/scripts" / script).is_file())
        self.assertTrue((ROOT / "CLAUDE.md").is_symlink())
        for name in ("micro-drama", "microdrama-subtitles", "subtitle-sidecars"):
            link = ROOT / ".claude/skills" / name
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), ROOT / ".agents/skills" / name)


if __name__ == "__main__":
    unittest.main()
