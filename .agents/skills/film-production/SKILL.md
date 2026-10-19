---
name: film-production
description: Orchestrate cinematic shorts, films, episodic shows, commercials, music videos and custom narratives through inspected Studio delivery. Use for multi-scene or multi-modality production, including an unspecified format. Do not use for isolated prompts, assets or edits.
---

# Film Production

Manage one coherent production run while keeping specialist skills modular. Read
the project's `project.md` and existing manifests first, inspect the existing
project before creating anything, and advance only as far as the available
evidence and mode-authorized decisions permit.

The workspace `AGENTS.md` and the
[production policy](../../contracts/production-policy.md) own approval modes,
Studio commands, stage gates, prompt review, registration and submission
recovery. This skill owns the sequencing: which stage comes next, which
specialist runs it, and which production defaults make the result better.

## Format and brief authority

Use the [production brief](../../contracts/production-brief.md) and
[production profiles](../../catalog/production-profiles.json) contracts.
Format, genre, medium, audience,
language and delivery are independent. Follow the supplied script or treatment;
do not silently rewrite it into a short-form formula.

Only an explicit micro-drama format or an existing selected `micro-drama`
workflow delegates episode structure to that orchestrator and its market writer.
An explicit format wins over a workflow hint; changing a conflicting lock still
requires a recorded, authorized change.
Without that selection, an unspecified format stays on this general route.
A landscape cinematic short
can have quiet held shots, wordless scenes and a resolved ending without
Hook/Turn/Cliffhanger, a runtime default or a to-be-continued card. Use
`tig-scene-engine` for scene craft as needed, not `microdrama-story-formats` as
the generic development fallback.

`project.md` remains the canonical shared brief. Preserve existing locks, optional
market context and legacy episode fields; a validated `production.json` supplies
format, ordered unit/scene membership and unit brief paths. Resolve scope before
work: no manifest keeps `projects/<project>/studio/`, while an active manifest
uses `projects/<project>/units/<unit>/studio/`. Use `--unit ID` for unit commands;
multiple units require selection, except aggregate status and shared canon work.
Invalid manifests fail closed. Candidate validation never authorizes activation
or migration of existing productions.

Do not start a second HyperFrames intake. Unit `init`/`sync` generate `BRIEF.md`
with effective delivery, context and source hashes, not another editable
authority; reconcile user-authored or modified adapters explicitly. The scoped
APIs implement `PLAN_SEED_CINEMA_STUDIO.md`, but technical tests are not a fully
verified release, creative-pilot approval or feature-length readiness.
Record capacity gaps and require measured trials; alternate cuts remain deferred.

## Core operating model

- Act as the single manager communicating with the user.
- Treat project files and manifests as production memory; do not rely on chat
  history alone.
- Keep the selected legacy or unit HyperFrames Studio project
  in step with the manifests through `studio_project.py` for every stage
  review and handoff. A project with a `showcase.json` is a pre-Studio canvas
  project and keeps its canvas checkpoint instead.
- Delegate modality work to the narrowest applicable specialist skill. Run
  prompt review inline unless the user explicitly asks for a sub-agent review.
- Prefer a deterministic workflow when the next action is known. Use agentic
  judgment for creative choices, contradiction resolution, and review.
- Provider success is `review`, never approval. A poll timeout resumes the
  recorded task; it never triggers a second submission.
- Never silently replace user writing, approved canon, selected variants, or
  unrelated project state.

## Start or resume a run

1. Resolve the project directory. Search before creating a project, scene,
   element, shot, or same-purpose artifact.
2. Read `project.md`, the active manifest and selected unit brief when present,
   `handoff.md`, `task_ids.json`, the resolved Studio's `stages.json`
   (`showcase.json` for a pre-Studio canvas project),
   relevant element, scene and shot manifests, prompt snapshots, and the latest
   review decisions. Manifests and the registry win over `handoff.md`. A new
   Studio project starts with `approval_mode: approve_for_me` in `project.md`,
   `studio_project.py init <project> [--unit ID]`, then
   `studio_project.py stage <project> [--unit ID] start brief-development`.
3. **Never hand-write Studio state** (`stages.json`, `provenance.json`,
   storyboard frames, compositions, render records) or a `showcase.json`. A
   scaffold delegated to a sub-agent names the exact command and prohibits
   hand-authoring.
4. Determine the current stage from recorded artifacts and lifecycle states,
   not from filenames.
5. Identify contradictions, missing inputs, stale dependencies, pending provider
   tasks, and decision gates. Recheck the effective approval mode before each
   decision.
6. Carry the selected context into every unit command, request and decision.
   New scoped requests use v3; scoped decisions use v2 with the actual unit-brief
   upstream hash. Shared canon uses explicit production scope, not the unit.
   Follow [production versions](../../contracts/production-versions.md).
7. State the current stage, the next safe objective, required specialist
   skills, and any user decision needed before spending credits.

Read [stage contracts](references/stage-contracts.md) for entry evidence,
required outputs and exit conditions, and
[handoff contracts](references/handoff-contracts.md) before moving an artifact
between modalities.

