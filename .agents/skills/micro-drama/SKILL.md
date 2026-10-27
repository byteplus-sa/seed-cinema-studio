---
name: micro-drama
description: >-
  Produce vertical short-form micro-drama episodes end to end for any market:
  a hook in the first seconds, a mid-episode reveal or confrontation, and a
  close-up cliffhanger, delivered as 9:16 episodes with a to-be-continued card.
  Orchestrates a market story writer when one exists (for example
  filipino-micro-drama) or the market-neutral microdrama-story-formats, then canon sheets, planning-only storyboards,
  Seedance 2.5 scene clips with native dialogue, dialogue-accuracy QA,
  assembly, loudness-matched delivery, and an optional full-episode showreel,
  all in a HyperFrames Studio project. Use for micro-dramas, vertical
  dramas, ReelShort/DramaBox-style series, TikTok drama episodes, or batches of
  several independent episodes produced in parallel. Do not use for a single
  prompt, a non-episodic ad, a music video, or long-form film; use
  film-production for general multi-scene work.
---

# Micro-Drama

Produce one or more vertical micro-drama episodes for any market, language and
genre the user chooses. Unless the user specifies another format, each episode
is a complete, reviewable 45–60 s unit built from three Seedance scene clips. This skill owns
the episode format and its production sequencing. Market story craft, such as
tropes, dialogue register and cultural signifiers, belongs to a market writer
skill. Stage, approval, Studio and submission rules come from `AGENTS.md` and
the production contracts; this skill does not relax them.

Confirmed scripts and custom episode formats override the creative defaults in
this skill and its recipes, including hook timing, casting, scene count, ending
and cards. They do not override approval, rights, review or submission gates.

## Inputs and outputs

Input: optionally a market card (user-defined, free-form; see
[market card](references/market-card.md); never assume one), a premise or formula, the episode count, and any
locked dialogue, cast, budget or approval mode. When a market writer skill
exists for the audience, obtain a locked episode brief from it first; for any
other market or language use `microdrama-story-formats`. Otherwise draft the
brief with the fields in [episode structure](references/episode-structure.md).
Any language, genre and market is in scope.

Output per episode: a project under `projects/<slug>/` with all eight production
stages closed, a final master (1080×1920 H.264/AAC unless the market card sets another
aspect), a subtitle sidecar per language in the card (named `<master-stem>.<language-code>.srt`), locks, and an honest defect list. For a batch, also a portfolio page
and an optional full-episode showreel.

For manifest-backed productions, episodes are the selected units of the existing
project, not new projects or legacy scene folders. Resolve `production.json`
first and use `units/<unit>/studio/` with `--unit ID` on unit operations.
Multiple units require explicit selection before editing; invalid manifests
fail closed. Without a manifest, retain the existing root Studio layout.
Candidate validation does not authorize activation or migration.

## Workflow

1. **Brief.** Lock logline, formula, recurring cast, locations, threshold props,
   and exact dialogue per
   scene within the word budget in [episode structure](references/episode-structure.md).
   Default to at most three recurring characters and one or two locations unless
   the confirmed episode plan specifies otherwise.
   Record `approval_mode`, format, run budget, the native-dialogue audio route and
   look intent in `project.md`,
   run `brief-intake` with a fast proposal, then run `studio_project.py init <project>` (see the
   [production policy](../../contracts/production-policy.md)) (pre-Studio canvas projects with
   `showcase.json` keep the `showcase-html` canvas).
2. **Breakdown.** Follow the confirmed episode or market-card scene plan.
   For new or revised character performances, run `acting-direction` and
   record `## Performance plan` before shot design under the
   [performance contract](../../contracts/performance-direction.md).
   Use `scene-craft` for the selected scene framework, without forcing its
   five-element engine. Coordinate `seedance-fight-choreography` for fights.
   Default to three scenes: Hook (about 15 s), Turn (about 20 s), Cliffhanger
   (about 15 s). Split scenes into clips as needed for verified model limits and
   dialogue timing. Each scene gets a shot plan (size, angle, move and light per
   shot) from `seedance-shot-design` at standard energy by default; kinetic is for
   shots without spoken lines. Walk every beat against the element-identification
   contract.
3. **Canon.** Character sheets, location plates and threshold props as
   three-sample Seedream sets. Preserve the approved casting and medium;
   make identities visually distinct within those choices. Inspect every image
   and select with hash-bound decisions.
