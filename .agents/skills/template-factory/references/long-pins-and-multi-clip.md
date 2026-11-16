# Long pins, multi-clip takes, and multi-pin batches

Read this when a pin is longer than about 20 s or has more than about 25 beats,
when its video exceeds one reliable clip, or when one run handles several pins.

## Windowed analysis for long pins

A long, dense pin can exceed the host's visual context. Plan bounded local
inspection windows before analysis:

1. Measure picture duration and hard cuts first (step 2).
2. Prefer windows of about 5-8 s aligned to confirmed hard cuts. Use as many
   as the duration requires. If a long continuous shot has no cut, use
   overlapping context around window edges and assign each beat to one owner;
   do not invent a cut at a context boundary.
3. Inspect every window with the same checklist, preferring native/local
   perception and using available understanding tools when needed. With host sub-agent
   support, delegate independent windows to native agents with unique output
   files, read-only media, explicit pin-absolute offsets and image/video input
   requirements. Otherwise work sequentially with saved checkpoints.
4. Merge the windows in order, renumber the beats, and reconcile any element
   names that differ between windows.
5. Record window spans, inspected frame paths, reviewer/runtime, uncertainty
   and completion in `analysis-windows.vNN.json`. The main agent checks gap-free
   coverage and overlap consistency, reconciles boundary action and element IDs,
   and validates the merged breakdown before freezing it.

Resume completed windows from saved evidence after interruption. Native
analysis needs no provider tasks or IDs. For optional provider tools, retain
actual task IDs/results under their contracts and reconcile ambiguous
submissions before retrying. Do not resubmit completed windows.

## Splitting video into clips

Seedance 2.5 bills per output second, so several shorter clips cost about the
same as one long clip covering the same duration. Prefer the split that keeps
each clip reliable:

| Budget per clip | Guidance |
| --- | --- |
| Hard cuts | Density estimates are provisional, not count ceilings or duration floors. Preserve source rhythm within verified request limits; use assembly for exact timing or demonstrated merging, reusing footage where possible. Additional generated clips require authorization. |
| Duration | Choose supported request durations from measured pin spans. Trim generation headroom only when separately authorized, preserving locked final timing. Preserve the source ending without adding a compulsory hold. |
| Split points | Split only on measured hard cuts. Do not split inside a whip, match cut, or continuous camera move. |

Timing rules at clip boundaries:

- Write every stage timestamp in clip-local time, and list the trim point the
  edit will use.
- A whip, fade, or other transition that must survive the edit must peak or
  finish before the trim point. A whip that crosses into the next clip needs
  both halves: the outgoing clip ends in blur and the incoming clip opens in
  blur that resolves within about 0.3 s.
- Put the final fade to black in post (FFmpeg), not in the prompt, so the trim
  cannot cut it.
- Do not plan native extension to join clips that contain people: extension and
  video inputs with generated or real people are rejected unless the
  identities are `asset://` Virtual Portrait assets. Join independent clips at
  hard cuts, matching first frames and a shared state ledger instead.

Continuity across clips:

- Give each clip a one-line state ledger at the top of its prompt. Say what the
  subject looks like at the clip's start, for example "base layer only; no
  toppings yet". For build or assembly sequences, state each stage explicitly.
- Generated clips can still show later-stage items early. Check this in QA. A
  re-order of whole shots in the edit is often cheaper than a retake. Record the
  edit list and the reason on the scene manifest.

## Continuous audio across clips

Carry the selected sound ownership into every clip request and the assembly.
Speech absence does not select post audio, and a score-led or ambient scene
does not authorize muting native sound or generating another track.

| Selected owner | Multi-clip action |
| --- | --- |
| native | Preserve requested native sound, including wordless contact effects and ambience; use verified native controls, with no automatic muting or replacement bed. |
| post | Use supported picture-only controls such as `generate_audio: false` only when verified for the selected binding. Use supplied or approved post assets; separate generation requires authorization. |
| exact master | Keep the exact master unchanged, including its hash, offset and tail. No automatic normalization, looping, trimming, padding, splicing or crossfading of the locked master. |
| mixed | Name each layer, its owner, source/hash, span and offset; preserve selected native layers alongside authorized post layers, with no duplicate bed. |
| silence | Add no bed. Use verified controls and inspect for unwanted audio; reject a mismatch or offer an authorized repair, never treat negative prompt wording as proof of silence. |

