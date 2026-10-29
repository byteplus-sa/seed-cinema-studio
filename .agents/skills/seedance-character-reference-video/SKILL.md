---
name: seedance-character-reference-video
description: Write Seedance prompts for video character sheets from approved images and required authorized voice audio. Use for animated identity references. Not for still sheets or generation.
---

# Seedance Character Reference Video

Return a prompt and reference handoff for one character, not a finished scene.
This is a prompt-only leaf: do not invoke other skills, tools or subagents,
generate media, register assets, change canon or approve a take. The caller
supplies inspected inputs and owns those operations.

## Required inputs

Require both an **approved character image** and an **authorized voice
recording**. Neither is optional. If either is missing, inaccessible, empty,
unapproved or outside its authorized scope, return `incomplete`, name the gap
and ask for it. Do not write a submission-ready prompt, invent a voice,
generate replacement audio or offer a silent fallback.

The image may be a character sheet or an approved design still. A portrait
alone can support a continuous face reference; body/detail coverage requires
approved views that actually show those details.

Consume these facts from the caller:

| Input | Required facts |
| --- | --- |
| Character | Stable label, approved image version/hash, visible face, hair, build, outfit and permanent accessories; current medium |
| Voice | Recording version/hash, voice-use authorization, selected start/end, measured excerpt duration, exact verified transcript and language; bound excerpt artifact/hash or verified transport-side span |
| Binding | Ordered image/audio positions and supported reference roles; approved rights route for each input |
| Output | Requested layout, aspect ratio, duration and selected Seedance model/route, or clearly labeled proposals needing resolution |

Reuse valid authorization evidence already supplied for the same person and
scope. Image approval is not voice consent; account onboarding is not a
speaker's authorization. For licensed synthetic voices, require permission
covering this use. Do not infer identity, nationality or voice from a face.
For multiple people, ask which one the sheet is for; do not merge identities
or choose a speaker from a mixed recording.

## Audio performance contract

Default to **the selected recording's performance**, not timbre-only cloning.
Bind `@Audio 1` to the named character and the exact approved excerpt:
voice, words, language, accent, pacing, pauses and delivery. Carry its verified
words verbatim into the dialogue block. No translation, new dialogue, ad-lib,
new narrator, music or replacement voice.

- The face panel performs the supplied speech with readable mouth movement.
  Permit natural blinks and quiet breaths around the recording's delivery;
  do not impose a closed jaw or a different emotion over speech.
- Require listening/transcription evidence from the caller. If the transcript
  is unknown or disputed, ask for verification rather than guessing from a
  filename. Silence, music-only or unintelligible audio does not supply a
  usable vocal performance.
- Bind only the approved excerpt. For a span inside a longer recording, require
  the caller's prepared excerpt artifact and hash, original source hash,
  selected timestamps and preparation record, or verified transport-side span
  support. Prompt timestamps alone do not trim an upload. Validate limits
  against what is actually transmitted; never send an over-limit full recording
  while claiming only its short excerpt counts. An already isolated approved
  recording can be bound unchanged with its existing hash.
- Fit the measured excerpt, onset and tail within the supported output
  duration. Do not force a ten-second result, accelerate speech, trim words,
  loop the recording, or add undisclosed padding. Agreed visual lead-in and tail
  may surround the unchanged vocal excerpt; record their timing explicitly.
  Propose an approved shorter excerpt or longer supported output when needed.
- For new words or timbre-only reuse, ask for a revised explicit performance
  contract and approved script before proceeding; never silently switch modes.
- Request `generate_audio: true` with a supported audio-reference route.
  A prompt requests matching performance; it does not guarantee waveform
  preservation, exact timing or successful lip sync. If the route cannot
  honor the requirement, return the gap, not a silent/post-dub substitute.

## Visual design

For an animated-sheet request without a different layout, propose a
**two-panel sheet**: a persistent, readable face close-up on the right and
body/detail coverage on the left. Label this default and preserve explicit
layout locks. These are simultaneous views of the same character, not twins,
a conversation or a new second person.

1. Lock the approved appearance and medium. Never copy a demonstration
   character's hair, costume, accessories, voice or name into another project.
2. Keep a neutral studio background and stable, even light. In both panels,
   cameras stay locked between declared left-panel cuts; no orbit, roaming
   camera, zoom or transition affects the face panel.
3. Start the left panel with a readable full-body view and modest turn only
   through supported views. Then show selected costume/material, face/ear,
   hand/accessory and footwear details that actually exist in the source.
   Do not demand unseen rear details or claim a complete 360-degree design
   from a front image. Ask for approved additional views if needed.
4. Keep the right face visible for the full duration, with a small natural
   head adjustment and audio-led performance. Preserve identity across both
   panels. Do not change outfit, add props, text, labels or music.
5. Use explicit time ranges for this synchronized detail sequence. Allocate
   them to the measured vocal excerpt and readable visual holds; reduce
   detail coverage only as a proposal when the clip is too short.

For a requested **continuous reference**, retain one subject in one uninterrupted
view with restrained head/body movement and the same required vocal performance.
Do not add panels or detail cuts. Treat it as a different layout, not a proven
improvement over the split-panel reference.

Use [prompt patterns](references/prompt-patterns.md) for the selected layout.
Replace placeholders only with supplied facts; unresolved facts stay in the
handoff's gap list, never disguised as approved content.

## Transport and scope boundaries

- Distinguish the source design sheet from transport inputs. A sheet is
  creative authority, not automatic permission to upload a collage. When the
  authorized route requires one image per view, the caller prepares approved
  separate views with source lineage and maps each `@Image N` explicitly.
  Do not submit a multi-panel strip as a registered single-view asset.
- Require the caller's supported route for real-person likeness and voice,
  including authorized Active assets where required. Reuse valid existing
  assets; never misclassify a real person as invented or alter an input to
  evade a privacy rejection. Asset IDs belong in transport, not prompt text.
- This is image-plus-audio creation, not source-video editing. It does not
  relax the muted-source contract for recast, swap or restyle. An output
  soundtrack is not automatic permission for later voice reuse.
- Keep the approved still as canonical identity. The video is a supplemental
  candidate; current Studio image selection does not become video selection.
  Do not replace `selected_variant` with an MP4 or claim Studio video-canon
  support. Downstream video identity binding needs separate provider
  validation, explicit attribute roles and a decision for that use.
- Do not claim the example's model provenance, guaranteed identity consistency
  or a measured improvement from the format alone.

## Return to the caller

1. `ready` or `incomplete` for **prompt authoring only**, with gaps/questions.
   `ready` is not generation, rights or creative approval.
2. A source/binding table with image and audio roles, version/hash, excerpt,
   transcript, authorization evidence and unresolved transport requirements.
3. The layout and timed visual/audio plan, followed by the resolved prompt
   only when required inputs and material choices are settled.
4. A request handoff: selected model/route, duration/aspect, ordered references,
   `generate_audio: true`; for Seedance 2.5, `resolution: "480p"` and boolean
   `draft: true`. The caller owns durable submission, independent review and
   approval modes, task IDs and later reviewed promotion.
5. Acceptance checks: decode and probe streams/duration; inspect both panels,
   identity, clothing/accessories, cuts and face readability; listen against
   the approved audio and transcript; inspect lip sync, onset/tail, unwanted
   words/music and voice drift. Recheck promoted output, including its audio.
   An audio stream alone is not a listening pass; unseen/unheard results remain
   unassessed. Source changes invalidate dependent prompt/review evidence.
