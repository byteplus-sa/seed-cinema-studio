# Language Support

Read [the entrypoint](../SKILL.md). Check this before locking dialogue.

## Historical language guidance

The historical Seedance 2.5 guide listed Chinese, English, Spanish, Indonesian,
Malay, Thai, Arabic, Portuguese, Vietnamese, Japanese and Korean. This comes from
the Seedance 2.5 prompt guidance bundled in `seedance-prompt`
(`references/parameter-reference.md`). Inclusion or absence does not establish
support or incapability for the selected exact model, operation and destination.
Use current applicable evidence; unknown support remains unresolved.

## Routing

| Situation | Route |
| --- | --- |
| Native language support is verified for the exact binding | Preserve the native route and add delivery direction; no automatic annotation |
| Accent or variety matters | Name the requested variety and register; verify the result by listening |
| Language support is unknown, including an unlisted language | Keep approved words and the requested language; return useful direction with support unresolved |
| Applicable evidence establishes unsupported native language | Offer annotation as a hypothesis, a user-selected supported-language dub with post subtitles, or explicitly requested and supported audio-first; do not select a substitute |
| Code-switching is requested | Preserve exact words, order and register; verify each language without shortening or translating the approved passage |
| A market pack is explicitly selected | The caller may compose it for language-specific lessons; it does not establish model capability |

Return the route and its evidence for the caller's shot notes; prompt-only
writing does not create records, generate experiments or authorize submission.

## Unsupported-language rules

- Do not promise pronunciation fidelity even when language support is verified.
  An authorized take still needs playback and listening.
- Annotation is a cue outside the braces, short and evidence-based.
- A supported-language dub with subtitles in the audience's language is a valid
  production choice; it is the user's decision, not the agent's.
- Audio-first (Seed Audio track as `reference_audio`) needs explicit scope,
  a verified tool binding and duration fit.
