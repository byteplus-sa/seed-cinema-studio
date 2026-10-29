# Production Recipe

Read [the entrypoint](../SKILL.md). Use this reference from canon through
delivery. These are working practices, not provider guarantees. Confirmed
casting, medium, scene structure and timing override creative defaults here;
approval, rights, review and submission gates remain unchanged.

`review_mode: default` (also when absent) uses minimal inline preflight and
final-output sanity, not the full QA gates below. Strict retains those gates.
Explicit required checks and supplied reports remain binding in either mode.
Approval authority is independent; never invent listening or user acceptance.

## Canon

- Character sheets: three-panel identity sheets on a neutral background with
  full wardrobe and every always-worn item visible in each panel. Reject a
  candidate whose accessories move between wrists or panels.
- Preserve the brief's approved age, features, expression and medium, including
  weary or weathered characters. Check identity and readability at delivery
  size; do not require bright eyes, soft faces or warm, endearing elders.
  Character morality does not prescribe attractiveness.
- Spread a natural range of complexions and hair silhouettes across the cast
  instead of one shared tone, so each character is distinct at thumbnail size.
- Location plates: empty establishing views that fix the landmarks the story
  needs (which side the stairs are on, where the door opens).
- Props: only story-critical objects such as proof documents, a box, an
  envelope or a mark on the skin get a sheet. Describe every other recurring
  object positively as plain ("plain cream envelope, smooth unmarked paper"),
  because generic jars, cases, folders and labels grow invented lettering.
- One Seedream image per element in default, three samples in strict, unless
  another count is requested; inspect what was actually generated.

## Storyboards

Optional planning and review boards. For a scene board, derive the panel count
from its L1/L2/L3 level (L2 by default), rather than a fixed grid count. **Never bind a
storyboard grid or panel as a Seedance reference.** Boards with corner
numerals can leak digits into the top-left of shots even with a "do not copy
panel numbers" clause, and sketch or watercolour looks can bleed into the
footage. Translate each panel's framing, blocking
and end state into the clip prompt text instead. Skip the stage when the shot
plan already carries the staging.

## Clip prompt

Build with `seedance-prompt-25` from the scene's shot plan: each internal shot
keeps its planned size, angle, camera move and light direction, and the hook,
turn and cliffhanger each get the plan's most distinct shot. A close-up
cliffhanger can hold still as a recorded `contrast_hold` after motion. Bind
element references (character sheets, location plates, threshold props), plus
a dedicated approved blocking map when required by the blocking contract. A
blocking map is a separate control artifact, never a board panel or overview.

State:

- Identity bindings for every character sheet, location plate and prop, with
  exact head counts and "each character keeps their own face, hair and
  wardrobe".
- For character sheets on plain studio backgrounds: "every shot takes place in
  <location>; the sheet's studio background is not part of the scene", because
  a gray sheet background has bled into close-ups.
- Hands by anatomy and frame side ("her right hand, frame-left"); the model
  reads left and right as the character's own side.
- Speaker attribution for every line, exact dialogue in `{braces}`, and the
  dialogue language and register.
