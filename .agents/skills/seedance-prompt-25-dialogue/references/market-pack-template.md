# Market Pack Template

Read [the entrypoint](../SKILL.md). Use this when a language or market will be
produced repeatedly.

A market pack is two independent leaf skills plus an optional note in the
repository docs:

| Piece | Purpose | Model |
| --- | --- | --- |
| Story writer, for example `<market>-micro-drama` | Local formulas, honorifics, visual signifiers, subtitle rules | `filipino-micro-drama` |
| Dialogue partner, for example `seedance-prompt-25-<language>` | Pronunciation and delivery lessons, observed failures, optional audio-first route | `seedance-prompt-25-filipino` |

## Dialogue partner contents

1. `SKILL.md` with the same input and output contract as this skill.
2. `references/observed-failures.md`: a table of locked text, heard text,
   context, cue tried and result, with the evidence level stated.
3. `references/native-audio.md`: native-audio defaults for the language.
4. `references/register.md`: formality, honorifics and code-switching.
5. `evals/evals.json` and `agents/openai.yaml`.

## Rules

- Each skill stands alone; mention siblings in prose only.
- Evidence labels: recorded transcript, model listening, native-speaker
  confirmation. Never present a hypothesis as a failure.
- Do not hard-code personal paths or machine-specific details.
- Register the new skills in the README table, the catalog and
  `skills-lock.json`, then refresh integrity.

See `docs/ADD_A_MARKET.md` for the repository checklist.
