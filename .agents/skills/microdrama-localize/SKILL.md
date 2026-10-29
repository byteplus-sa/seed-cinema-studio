---
name: microdrama-localize
description: Orchestrator for localizing delivered micro-drama with preserved sources and honest lip-sync QA. Use for a new episode language or market version. Do not use for isolated subtitles or first production.
---

# Microdrama Localize

This is an orchestrator. It sequences specialist skills for localizing a
delivered episode and owns the route choice, the gates and the handoffs. Leaf
skills stay independent; this skill names them as prose hints and the caller
loads only the ones the chosen route needs. Stage, approval, Studio and
submission rules come from `AGENTS.md` and the
[production policy](../../contracts/production-policy.md); this skill does not
relax them.

This is the retained micro-drama entry for the
[shared localization protocol](../../contracts/production-localization.md).
The generic `production-localize` entry follows the same protocol; neither
orchestrator loads the other. Keep the old skill and reference paths supported.
Use `production_post.py localization` for read-only preservation checks, never
as evidence that Studio edits were imported or listening was completed.

## Inputs and outputs

Input: the delivered episode project (`project.md`, shot manifests with locked
dialogue, takes, the final render and locks), the target language and market,
the market card entry for it if one exists, the user's preferred route,
and any glossary, names or lines the user has locked in the target
language.

Output: a localized deliverable set per target, never an overwrite of the source:

- a translation sheet of locked lines (source text, target text, register note,
  status `draft`, `user_approved` or `native_checked`);
- `<master-stem>.<language-code>.srt` sidecars for every subtitle language;
- for a re-voice or regenerate route, a new master version with its own
  Studio render, locks and delivery notes;
- a QA record and an honest list of defects and unverified items.

## What must not change

- Picture, shot order and cut timing of the approved master, unless the route is
  a full regenerate that the user chose and that gets its own review.
- Locked canon: characters, wardrobe, locations, props, and the source-language
  locked lines. Localization adds a language; it never edits the source.
- The source master and its earlier renders stay on disk. Write a new version
  (`v02`), as the render command already does.
- Speaker identity and the story beats of the hook, turn and cliffhanger.
  A translation may reorder words for the target language; it may not move a
  reveal to a different line.
- Generated footage stays text-free. Subtitles are sidecars or Studio overlays.

## Workflow

1. **Scope.** Record target language, variety, register and platform in
   `project.md` or a localization note. Ask for what is missing and would
   change the result, such as whether a native speaker will review. Do not
   assume a market from the user's name, location or request language.
2. **Inventory.** Extract every spoken line with speaker, addressee, register
   and timing from the manifests and the final timeline. Mark names, titles,
   honorifics and any word that must stay untranslated.
3. **Translate.** Draft target text line by line, keeping the register of each
   speaker pair (formal or casual address, status markers, politeness) and
   speakable length: a translated line should fit the original line's window
   at natural speed. Shorten or restructure rather than speed up. Record
   alternatives separately; the user accepts the text. Details in
   [translation and register](references/translation-and-register.md).
4. **Choose the route** for the spoken language. The default is the cheapest
   route that satisfies the user. See [routes](references/routes.md).

| Route | Spoken audio | Picture | Cost |
| --- | --- | --- | --- |
| A. Subtitles only | Source language kept | Unchanged | None beyond the sidecar |
| B. Re-voice, source soundtrack kept | New language on changed lines only | Unchanged; mouths still match the source language | One audio operation per scope |
| C. Full regenerate | New language native to the video model | New clips, new reviews | Full Seedance cost per clip, drafts first |

5. **Check the language first.** Use the native-language check in
   `seedance-prompt-25-dialogue` before any route that speaks the new language.
   A listed language can use C; an unlisted language needs a recorded route
   (annotation, a supported spoken language with subtitles, or an explicitly
   requested audio-first track) and the first take is an experiment.
6. **Subtitles.** For every route, produce the sidecars with
   `microdrama-subtitles` from the locked target text and the measured timing
   of the delivered version (subtitles follow locked words, not heard words).
