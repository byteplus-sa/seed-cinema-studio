# Language Support

Read [the entrypoint](../SKILL.md). Check this before locking dialogue.

## Natively supported spoken languages

Seedance 2.5 natively supports Chinese, English, Spanish, Indonesian, Malay,
Thai, Arabic, Portuguese, Vietnamese, Japanese and Korean. This list comes from
the Seedance 2.5 prompt guidance bundled in `seedance-prompt-25`
(`references/parameter-reference.md`). Capability lists change; confirm
against current tool or model evidence before a paid submission.

## Routing

| Situation | Route |
| --- | --- |
| Language is on the list | Native audio with delivery direction. No annotation needed |
| Language is on the list, accent or variety matters | Name the variety and register; treat accent as a request to verify by listening |
| Language is not on the list (for example Hindi, Bengali, Swahili) | Pick one: pronunciation annotation in the prompt; a supported spoken language with subtitles in the target language; or, only if the user requests lip-synced audio, an audio-first track |
| Code-switching between a supported and an unsupported language | Keep the unsupported words short, mid-sentence and at normal volume; subtitle the rest |
| A market pack exists for the language | Compose with it for language-specific lessons |

Record the chosen route in the shot notes so reviewers know a language
decision was made rather than assumed.

## Unsupported-language rules

- Do not claim the model will pronounce an unlisted language correctly. The
  first take is an experiment.
- Annotation is a cue outside the braces, short and evidence-based.
- A supported-language dub with subtitles in the audience's language is a valid
  production choice; it is the user's decision, not the agent's.
- Audio-first (Seed Audio track as `reference_audio`) needs explicit scope,
  a verified tool binding and duration fit.
