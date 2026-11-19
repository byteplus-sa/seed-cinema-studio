# Audio-video alignment

Native generated audio is sufficient unchanged. Preserve generated and supplied
audio by default. Finalizing, assembling or delivering a video does not authorize
normalization, gain matching, limiting, EQ, compression, ducking/carving, fades,
splicing, padding, trimming, time stretching, replacement or re-voicing.
Apply audio changes only when the user explicitly requests or approves them.
Do not suppress native audio to create a post-production workflow, including
wordless, ambience-only or score-led work. This policy applies to FFmpeg,
HyperFrames and provider-side editing alike.

Separate Seed Audio dialogue is opt-in when the user requests lip-synced dialogue audio. Otherwise use native video audio. Generate each scene at its natural duration, using the selected model/tool's current supported limits.

The following reference and timing records apply only to explicitly requested
separate lip-sync audio, not to unchanged native sound:

1. Preserve exact dialogue in both audio and video prompts; bind the chosen audio reference in each applicable shot.
2. For requested synchronization, inspect actual audio duration and line timing before video submission. Align picture to the approved audio; a mismatch needs a scoped decision, not automatic audio trimming or picture padding.
3. Persist the audio path, SHA-256, verified duration, and dialogue-to-shot alignment in the owning manifest. The generation request contains the same ordered audio reference.
4. Use second-level prompt timing when explicitly requested or necessary for the requested synchronization/editing operation. Ordinary prompt composition does not add per-shot seconds by default.
5. Replacing audio invalidates dependent review hashes. Preserve old snapshots/takes; obtain a new review for the changed request.
6. Provider success places output in `review`. Inspect lip sync, dialogue placement, audio streams and decode integrity. Record a hash-bound audio/video review; a mode-authorized agent decision or explicit user decision may approve only a passing take.

Preserve exact supplied masters, offsets and independent audio tails, including
unequal picture/audio endings. Requested silence adds no bed; use supported silent
generation or an explicitly authorized mute. Exact-master requests may need
compatible stream-copy muxing, but do not require extraction or re-encoding when
the selected operation already preserves the requested audio. Verify current
model/operation capabilities; never assume native generation preserves an exact
source recording. Disclose required transcoding or timeline adaptations and
obtain approval before making them. Keep originals and hash every derivative.

Read-only probes, decode checks, loudness measurements and listening remain
available. Validate actual streams, duration, sync and audible continuity at the
requested review depth. Loudness readings do not replace listening; unavailable
inspection remains unresolved, never permission to repair. There is no default
LUFS or peak target. An explicitly requested specification scopes measurement
and any approved correction to that deliverable.

Native audio needs no separate preparation, cue sheet, mix evidence or audio-file
lock. Its listening evidence can live in the take/final review. Skip the optional
audio-preparation stage when no separate audio work is requested. Studio render
provenance, selections and picture/final-master locks remain distinct delivery
requirements; they do not imply an audio-editing pass.