7. **Execute the route** under the approval and reconciliation rules below.
8. **QA.** Run the QA checklist below on every new file. Provider success is
   `review`, not approval.
9. **Deliver.** Studio renders the new master for B and C; the sidecar rides
   beside it. Close the stages through `studio_project.py` as the policy
   requires, and update `handoff.md`.

## Approval and reconciliation

- Honor the project's `approval_mode`. A user-stated lock on text, route or
  voice is never overridden by an agent decision.
- Register every generation-bound operation with `prepare_request.py --register`
  before submission and save the acknowledged task id at once. Run
  `prompt-review` inline on every new prompt and resolve CRITICAL and MAJOR
  findings. A changed input invalidates the review.
- Never resubmit a paid operation that may already exist. After a timeout or an
  unknown acceptance, reconcile from `task_ids.json`; never retry through a
  second transport. A retry is an explicit, scoped decision with its cost.
- Draft first for Seedance (480p), reviewed and selected before any final
  generation, as the policy requires.
- Real-person likeness or voice inputs need authorized Advanced Creation Rights
  assets. Cloning a voice is a rights question; do not clone a voice without
  the speaker's authorization, and prefer voices attached to invented
  characters.
- Record available cost estimates separately from confirmed billing; missing
  estimates do not block submission and provider success is not billing evidence.
- Cultural review is separate from creative approval. Nothing is marked
  `native_checked` until a native speaker has said so in the user's words.

## QA checklist

Run per target language and route. Record pass, fail or not applicable with
evidence; unavailable evidence stays unresolved.

- **Text.** Every source line has a target line, with no unrecorded additions,
  merges or drops. Register, honorifics and names match the sheet and glossary.
  Cultural, dialect and slang items are listed `unverified` until a native
  speaker confirms; never mark `native_checked` by inference.
- **Subtitles (all routes).** Sidecar named `<master-stem>.<language-code>.srt`
  from the locked target text, not a transcript. The script report has no
  unexplained warning. One line per language viewed against the master in a real
  player, including every right-to-left or non-Latin language. No caption text
  baked into any video.
- **Speech (B and C).** Speech-to-text diff of every spoken line against the
  locked target text, word by word, with correct speaker and order; a model's
  summary is not evidence. A listening pass for pronunciation, accent, register
  and speaker identity, which a transcript cannot certify.
- **Soundtrack (B).** Music, effects and room tone from the source are intact
  and continuous across each replaced line. Each splice stays within about 10
  percent pitch and tempo, no last word is clipped, and tail silence is kept.
- **Loudness and decode.** Matched to the delivery target with peaks under the
  ceiling; clean decode; audio and video durations agree.
- **Picture and timing.** A and B: video stream identical to the source master,
  or the difference explained. C: identity, wardrobe, geography, continuity and
  the hook window re-checked on every new take. Cue and line timing measured on
  the localized master, not the source.
- **Lip-sync verdict.** Exactly one of: native (C, checked by eye),
  approximate (B, source-language mouths with a new-language voice), or not
  applicable (A). Keep `unverified` while required playback is unavailable.
  Never claim sync that was not viewed.
- **Records.** Every paid operation is in `task_ids.json` with its prompt
  snapshot and review, with no duplicate or unreconciled submission. Estimated
  and confirmed cost recorded. New masters are new versions with hashes; source
  files untouched. `handoff.md` lists route, language status, open defects and
  unverified items.

## Specialist hints (prose, not directives)

`microdrama-subtitles` writes the sidecars. `seedance-prompt-25-dialogue`
checks language support and writes dialogue direction for route C. A market
pack for the target language, if one exists, adds register depth.
`seed-audio-prompt` and `ark-mcp` cover the audio operation for route B.
`prompt-review` reviews generation-bound prompts. `micro-drama` owns the
original episode flow and assembly.

## References

| Need | Reference |
| --- | --- |
| Route choice, steps and limits | [Routes](references/routes.md) |
| Register, length fit, names and glossary | [Translation and register](references/translation-and-register.md) |
