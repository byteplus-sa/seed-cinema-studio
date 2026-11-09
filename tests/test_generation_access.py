import re
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / '.agents/contracts/generation-access.md'

ENTRYPOINT_REQUIREMENTS = {
    'AGENTS.md': (
        'Before generation or production setup, follow',
        'Without usable `ark-mcp`, return paste-ready prompts',
        'do not automatically fall back to Ark CLI or initialize a production project',
        'Connected MCP still requires explicit generation scope',
        'This policy overrides older skill fallback and production-setup recipes',
    ),
    'README.md': (
        'No usable `ark-mcp` connected?',
        'No generation credentials, Studio project, asset locks or production setup are required',
        'Connection alone does not authorize generation',
        'There is no automatic CLI fallback',
    ),
    '.agents/contracts/routing.md': (
        'before these routes or any production setup',
        'No usable MCP means prompt handoff unless the user explicitly selects a usable alternative',
        'Connection alone never authorizes generation',
        'older automatic fallback recipes do not apply',
        '| MCP unavailable or unusable before submission | Prompt handoff in chat; no automatic Ark CLI fallback or production setup |',
    ),
    '.agents/contracts/production-policy.md': (
        'before starting this lifecycle',
        'Without usable MCP or an explicitly requested usable alternative transport, deliver prompts in chat',
        'Prompt handoff does not require Studio, manifests, registration or production locks',
        'The production requirements below apply to authorized production, not to a writing-only handoff',
    ),
}

ENTRYPOINT_BOUNDARIES = {
    'AGENTS.md': r'^## Production invariants$',
    'README.md': r'^## (?:Getting started|Production routing)$',
    '.agents/contracts/routing.md': r'^\| Intent \| Route \|$',
    '.agents/contracts/production-policy.md': r'^## ',
}