## Route specialist work

<!-- markdownlint-disable MD013 -->

| Production need | Primary skill |
| --- | --- |
| Brief intake, directorial defaults, audio route, look intent | `brief-intake` |
| Narrative reference-video inspiration | `template-factory` for native-first reverse-engineering; native/local inspection and timing evidence for lighter analysis, with permitted MCP fallbacks when needed. Preserve the selected unit, supplied script, quiet holds and confirmed format |
| Explicit micro-drama format | `micro-drama` (with a market writer such as `filipino-micro-drama`) |
| General premise, treatment, outline or script-led scene list | `story-development`; preserve supplied writing and compose `tig-scene-engine` separately for scene craft |
| Shared bible, mutable state and character knowledge | `series-continuity`; scoped audits without changing canon |
| Review of an actual edit for coverage, pacing and continuity | `editorial-review`; explicit `editorial.py` snapshots, no automatic edit application |
| Edit-bound cue sheets, mix decisions and listening evidence | `sound-post`; caller executes authorized mixing/rendering |
| Locked-text SRT/WebVTT with measured unit-local timing | `subtitle-sidecars`; retain `microdrama-subtitles` and its shared engine |
| Source-preserving language versions of delivered work | `production-localize`; retain `microdrama-localize` for explicit micro-drama |
| Character identity asset | `seedream-character-sheet` |
| Character sheet cleanup | `seedream-character-sheet-cleanup` |
| Authorized face or voice asset (`asset://` Virtual Portrait) | `seedance-virtual-portrait` |
| Location identity asset | `seedream-location-asset` |
| Prop or product identity asset (acquire an authorized real brand or product first) | `seedream-prop-asset` |
| Exact static typography, poster, title/end card, UI, product grid, price/CTA treatment, or transparent overlay | `html-graphic-render` |
| General image generation or edit | `seedream-prompt` or `seedream-edit` |
| Storyboard for planning and review | `seedream-storyboard` |
| Scene board record, annotated sheet, animatic and panel repair planning | `scene-board-sheet` |
| Scene geography and crowd blocking | `tig-blocking-map` |
| Score, ambience, SFX or dialogue audio | `seed-audio-prompt` |
| Per-shot coverage, camera, lens intent and light for a scene | `seedance-shot-design` |
| Seedance 2.5 video prompt | `seedance-prompt-25` |
| Spoken dialogue in any language | `seedance-prompt-25-dialogue` with `seedance-prompt-25` |
| Market-specific video dialogue (for example Filipino or Taglish) | The market's dialogue skill, such as `seedance-prompt-25-filipino`, with `seedance-prompt-25` |
| Seedance 2.0 video prompt | `seedance-prompt-20` |
| Model submission, polling, artifact access, speech-to-text | `ark-mcp` |
| Animated exact graphics or timed overlays | appropriate HyperFrames skill |
| Assembly, media transforms, captions, word-scoped audio patches | appropriate HyperFrames or FFmpeg skill; the result is placed in Studio and rendered with `studio_project.py render` |
| Studio project, stage gates, review and selection | `studio_project.py` with the `hyperframes-studio` conventions; pre-Studio canvas projects use `showcase-html` |

<!-- markdownlint-enable MD013 -->

If the needed lifecycle role does not exist, keep the work at its current stage
and record the gap. Do not disguise a generic prompt as a completed production
department workflow.

## Production defaults

Read [production defaults](references/production-defaults.md) before the first
paid video submission and again at assembly. In short:

1. **Draft first.** Every new Seedance 2.5 shot is a 480p Draft, reviewed and
   selected, then promoted to the delivery target. Edit inputs only before the
   Draft; re-check audio on the final. Record each provider draft task ID with
   `draft_ledger.py` and follow the [draft and promotion contract](../../contracts/draft-promotion.md).
2. **Audio route from the brief.** Native dialogue keeps native audio.
   Ambience-only, score-driven and wordless pieces generate picture with
   `generate_audio: false` and build the bed in post, because a "no music" line
   does not reliably hold.
3. **Structure from the confirmed brief.** Derive scenes, duration, ending,
   aspect and coverage from the script or treatment and disclosed profile.
   Preserve held shots and wordless passages. Advertising cadence and
   micro-drama beats are not general narrative requirements.
4. **Storyboards plan; they are never bound** as Seedance references. Bind
   element references and write staging in the prompt.
5. **People in video inputs** (extension, video-to-video) need `asset://`
   Virtual Portrait identities; otherwise use short single passes and a
   blocking map.
6. **Text-free footage.** Overlays, end cards and any required labels are added
   in post; add a disclosure label only when the user, platform or brief requires one.
7. **Ungraded assembly** in original colours, exact-length intermediates, one
   final encode.
8. **Narrow fixes.** Word-scoped audio patches and re-voicing that keeps the
   source soundtrack. Compare speech-to-text against locked dialogue and listen
   to disputed words; a wordless piece does not invent a dialogue gate.

## Run one stage at a time

For the active stage:

