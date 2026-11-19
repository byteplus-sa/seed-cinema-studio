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
| Requested silence | Supported silent generation or explicitly approved muting; no bed |
| Explicitly requested separate music or ambience | A scoped post layer; preserve any supplied exact master |
| Clip with unwanted native sound | Keep the provider master untouched, report the defect and obtain a scoped repair or retake decision |

## Native audio can ignore a negative

In one run with `generate_audio: true` and an explicit "no music, no spoken words"
line, six of nine ambient-only clips still carried speech, chants, cheers or a
score. A negated instruction is not a guarantee. Check the delivered render, not
the draft (a final's audio is not identical to its draft), through actual listening
and speech-to-text when relevant; extract only if the chosen diagnostic needs it. Treat model-based listening as a flag
and add a human listen for anything the checks disagree about.

## Generating a bed

Only when the user explicitly requests or approves a separate bed:

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
5. Loop, trim or cross-fade only within the approved audio-edit scope.

## Mix and delivery

- For requested mixing, assemble in Studio as clips and overlays, then render; do not ship an FFmpeg-only
  mux as the final (see the production policy's final-files rule).
- Native audio is sufficient unchanged. No default normalization, target,
  limiter or carve is required (see the audio-video alignment contract).
- A music identity reused across a series is one asset with one hash; do not
  regenerate it per episode.
- Music and voices from real people or recognizable songs need rights clearance;
  generated beds carry no such clearance for a named artist or track.
