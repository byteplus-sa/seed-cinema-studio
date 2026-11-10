---
name: setup
description: Interview users and remember local Studio preferences. Use for /setup, onboarding, changing defaults or remember my preferences. Not for credentials, installing tools or starting production.
---

# Set Up Studio Preferences

Use [workspace preferences](../../contracts/workspace-preferences.md) and the
trusted `.agents/scripts/workspace_preferences.py` helper. This is an
interactive preference interview, not MCP installation or production intake.
Literal slash commands depend on the host runtime; "run setup" and ordinary
durable-preference requests use the same workflow.

## Start With Existing Choices

Read the workspace defaults and, only when explicitly selected, production
overrides. Prefer already installed Python 3.11+:

```bash
python3 -B .agents/scripts/workspace_preferences.py show
python3 -B .agents/scripts/workspace_preferences.py show --project <project-id>
```

Commands run from the workspace root; `--root <absolute-workspace>` belongs
before `show` or `set`. The helper needs the standard library only, not uv,
Git or MCP, plus no-follow descriptor-relative filesystem operations.
Unsupported runtimes, including standard Windows Python, use the native-file-tool
fallback with the exact contract format and explicit write-guarantee limits.
If safe containment cannot be established, remain chat-only and report that
nothing was saved. Never install Python or dependencies without a separate request.

If preferences already exist, summarize them and ask what to change rather
than repeating onboarding. A user who already supplies clear choices need
only resolve missing scope or genuine conflicts. Honor prior approval for the
same save. Invalid local state is a repair question, not permission to reset.

## Interview In Small Batches

Ask two or three questions per turn, with plain-language options and a skip/
keep-current option. Offer workspace-wide defaults first, plus overrides for
an explicitly named production. Skip unrelated questions, allow free-text
answers and never require the whole questionnaire before writing prompts.

| Question | Options and mapping |
| --- | --- |
| Where should these choices apply? | This workspace, recommended; or one named production |
| What should the agent do by default? | Prompts only, recommended on first setup (`prompt_only`); or agent assistance (`agent`) |
| What matters most for future generation? | Faster results (`fast`), balanced, recommended (`balanced`), or higher quality (`quality`) |
| May the agent propose another verified model? | Keep the workspace model, recommended (`workspace_default`); or allow verified alternatives (`allow_verified_alternatives`) |
| How much checking do you want? | Lightweight/default, recommended (`default`); or detailed/strict (`strict`) |
| Who chooses passing creative results? | Agent selects, recommended (`approve_for_me`); or ask you (`ask_for_approval`) |
| How should prompts be delivered? | Concise and paste-ready, recommended (`concise`); or detailed explanation (`detailed`) |
| Any language, tone, visual style or recurring aspect? | User-supplied values only; otherwise leave unset |
| Any other preferences to remember? | Named, nonsensitive creative/workflow choices in `custom`; optional |

In prompt-only mode, explain that generation settings are future preferences,
not a reason to generate. Offer to skip them or save them now. No paid probe,
credential setup, asset download, production directory or manifest is required.

"Fast" is independent of review and approval. It does not guarantee latency,
automatically change models, generate extra variants or bypass native drafts,
rights, consent, locks, required review or task recovery. Explain these
boundaries briefly when relevant instead of asking a separate safety quiz.

## Confirm And Save

Show only the proposed changes, their scope and effects. On first setup,
"keep recommended defaults" explicitly accepts the displayed proposal,
including `prompt_only`; silence or merely skipping the interview does not.
Ask for confirmation unless the user has already explicitly authorized
remembering the same values in the same scope.

Use a small patch, preserving unrelated settings. Take the revision returned
by the latest `show` for the scope being edited:

```bash
python3 -B .agents/scripts/workspace_preferences.py set \
  --patch '{"execution_mode":"prompt_only","generation_priority":"fast"}' \
  --expected-revision <revision-or-absent> --confirm
```

For a production override, add `--project <project-id>` after `set`.
Use `null` to remove an override and inherit its parent/default again;
individual `custom` entries support the same operation. Re-read and reconcile
on stale revision or a writer lock; do not force a write.

Read back and report what was actually saved. The ignored
`.agents/local/preferences.json` and `.agents/local/projects/<project>/preferences.json`
files persist across sessions and repository updates, not other workspaces.
Do not modify global agent rules, credentials, model bindings, existing
production briefs or selected assets. Preferred review/approval modes apply
when creating a future brief; active brief changes require separate scope.

## Later Changes And Task Overrides

For `/setup` again, "remember I prefer short prompts", or "use prompt mode
for this workspace", update only the requested fields. Do not infer permanent
preferences from one task, copy raw conversation logs or persist private facts.
Offer confirmation for an ordinary ambiguous preference mention.

"Use agent mode for this task" overrides a saved prompt-only default only for
that task, still requiring usable tools and explicit generation scope. It
does not update the stored preference. A conflicting generic "generate this"
requires clarification. Saving `agent` never authorizes automatic CLI fallback
when MCP is unavailable. Reconcile already-submitted operations in both modes.

Report unavailable writes or checks honestly. Setup completion means the
preferences were saved and read back, not that any model, provider, runtime or
production workflow was tested.
