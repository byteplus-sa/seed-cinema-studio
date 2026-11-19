---
name: sound-post
description: Write cue sheets, mix decisions and listening evidence for an edit. Use for dialogue, ambience, score or sound-post planning and review. Do not use for audio generation or rendering.
---

# Sound Post

Act as an independent leaf. Write cue sheets, mix decisions and evidence;
never invoke sibling skills, call providers, mix media or render. Follow the
[post contract](../../contracts/production-post.md).

Native generated audio is sufficient unchanged. A separate cue sheet, mix
record or audio preparation artifact is not a finalization prerequisite.
Use this skill for requested planning, audio-edit decisions or listening reports;
native listening evidence may stay in the take/final review.

## Inputs

Read the explicit edit record and hash, actual master or stems when available,
locked dialogue, sound intent, rights restrictions and any explicitly requested
loudness/peak specification. Do not invent a target or block on its absence.
No audio input means planning
only, not a listening pass.

Consume early sound/editorial intent from the brief: what sound leads, reveals,
withholds or emphasizes and where silence matters. Early planning needs no
finished assets or invented cue times. Once the edit exists, conform final
cues to measured timing and assess their intended effect by actual listening.

## Procedure

1. Map each cue to measured edit time with ID, kind, start/end, narrative intent,
   source asset/hash when acquired and planned gain. List dialogue, ambience,
   music, effects and deliberate silence separately. An unacquired cue has no
   source reference; never fill one with a pretend file.
2. Preserve dialogue intelligibility and speaker identity. Specify ambience
   continuity across cuts and requested score entrances/exits or transitions
   in `mix_notes`. Ducking or other processing needs explicit user scope. Do not rebuild a source soundtrack
   when only a scoped dialogue repair is requested.
3. Write `sound/<unit>/cues.json` bound to the exact editorial JSON. Keep
   proposed gains separate from measured loudness. Overlapping cues are normal
   in a mix; every cue still stays within the edit's duration.
4. Listen to the relevant full mix and critical transitions when playback is
   available. Evidence records exact media paths/hashes, method, observer,
   covered ranges, findings and limits. Transcripts do not certify accent,
   pronunciation, timbre, music balance or splice quality.
   Judge the project-specific attention and ending criteria as well as
   intelligibility and loudness. Record timestamped evidence; technical
   measurements alone do not establish the intended artistic response.
5. Keep `listening.status` as `unverified` until actual listening evidence
   exists. Wordless footage may still have sound and requires listening.
   `not_applicable` needs an intentionally silent cut and a rationale, not a
   missing tool.
6. Return cue decisions, delivery measurements if actually available,
   defects and execution handoffs. Offer scoped alternatives for wrong words;
   do not prescribe splicing or re-voicing without the user's audio-editing
   decision. Preserve untargeted sound and inspect actual voice and continuity
   for any authorized edit. Measurements alone never establish repair quality.

```bash
uv run python .agents/scripts/production_post.py sound projects/<slug> \
  --record sound/<unit>/cues.json --unit <unit>
```

## Outputs

Return the cue record plus versioned listening/mix notes. Preserve source
masters and stems. The calling orchestrator owns acquisition, generation,
FFmpeg/Studio execution, new master versions and mode-valid audio approval.
Validation checks references and structure only; it neither listens nor
implements cues on the Studio timeline.
