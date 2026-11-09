import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / '.agents/contracts/generation-access.md'


class GenerationAccessPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = CONTRACT.read_text(encoding='utf-8')
        self.rows = {
            tuple(cell.strip() for cell in line.strip('|').split('|'))
            for line in self.policy.splitlines()
            if line.startswith('|')
        }

    def test_missing_or_unusable_mcp_returns_prompts_without_cli_fallback(self):
        for availability in ('Unavailable', 'Unusable'):
            with self.subTest(availability=availability):
                self.assertIn(
                    (availability, 'No explicit alternative transport', 'Prompt handoff'),
                    self.rows,
                )
        self.assertIn('Never automatically fall back to Ark CLI', self.policy)

    def test_connected_mcp_requires_generation_scope_and_preserves_prompt_only(self):
        self.assertIn(('Any', 'Prompt-only request', 'Prompt handoff'), self.rows)
        self.assertIn(('Usable', 'No generation consent', 'Prompt handoff'), self.rows)
        self.assertIn(
            ('Usable', 'Explicit generation scope', 'MCP generation with existing safeguards'),
            self.rows,
        )

    def test_explicit_alternatives_require_usable_authorized_transports(self):
        self.assertIn(
            ('Any', 'Explicit Ark CLI generation', 'Ark CLI generation if usable; otherwise prompt handoff'),
            self.rows,
        )
        self.assertIn(
            ('Any', 'Explicit HTTP/curl generation', 'HTTP generation if securely configured; otherwise prompt handoff'),
            self.rows,
        )

    def test_connection_loss_recovers_existing_jobs_without_new_submissions(self):
        self.assertIn(
            ('Known provider task ID', 'Resume or reconcile that task; no new submission'),
            self.rows,
        )
        self.assertIn(
            ('Unknown submission acceptance', 'Preserve submission_unknown; reconcile before any retry'),
            self.rows,
        )
        self.assertIn(
            ('Completed task, failed download', 'Retry the existing artifact download; do not regenerate'),
            self.rows,
        )

    def test_prompt_handoff_is_chat_first_without_production_setup(self):
        for phrase in (
            'paste-ready prompt text', 'ordered reference bindings', 'model parameters',
            'No Studio initialization', 'Save prompt drafts only when requested',
            'Do not invent task IDs', 'read-only tool discovery',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.policy)

    def test_entrypoints_link_policy_before_production_and_override_old_recipes(self):
        for name in ('AGENTS.md', 'README.md', '.agents/contracts/routing.md',
                     '.agents/contracts/production-policy.md'):
            document = ROOT / name
            links = re.findall(r'\]\(([^)]*generation-access\.md)\)', document.read_text())
            with self.subTest(name=name):
                self.assertTrue(links)
                self.assertTrue(all((document.parent / link).resolve() == CONTRACT for link in links))
        self.assertIn('takes precedence over older skill recipes', self.policy)
        self.assertIn('review_mode', self.policy)
        self.assertIn('approval_mode', self.policy)
        self.assertIn('registration before submission', self.policy)
        self.assertIn('native draft-first', self.policy)


if __name__ == '__main__':
    unittest.main()