1. Record the stage objective and observable acceptance criteria.
2. Confirm every input path, selected variant, lifecycle state, and SHA-256.
3. Invoke only the specialists needed for that stage.
4. Persist exact prompts beside generated media and update the owning manifest.
   Deterministic static graphics persist their editable HTML entrypoint, local
   dependencies, input/font hashes, render record and PNG instead.
5. Inspect every actual output: images visibly, video temporally, audio by
   listening plus speech-to-text where words matter. Reject hard-gate failures
   and rank passing candidates against the brief's recorded criteria.
6. Record the decision under the project's approval mode: an agent decision in
   `approve_for_me`, or a recommendation and the user's chat answer in
   `ask_for_approval`. Choose takes with `studio_project.py candidates`, a swap
   in Studio (or `place`), then `record-selection`.
7. Run `studio_project.py sync` after every material change and open the
   selected Studio for visual review of shot takes. It preserves manual edits;
   do not treat sync as edit-order application.
8. Exit with `studio_project.py stage <project> [--unit ID] complete <stage-id>`.
   Skip out-of-scope `storyboard-visual-plan` or `audio-preparation` with
   `stage <project> skip <stage-id> --reason TEXT`; reopen a completed stage
   when an upstream input changes. A changed unit context requires reopening
   `brief-development`, preserving the prior ledger in history and invalidating
   later locks. Update `handoff.md` at every exit.
9. Advance only when the stage exit contract is satisfied.

At the brief/development stage, run `brief-intake` before writing the brief's
required output. It proposes directing defaults derived from the idea, and the
brief must also record the audio route, the look intent (ungraded original
colours unless a look is requested), the on-screen copy that will be added in
post, and the script-led structure and delivery choices. Persist the
mode-authorized confirmed set as a `locked` block in `project.md`.
Sequence `story-development` for source inventories and script-led breakdown,
and `series-continuity` for state/knowledge evidence. Do not require redundant
new writing when a supplied locked script already contains it.

At the scene breakdown stage, run `seedance-shot-design` for every narrative,
ad, micro-drama, music-video or showcase scene before any shot prompt is
written, and store the plan in the scene file's `## Shot plan` section. The
plan stays `draft` until the scene's locations are approved, then is
revalidated before shot generation. An exempt scene records its
`static_reason`. The plan carries the project's confirmed camera, lens,
lighting, pacing and energy axes into the shot lines or records a scene
override. At shot generation, inspect each take against its plan: a missing
planned cut, move or light change is a soft defect to record, and a missing
move or light on the turn shot is a hard-gate failure.

## Approval and spending gates

Approval modes, decision evidence and lock rules are defined once in the
production policy. The orchestration-specific rules are:

- Declare a run budget (generated seconds or currency) before the first paid
  submission, and stop and report before exceeding it. Promote only selected
  drafts.
- A tie between passing candidates uses stable operation ID and
  variation-index order. Do not promote the least-bad output merely to advance.
- Rights, real-person likeness or voice consent, new spending beyond the
  declared budget, external delivery and publishing need their own scope in
  either mode. An approval to generate never approves its result.
- Record estimated and confirmed cost separately.

## Handle revisions

Write every revision as:

- **Locked decisions:** properties that must remain unchanged;
- **Requested delta:** the single intended change where practical;
- **Acceptance criteria:** observable evidence of success;
- **Known rejections:** previously rejected outcomes that must not return;
- **Invalidation scope:** dependent artifacts that return to `review` if inputs
  change.

Prefer a bounded edit over full regeneration after composition or performance is
approved: a post repair, a word-scoped audio patch, or one corrected shot.
Preserve rejected history and never overwrite source media.

## Finish the run

At assembly, export the actual Studio edit with `editorial.py export`, check it
and explicitly reconcile the snapshot with an expected revision when accepting
it as `editorial/<unit>/main.json`. These commands never apply order or trims.
Unsupported edit constructs remain in Studio with a recorded coverage gap.
Use `editorial-review` and `sound-post` for actual playback/listening evidence,
not merely successful JSON validation.

For an indexed named delivery, use `deliverables.py validate/status`, bind an
explicit current unit render with `bind --render-record --expected-revision`,
then record its own reviewed `lock --decision --expected-revision`. The ID
selects its unit; this service has no `--unit` flag. Keep named locks separate
from the unit stage's final-master lock and context-local newest-render gate.
Only `cut_id: main` is supported; no newer proxy or language output silently
replaces a named master. Follow the complete commands in the production policy.

Report the stage reached, artifacts created or changed, Studio project path and
stage-exit evidence, review status, provider tasks still running, costs when
known, unresolved risks, and the next production decision. A production run is
complete only when its active stage exit contract is satisfied; the selected
unit is complete only after its inspected master has a mode-authorized final
lock and applicable named delivery evidence. Other units may remain planned.
External delivery or publishing remains a separate action.

Submission recovery (register before submitting, record the task ID at once,
reconcile `submission_unknown`, never resubmit through a second transport)
follows `AGENTS.md` and the production policy.
