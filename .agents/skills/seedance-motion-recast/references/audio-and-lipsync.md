# Audio and Lip-Sync

Focused reference for `seedance-motion-recast`. Read [the entrypoint](../SKILL.md)
for mode selection, gates and caller responsibilities.

- [Audio preservation](#audio-preservation)
- [Post-audio routes](#post-audio-routes)
- [Re-voicing over the kept soundtrack](#re-voicing-over-the-kept-soundtrack)
- [Speaker ownership](#speaker-ownership)
- [Preparing source audio](#preparing-source-audio)
- [Lip-sync QA](#lip-sync-qa)

## Audio preservation

Native generated audio is sufficient unchanged. Bind the selected source as
`@Video 1` without requiring a mute, extract or mux. Verify audio behavior for
the exact model, operation and transport. For a source-preserving request:

```text
[Audio]
Preserve the source soundtrack and its timing; change only the requested picture.
```

This is intent, not a guarantee that a provider preserves an exact recording.
An exact-master request needs verified preservation or an approved compatible
stream-copy route. Unknown support stays unresolved. Requested silence or
post-owned audio can use supported audio-disabled generation within that scope.
Follow the [video-to-video inputs contract](../../../contracts/video-to-video-inputs.md#audio-preservation).

## Post-audio routes

These capabilities apply only to explicitly requested audio changes. Native
audio needs no separate preparation, post route or mix evidence.

| Route | Use when | Source | Lips |
| --- | --- | --- | --- |
| **Original** | The user requires the exact source recording and the selected operation cannot retain it | Approved stream-copy transport from the source | New mouths follow the source mouth motion |
| **New** | The brief asks for new music, SFX, ambience or voice | Seed Audio or an approved library track | No on-screen speech, or a re-voiced line |
| **Mixed** | Keep the source dialogue, replace the bed (or the reverse) | Separated stems plus new audio | Kept dialogue follows the source mouth motion |
| **Re-voiced** | New words, language or voice | Post voice overlay with `ffmpeg` and `seed-audio-prompt` | Check sync; lip-sync work is opt-in |

Voice rules:

- Keeping a real person's recorded voice, or cloning its timbre for a new
  character, requires that person's recorded voice consent, separate from
  footage rights. See the
  [production policy](../../../contracts/production-policy.md).
- Separate lip-sync audio is opt-in. When the user asks for it, follow the
  [audio-video alignment contract](../../../contracts/audio-video-alignment.md).
- When lips are off-screen or not the focus, a voice overlay in post avoids
  re-rendering the mouth.

## Re-voicing over the kept soundtrack

An explicitly requested Re-voiced or Mixed route changes only the authorized
words, voice or layers. Keep source music, ambience and effects otherwise.
Report a pronunciation defect and agree the repair scope before editing.
Do not prescribe word surgery, fades or normalization as a finalization step.
Inspect the source, record approved changes and preserve untargeted sound.
When replacement audio needs transport, prefer compatible stream copy and
disclose any required transcode. Listen to the result and record source/output
hashes; measurements alone do not prove voice or performance preservation.

## Speaker ownership

Speech windows come from the subject map or your own inspection. Map each
window to one named character. A line whose speaker is removed or turned into a
background extra needs an explicit decision: cut the line, give it to a mapped
character, or keep it off-screen.

## Preparing source audio

1. Prepare only derivatives needed for an explicitly requested audio edit or
   approved provider adaptation. Record source and derivative hashes.
2. For an authorized Mixed route, separate voice and background with the VOD voice
   separation tool. Record the task ID, output hashes and time range.
3. Preserve independent audio tails. A probe does not authorize trimming the
   delivery soundtrack; any timing change needs its own approved scope.
4. Transcribe kept dialogue with speech-to-text and keep the word timings as the
   reference for lip-sync QA.

## Lip-sync QA

Apply to the actual output when any character speaks on screen, with or without a mux:

- Transcribe the final audio with `speech_to_text` and diff it against the
  intended lines; the transcript is the authority for words. Kept dialogue
  matches the source; replaced or translated lines match the approved script.
  Accent and pronunciation verdicts need a native listener, not a model.
- Each line comes from the mapped character's mouth, never from a removed
  subject or an extra.
- Step through close frames on plosives (p, b, m) and open vowels; mouth shapes
  land on the audible sounds.
- Measure the audio-to-mouth offset at two or three syllables. An offset that
  grows across the clip suggests a duration mismatch between picture and audio.
- Listen in full. Loudness readings and waveforms do not replace listening.
- Report visible drift and offer a scoped repair or retake. Do not perform an
  unrequested re-voice or accept the failure silently.