- Sound design stated positively ("only room tone and footsteps under the
  dialogue"). Seedance often adds a score or sting anyway; review what arrives.
- A closing line that keeps the frame clean: plain surfaces, no captions,
  subtitles or on-screen text.

### Dialogue timing

Speech lands 0.5–1.5 s after its cue, later after a long pre-line action, and
fills to the clip end. Budget for it:

- Each spoken line sits inside one shot at least `words / 2.2 + 1` s long.
- Keep the spoken total near 2.2 words per second of available time, and end
  the last line at least 0.4 s before the clip's end.
- Avoid three state changes (a line, a move, a reveal) inside the last 3 s.
- Choose hook words that speech-to-text transcribes cleanly; a garbled first
  word costs the hook.
- Trimming a clip's head does not lengthen the tail after the last word. Fix a
  short tail with a retake that shortens pre-line action, a freeze-hold, or a
  recorded waiver.

## Draft, review, promote

Use this native Seedance 2.5 Draft-first sequence in both review modes.
Review depth does not waive draft selection, assembly or promotion source safety.

1. Submit each clip as a 480p native Draft (`draft: true`) with its frozen,
   reviewed request. Draft the three clips of an episode in parallel.
2. QA the Draft with the gates below and record a selection.
3. Record the draft task ID with `draft_ledger.py`, then promote the selected
   Draft with its `draft_task_id` within 7 days to the delivery resolution
   (1080p by default; the market card may override it). Follow the
   [draft and promotion contract](../../../contracts/draft-promotion.md). The promotion
   reuses every input; a prompt fix needs a new Draft.
4. Run every gate again on the final. The final soundtrack is not identical to
   the Draft's, so the dialogue gate is repeated.

## QA gates per take

| Gate | Evidence |
| --- | --- |
| Technical | ffprobe: 480p draft or market-card delivery target (1080×1920 by default), video-stream duration, audio stream |
| Picture | Frames about every 1 s plus top-left corner crops, viewed directly: identity, wardrobe, geography, anatomy, baked-in text or digits, black side bars |
| Dialogue | Word-timed speech-to-text diff against locked lines: every word, correct speaker, order, and the tail after the last word; listen to disputed words because ASR can be wrong |
| Temporal | Actual playback covering the full take when native video tools are available; otherwise supported video analysis such as `seed_understand` on an uploaded take. Check motion plausibility, unnatural head or body turns, duplicated props and visible lip sync; frame samples alone are insufficient |
| Listening | Listen through the full soundtrack when native audio tools are available. `seed_audio_understand` on an audio extract under 25 MB can flag leaked score or stings but can mislabel music; flagged or contested audio needs direct listening, and accent verdicts need a native listener |

Honor explicitly requested provider analysis. Record what each inspection covered;
unavailable temporal, dialogue or listening checks remain unresolved and cannot
be promoted to a passing take from frame samples or a summary.

Hard-gate failures: identity swap, wrong speaker, missing or wrong word in a
locked line, baked-in text, broken anatomy, impossible motion, wrong location,
and a missing planned move or light on the shot flagged as the turn. Soft
defects (small continuity slips, softness, a missing planned cut or move on
another shot) are recorded, not retaken.

## Retakes and repairs

- One corrective retake per clip, only for a hard-gate failure, with one
  targeted prompt change, as a new Draft.
- Prefer a deterministic post repair when it is invisible: crop or delogo for a
  leaked corner mark, a centre punch-in for black side bars, or removing a
  defective shot from inside a multi-shot clip and dissolving across the gap
  when no dialogue is lost.
- **Dialogue fixes are word-scoped.** Patch only the wrong word windows; never
  re-dub a whole clip. Transcribe with word times, splice pitch- and
  loudness-matched replacements with short fades, and prove that samples
  outside each window are unchanged. Measure the actual speaker's local pitch
  and timing, then listen for timbre, prosody and continuity. About 10% pitch
  or tempo adjustment is an advisory review flag, not a universal pass/fail
  gate; smaller changes can also sound wrong. Unavailable listening remains
  unresolved, and retaining a known defect requires a recorded decision.
- When a model re-voices words, send the original clip with its audio, name
  the words to fix, take the full audio back, match the original loudness and
  mux it over the untouched picture. Never send dialogue alone: the score,
  room tone and effects must survive.
- Record every repair beside the clip with its source hash and command.

## Budget

Seedance cost scales with generated seconds, model and resolution. Never carry a
price over from an earlier project or from this file; read current pricing from
the available pricing tool or Ark CLI pricing surface
(`arkcli pricing models --model <model-id>` after `arkcli auth login`; it covers
foundation-model video and image pricing but not voice or audio models) (see
[routing](../../../contracts/routing.md)) for the exact model and resolution
before committing, and record where the price was read.

```text
estimated_cost = clips x seconds_per_clip x price_per_second(model, resolution)
                 x (1 + retake_allowance) x draft_to_final_multiplier
```

- `retake_allowance` is the planned share of clips regenerated, for example 0.15
  for roughly one retake in seven clips. Agree it with the user.
- `draft_to_final_multiplier` is 1 plus the draft cost over the final cost,
  when a shot is generated first as a 480p draft and then as a final:
  `1 + price_per_second(model, draft resolution) / price_per_second(model, final resolution)`.
  A promoted Draft is billed again at the
  final resolution (see the draft and promotion contract).
- Illustrative only, with made-up numbers: 3 clips of 15 s at a price of 0.10 per
  second, a 0.15 retake allowance and a draft ratio of 0.25 give
  3 x 15 x 0.10 x 1.15 x 1.25, about 6.5 in the pricing currency.

Declare a per-episode cap in generated seconds (for example 90 s) and stop and
report before exceeding it. Report the estimate and the confirmed cost
separately: the estimate comes from this formula before submission, and the
confirmed cost comes from billing or usage records after the tasks finish. Never
present one as the other. Seedream stills are minor by comparison.

## Assembly

- Default order, only when adopted by the brief: cold open (the first line of scene 1), title card, the rest of the
  scenes with 6-frame dissolves, a 12-frame dissolve into the to-be-continued
  card.
- No grade unless the brief records a look: keep the original Seedance colours. Decode HEVC finals as
  limited-range BT.709 and tag the output BT.709.
- Render each clip to an exact-length lossless intermediate in whole frames
  with its audio padded or trimmed to match, join, and encode once.
- Normalize every delivered episode to one loudness target (for example
  -16 LUFS integrated, -1.5 dBFS peak); measure each episode's loudness first.
- Some FFmpeg builds lack `drawtext`. Render cards as deterministic PNGs and
  subtitles as a sidecar. Add no AI or fictional label unless required.
- Studio projects record shot-take selections with
  `studio_project.py record-selection` and picture, audio and final-master
  locks with `studio_project.py record-lock`. For a revision after delivery,
  such as removing a shot the user dislikes, render a new master version with
  `studio_project.py render` (it never overwrites an earlier render).
  Pre-Studio canvas projects record reviews and locks with the showcase-html
  `stage_lock.py` tool (`review`, `lock`, `advance`) and reopen with
  `stage_lock.py reopen --stage assembly-review`; the earlier version stays on
  disk either way.
- Some platforms play HEVC poorly. Deliver H.264 masters, and convert raw
  Seedance clips to H.264 before embedding them in documents.
