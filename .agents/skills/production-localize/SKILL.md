---
name: production-localize
description: Orchestrator for localizing delivered films, shorts and episodes with preserved sources. Use for new language or market versions. Do not use for first production or isolated subtitle files.
---

# Production Localize

This is an explicit orchestrator. Sequence only the specialists needed for
the chosen route; the leaves never invoke each other. Follow the shared
[localization protocol](../../contracts/production-localization.md) and
[production policy](../../contracts/production-policy.md).

## Scope and Preservation

Require the delivered source master, locked source lines, canonical references,
selected unit, target language/register, rights and budget. Keep scripts,
source-language lines, canon and all earlier renders intact. Inventory their
paths and hashes before work. Source picture and timing stay unchanged for
subtitles/re-voice; regenerate is an explicitly chosen new version with new
reviews. Preserve narrative beats, quiet passages and the ending actually
supplied, never impose micro-drama structure on a film.

## Sequence

1. Record scope and the source inventory. Inventory the actual edit and line
   windows. Resolve target language, variety, register, glossary and reviewer
   availability without assuming a market.
2. Draft a line-by-line translation sheet that retains source text, speaker,
   addressee and relationship register. Record proposed alternatives separately.
   Obtain required text acceptance before generation or delivery. Keep cultural
   claims `unverified` without native-speaker evidence.
3. Choose subtitles only, line-scoped re-voice with preserved soundtrack, or
   full regenerate. Explain what picture/audio changes, estimated cost and
   lip-sync limitations. Never silently upgrade into a paid route.
4. For spoken target audio, sequence `seedance-prompt-25-dialogue` for the
   native-language check; use the actual audio tool's verified language
   capability for re-voice. Unlisted languages require a recorded experimental
   or fallback route, never a promise of native speech.
5. Sequence `subtitle-sidecars` with locked target text and measured timing.
   For re-voice, sequence audio prompt/tool work only with verified capabilities
   and rights, preserve background stems and patch changed lines only.
   For regenerate, sequence the existing video workflow with unchanged canon,
   reviewed 480p drafts and separately reviewed final takes.
6. Before any generation, sequence inline `prompt-review` and durable
   `prepare_request.py --register`. Reconcile unknown submissions from
   `task_ids.json`; never duplicate a paid operation or switch transports
   as a retry. Preserve current authorization and spending boundaries.
7. Inspect the localized output under the shared QA protocol: locked-line
   transcript comparison, listening where audible, full-cut picture/timing,
   soundtrack preservation, subtitle/player checks and honest lip-sync verdict.
   A still or transcript never establishes listening or temporal evidence.
8. Return a new versioned output set, translation sheet, QA findings and
   source-preservation record. The caller's supported Studio lifecycle owns
   rendering and mode-valid locks; this route does not add runtime edit import.

## Validation and Handoff

```bash
uv run python .agents/scripts/production_post.py localization projects/<slug> \
  --record localization/<unit>/<language>/record-v01.json --unit <unit>
```

The record validator is read-only. It checks current source/output hashes and
aliasing, not speech quality, identity, stream equality or approval authority.
Do not label a valid record a delivered or creatively approved production.
Retain `microdrama-localize` as the explicit micro-drama compatibility entry;
both entry points follow the same protocol, without recursively loading one
another.