def active_markdown(contents: str) -> str:
    lines = []
    fence = ''
    for line in contents.splitlines():
        marker = re.match(r'^ {0,3}(?:> {0,3})*(`{3,}|~{3,})(.*)$', line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = ''
            continue
        if marker:
            fence = marker[1]
            continue
        lines.append(line)
    if fence:
        raise ValueError('Unclosed Markdown fence')
    return '\n'.join(lines)


def policy_table_rows(contents: str) -> set[tuple[str, ...]]:
    lines = active_markdown(contents).splitlines()
    rows = set()
    for header in (('MCP availability', 'Request', 'Action'), ('Existing operation', 'Action')):
        positions = [
            index for index, line in enumerate(lines)
            if line.strip().startswith('|')
            and tuple(cell.strip() for cell in line.strip().strip('|').split('|')) == header
        ]
        if len(positions) != 1:
            raise ValueError(f'Expected exactly one policy table: {header}')
        start = positions[0]
        if start + 1 >= len(lines):
            raise ValueError(f'Missing table separator: {header}')
        separator = tuple(cell.strip() for cell in lines[start + 1].strip().strip('|').split('|'))
        if len(separator) != len(header) or any(re.fullmatch(r':?-{3,}:?', cell) is None for cell in separator):
            raise ValueError(f'Invalid table separator: {header}')
        keys = set()
        for line in lines[start + 2:]:
            if not line.strip().startswith('|'):
                break
            row = tuple(cell.strip() for cell in line.strip().strip('|').split('|'))
            if len(row) != len(header) or not all(row):
                raise ValueError(f'Invalid policy row: {row}')
            if row[:-1] in keys:
                raise ValueError(f'Duplicate decision key: {row[:-1]}')
            keys.add(row[:-1])
            rows.add(row)
        if not keys:
            raise ValueError(f'Empty policy table: {header}')
    return rows


class GenerationAccessPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = active_markdown(CONTRACT.read_text(encoding='utf-8'))
        self.rows = policy_table_rows(self.policy)

    def test_decision_tables_contain_exactly_the_expected_conditions(self):
        self.assertEqual({row[:-1] for row in self.rows}, {
            ('Any', 'Prompt-only request'),
            ('Unavailable', 'No explicit alternative transport'),
            ('Unusable', 'No explicit alternative transport'),
            ('Usable', 'No generation consent'),
            ('Usable', 'Explicit generation scope'),
            ('Any', 'Explicit Ark CLI generation'),
            ('Any', 'Explicit HTTP/curl generation'),
            ('Known provider task ID',),
            ('Unknown submission acceptance',),
            ('Completed task, failed download',),
        })

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
        for name, requirements in ENTRYPOINT_REQUIREMENTS.items():
            document = ROOT / name
            contents = active_markdown(document.read_text(encoding='utf-8'))
            links = list(re.finditer(r'\]\(([^)]*generation-access\.md)\)', contents))
            normalized = ' '.join(contents.split())
            with self.subTest(name=name):
                self.assertTrue(links)
                self.assertTrue(all((document.parent / link[1]).resolve() == CONTRACT for link in links))
                boundary = re.search(ENTRYPOINT_BOUNDARIES[name], contents, re.MULTILINE)
                self.assertIsNotNone(boundary)
                self.assertLess(links[0].start(), boundary.start())
                for requirement in requirements:
                    self.assertIn(requirement, normalized)
                for obsolete in (
                    'use an equivalent available CLI surface',
                    'Equivalent Ark CLI transport',
                    'Equivalent CLI fallback',
                ):
                    self.assertNotIn(obsolete.casefold(), normalized.casefold())
        self.assertIn('takes precedence over older skill recipes', self.policy)
        self.assertIn('review_mode', self.policy)
        self.assertIn('approval_mode', self.policy)
        self.assertIn('registration before submission', self.policy)
        self.assertIn('native draft-first', self.policy)


class GenerationAccessRegressionTests(unittest.TestCase):
    def setUp(self):
        self.documents = {
            ROOT / name: (ROOT / name).read_text(encoding='utf-8')
            for name in (
                '.agents/contracts/generation-access.md', 'AGENTS.md', 'README.md',
                '.agents/contracts/routing.md', '.agents/contracts/production-policy.md',
            )
        }

    def policy_result(self, replacements):
        original_read = Path.read_text

        def read_document(path, *args, **kwargs):
            if path in replacements:
                return replacements[path]
            return original_read(path, *args, **kwargs)

        result = unittest.TestResult()
        with patch.object(Path, 'read_text', new=read_document):
            unittest.defaultTestLoader.loadTestsFromTestCase(GenerationAccessPolicyTests).run(result)
        return result

    def test_current_documents_pass_policy_checks(self):
        result = self.policy_result({})
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)

    def test_restored_fallback_entrypoints_with_valid_links_are_rejected(self):
        for document in self.documents:
            if document == CONTRACT:
                continue
            target = '.agents/contracts/generation-access.md' if document.parent == ROOT else 'generation-access.md'
            restored = (
                'If MCP is unavailable before submission, use an equivalent available CLI surface.\n'
                f'[Generation access]({target})\n'
            )
            with self.subTest(document=document.name):
                self.assertFalse(self.policy_result({document: restored}).wasSuccessful())

    def test_fallback_added_beside_current_gate_is_rejected(self):
        for document, contents in self.documents.items():
            if document == CONTRACT:
                continue
            mutated = contents + '\nIf MCP is unavailable, use an equivalent available CLI surface.\n'
            with self.subTest(document=document.name):
                self.assertFalse(self.policy_result({document: mutated}).wasSuccessful())

    def test_fenced_policy_links_do_not_satisfy_entrypoint_checks(self):
        for document, contents in self.documents.items():
            if document == CONTRACT:
                continue
            pattern = r'\[Generation access\]\([^)]*generation-access\.md\)'
            links = re.findall(pattern, contents)
            self.assertTrue(links)
            mutated = re.sub(pattern, 'Generation access', contents)
            mutated += '\n````markdown\n' + '\n'.join(links) + '\n````\n'
            with self.subTest(document=document.name):
                self.assertFalse(self.policy_result({document: mutated}).wasSuccessful())

    def test_fenced_expected_rows_cannot_mask_changed_active_decisions(self):
        changes = (
            ('| Unavailable | No explicit alternative transport | Prompt handoff |', 'Ark CLI generation'),
            ('| Known provider task ID | Resume or reconcile that task; no new submission |', 'Submit again'),
            ('| Unknown submission acceptance | Preserve submission_unknown; reconcile before any retry |', 'Retry now'),
            ('| Completed task, failed download | Retry the existing artifact download; do not regenerate |', 'Regenerate'),
        )
        for expected_row, wrong_action in changes:
            changed_row = expected_row.rsplit('|', 2)[0] + f'| {wrong_action} |'
            for fence in ('```', '~~~', '````'):
                mutated = self.documents[CONTRACT].replace(expected_row, changed_row)
                mutated += f'\n{fence}markdown\n{expected_row}\n{fence}\n'
                with self.subTest(row=expected_row, fence=fence):
                    self.assertFalse(self.policy_result({CONTRACT: mutated}).wasSuccessful())

    def test_duplicate_decision_keys_are_rejected_even_with_matching_actions(self):
        expected_row = '| Unavailable | No explicit alternative transport | Prompt handoff |'
        for duplicate in (expected_row, '| Unavailable | No explicit alternative transport | Ark CLI generation |'):
            mutated = self.documents[CONTRACT].replace(expected_row, expected_row + '\n' + duplicate)
            with self.subTest(duplicate=duplicate):
                self.assertFalse(self.policy_result({CONTRACT: mutated}).wasSuccessful())

    def test_fenced_historical_examples_do_not_change_current_policy(self):
        for document, contents in self.documents.items():
            mutated = contents + '\n~~~markdown\nuse an equivalent available CLI surface\n'
            mutated += '| Unavailable | No explicit alternative transport | Ark CLI generation |\n~~~\n'
            with self.subTest(document=document.name):
                result = self.policy_result({document: mutated})
                self.assertTrue(result.wasSuccessful(), result.errors + result.failures)

    def test_generation_gate_only_in_example_is_rejected(self):
        for name, requirements in ENTRYPOINT_REQUIREMENTS.items():
            document = ROOT / name
            instruction = requirements[0]
            pattern = r'\s+'.join(re.escape(word) for word in instruction.split())
            mutated, count = re.subn(pattern, 'Historical guidance', self.documents[document], count=1)
            self.assertEqual(count, 1)
            mutated += f'\n```markdown\n{instruction}\n```\n'
            with self.subTest(document=document.name):
                self.assertFalse(self.policy_result({document: mutated}).wasSuccessful())

    def test_policy_link_moved_after_production_is_rejected(self):
        for document, contents in self.documents.items():
            if document == CONTRACT:
                continue
            pattern = r'\[Generation access\]\([^)]*generation-access\.md\)'
            links = re.findall(pattern, contents)
            mutated = re.sub(pattern, 'Generation access', contents) + '\n' + '\n'.join(links)
            with self.subTest(document=document.name):
                self.assertFalse(self.policy_result({document: mutated}).wasSuccessful())

    def test_blockquoted_fenced_gate_does_not_count_as_active_instructions(self):
        document = ROOT / '.agents/contracts/production-policy.md'
        contents = self.documents[document]
        boundary = re.search(r'^## ', contents, re.MULTILINE).start()
        gate = ' '.join(contents[:boundary].split())
        for prefix in ('> ', '> > '):
            mutated = f'{prefix}```markdown\n{prefix}{gate}\n{prefix}```\n' + contents[boundary:]
            with self.subTest(prefix=prefix):
                self.assertFalse(self.policy_result({document: mutated}).wasSuccessful())