4. **Storyboard.** Optional planning and review boards bound to selected canon.
   For scene boards use `scene-board-sheet` to derive the L1/L2/L3 panel record
   (L2 by default), and `seedream-storyboard` to author the panels. Repair failed
   panels individually. Never bind a board, grid, panel or animatic as a Seedance
   reference; translate staging into prompt text. Skip this stage when the shot
   plan already carries the staging. A separate approved blocking map remains
   available under the blocking-map contract.
5. **Audio preparation.** Mark it skipped unless the user requests a separate
   lip-sync track. Native Seedance audio carries the dialogue.
6. **Shots.** Encode the performance plan with `seedance-acting-console`.
   Require `acting.plan_bound` and applicable `fight.readable_exchange` checks.
   Inspect actual registration, listening, response and delivery before
   selecting or promoting takes; a correct transcript alone is insufficient.
   Write each clip prompt from its shot plan with `seedance-prompt-25` and the market's
   dialogue partner skill (`seedance-prompt-25-dialogue` for any language; a
   market pack such as `seedance-prompt-25-filipino` adds language depth). Apply
   the prompt, dialogue-timing and QA rules in the
   [production recipe](references/production-recipe.md). Run `prompt-review`
   inline by default; use a sub-agent only when the user explicitly requests
   sub-agent prompt review for the project or specific generation. Register the
   operation for each clip, submit independent planned clips in parallel within
   the run budget as native 480p drafts
   (`draft: true`), record each draft task ID with `draft_ledger.py`, and QA each
   take. Promote approved drafts to the final resolution with `draft_task_id`
   within 7 days, as the [draft and promotion contract](../../contracts/draft-promotion.md)
   describes, and inspect each final before it replaces the draft in Studio.
7. **Assembly.** In Studio, follow the confirmed episode order and transition
   plan. The default is a cold open, title card, three scene clips with short
   dissolves, and a to-be-continued card; a confirmed format overrides these
   cards, scene count and transitions. Keep original
   colours unless the brief records a look. Fix wrong words with word-scoped audio
   patches. Add a subtitle sidecar per requested language and
   normalize loudness. Picture and audio locks come from real playback and
   listening evidence.
8. **Delivery.** Final lock and passing Studio stage-exit checks, with the final
   master from `studio_project.py render`; FFmpeg assembly, subtitle and
   loudness work is placed in Studio as a clip or overlay and rendered, not
   delivered directly (pre-Studio canvas: `--check --stage delivery`).

For a batch of independent episodes, follow
[batch production](references/batch-production.md): one agent per episode with
exclusive project ownership, on-disk checkpoints, and a single integrating
manager. For a connected series with shared canon, follow
the manifest's unit selection and shared canon contracts. The
[series production](references/series-production.md) single-Studio layout is
legacy-only for existing series without a manifest.

## Non-negotiables

- Generated footage stays text-free. Titles, cards and subtitles are added in
  post from deterministic sources.
- Storyboards are planning artifacts only. Bind approved element references and
  any separately approved blocking map; carry board staging in shot prompt text.
- When the default hook formula is selected, the hook lands within the first
  3 s and a title card does not consume that window. A confirmed script's
  opening and timing take precedence.
- Every spoken line is checked word by word against the locked dialogue with
  speech-to-text before a take can pass. A model's own summary of what was
  said is not sufficient.
- Retakes fix hard-gate failures only, within the declared budget, as a new native
  Draft. Dialogue repairs patch only the wrong word windows. Record
  residual defects instead of silently promoting a flawed take.
- Provider success is `review`, never approval. Never resubmit an ambiguous
  paid operation; reconcile it from the task registry.

## References

| Need | Reference |
| --- | --- |
| Beat timing, hooks, reveals, cliffhangers, cards, brief fields | [Episode structure](references/episode-structure.md) |
| Clip plan, prompt clauses, QA gates, retakes, budget, assembly | [Production recipe](references/production-recipe.md) |
| Several independent episodes in parallel, checkpoints, portfolio, showreel | [Batch production](references/batch-production.md) |
| Legacy connected series without a manifest: shared canon, continuity ledger, season order | [Series production](references/series-production.md) |
| Series music identity, ambience beds, native audio that ignores a negative | [Music and ambience](references/music-and-ambience.md) |
| Optional target market, language, platform and episode format | [Market card](references/market-card.md) |
| Confirming a platform's current delivery specs before export or posting | [Platform specs](references/platform-specs.md) |

Workspace contracts: [production policy](../../contracts/production-policy.md),
[element identification](../../contracts/element-identification.md),
[audio-video alignment](../../contracts/audio-video-alignment.md).