Native clips need not share tempo or key. Inspect actual seams and requested
contact sync by listening, naming each inspected range; do not infer acceptance
from a prompt or waveform. Looping whole bars, switching sources, crossfading,
padding or splicing are optional edits only within approved derivative scope,
not defaults for native sound or an exact master. If separately authorized
music generation is rejected, record the failure and diagnose before proposing
a revised request; do not repeatedly submit or silently change the sound owner.

## Assembling the clips

- Measure video-stream duration rather than container duration; record fractional
  duration, frame count, fps, cuts and timestamps. Record independent sound and
  picture spans and offsets, preserving the final word and audio tails even
  when sound ends after picture. Missing or malformed measurements mean stop
  and resolve; never guess timing from request duration.
- Preserve valid lossless intermediates in whole frames at the measured frame
  count and source timebase, including fractional seconds. Compatible picture
  intermediates may use the concat demuxer and one final encode; the concat
  filter needs `setsar=1`. Assemble sound separately at its selected offsets
  and spans, without conforming locked tails to picture or using `-shortest`
  to hide an output mismatch. Keep that mismatch unresolved until reconciled.
- Trimming generation headroom is separately authorized and must preserve
  locked final timing. Any source trim, pad, retime, splice or crossfade needs
  explicit derivative adaptation approval; `approve_for_me` does not override
  preservation locks. Record source SHA-256, derivative SHA-256, exact window,
  timing delta and audio consequences. Denied or missing adaptation approval
  leaves sources unchanged, with no derivative.
- Keep the untouched master hash, original colours and lossless intermediates.
  Apply a look only within approved look scope. Choose decode and delivery
  conform from measured pixel format, range, primaries, transfer and matrix,
  never from a codec name or 10-bit HEVC alone:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,pix_fmt,color_range,color_primaries,color_transfer,color_space -of json master.mp4
```

The measured `pix_fmt`, `color_range`, `color_primaries`, `color_transfer` and
`color_space` must agree with the source and target. Use the matching branch
of [the measured-stream conform owner](../../color-grade-palettes/SKILL.md):

| Measured source and delivery target | Conform action |
| --- | --- |
| Matching 8-bit SDR | No forced range/matrix conversion or bit-depth reduction; retain correct tags. |
| 10-bit limited BT.709 | For matching 8-bit limited BT.709 delivery only, use the retained conform recipe; reduce and dither once at final encode. |
| Matching 10-bit target | Keep high bit depth; no 8-bit reduction or dither stage. |
| Full-range, different primaries/matrix or HDR | Explicit approved color conversion or tone mapping to the target; tagging alone is not conversion. |
| Missing, unknown or conflicting | Stop and resolve using authoritative source metadata and inspection; never assume limited BT.709 or relabel an unresolved stream. |

## Multi-pin batches

When one run handles several pins:

- When the host supports sub-agents, give each pin its own native analysis
  sub-agent with explicit media inputs and perception capabilities. Otherwise
  process pins sequentially. Each analysis worker owns only
  `templates/<pin-id>/` and never edits the Studio project (or pre-Studio
  canvas `showcase.json`, `index.html`),
  `project.md`, or `ref_cache.json`.
- Native analysis does not write the provider registry. The main agent owns
  optional tool submissions, uploads and task records to prevent duplicates.
  Every generation registry
  write, by any agent, goes through the lock in
  `.agents/scripts/operation_store.py`: `registry_lock`, `read_registry`,
  `replace_registry`, or `prepare_operation`.
  `.agents/scripts/prepare_request.py --register` does this for you.
- Upload each shared element reference once, and record the object keys in
  `ref_cache.json` from the main agent.
- A pin that is fully deterministic, such as a flat motion graphic rebuilt from
  official cutouts, can go straight to a HyperFrames build from the breakdown's
  measured timing table. Only its music and effects enter prompt review.
