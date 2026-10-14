# Music and Ambience

Read [the entrypoint](../SKILL.md). Use this reference when a series needs a
consistent music bed, a recurring sting or ambience that the native Seedance audio
does not deliver. Native audio carries dialogue and scene sound by default; separate
audio is opt-in per the entrypoint's audio-preparation stage.

## Decide per project

| Need | Route |
| --- | --- |
| Dialogue and natural scene sound only | Native Seedance audio; no separate bed |
| One music identity across episodes (theme, sting, end-card tag) | A library asset under `projects/<series>/library/`, generated once and reused |
| Ambience or music that must be absent or exactly controlled | A bed generated in post and mixed over the approved picture |
| Clip where native audio added speech, chanting, cheering or a score although it was forbidden | Keep the provider master untouched; build a derived post master with a generated bed |

## Native audio can ignore a negative

In one run with `generate_audio: true` and an explicit "no music, no spoken words"
line, six of nine ambient-only clips still carried speech, chants, cheers or a
score. A negated instruction is not a guarantee. Check the delivered render, not
the draft (a final's audio is not identical to its draft), by extracting the audio
and transcribing it with `speech_to_text`; treat model-based listening as a flag
and add a human listen for anything the checks disagree about.

## Generating a bed

1. Use `seed_audio_generate` (text prompt up to 3,000 characters; optional
   `audio_references` or one image reference; `output.format`, `sample_rate`,
   `loudness_rate`). Describe the acoustic space and a timeline in positive terms,
   and close with "no voices, no music" when the bed must be ambient.
2. Name the file `amb_<scene>_<descriptor>_v01.wav` (music: `mus_`, effects:
   `sfx_`) under the project or its `library/`, per the asset-naming contract, and
   save the prompt snapshot beside it.
3. Beds are not frame-synced to the picture. Say so in the review notes and place
   them in Studio as an audio clip with explicit start and gain.
4. Under dialogue, lower the bed instead of lowering the dialogue; keep dialogue
   as the loudest element.
5. Loop or trim only at silent or low-energy points, and cross-fade the seam.

## Mix and delivery

- Mix in Studio as clips and overlays, then render; do not ship an FFmpeg-only
  mux as the final (see the production policy's final-files rule).
- Normalize to the project's single loudness target and peak ceiling and record
  both in the delivery manifest (see the audio-video alignment contract).
- A music identity reused across a series is one asset with one hash; do not
  regenerate it per episode.
- Music and voices from real people or recognizable songs need rights clearance;
  generated beds carry no such clearance for a named artist or track.