class GenerationAccessParsingTests(unittest.TestCase):
    def test_shorter_and_other_fence_markers_do_not_close_an_example(self):
        contents = 'Before\n````markdown\n```\n~~~\nExample\n````\nAfter'
        self.assertEqual(active_markdown(contents), 'Before\nAfter')

    def test_unclosed_fence_fails_instead_of_hiding_active_policy(self):
        for contents in ('```markdown\nExample', '   ~~~\nExample'):
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                active_markdown(contents)

    def test_empty_and_fenced_only_contracts_have_no_authoritative_tables(self):
        policy = CONTRACT.read_text(encoding='utf-8')
        for contents in ('', f'```markdown\n{policy}\n```'):
            with self.subTest(empty=not contents), self.assertRaises(ValueError):
                policy_table_rows(contents)

    def test_malformed_or_duplicate_authoritative_tables_are_rejected(self):
        policy = CONTRACT.read_text(encoding='utf-8')
        header = '| MCP availability | Request | Action |'
        mutations = (
            policy.replace('| --- | --- | --- |', '| invalid | --- | --- |'),
            policy.replace('No explicit alternative transport | Prompt handoff |', '| Prompt handoff |', 1),
            policy.replace('No explicit alternative transport | Prompt handoff |', 'No explicit alternative transport |', 1),
            policy + '\n' + header + '\n| --- | --- | --- |\n| Any | Other | Generate |\n',
        )
        for contents in mutations:
            with self.subTest(contents=contents[-80:]), self.assertRaises(ValueError):
                policy_table_rows(contents)


if __name__ == '__main__':
    unittest.main()
