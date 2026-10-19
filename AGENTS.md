# AGENTS.md - Seed Cinema Studio

Agent-driven production workspace for cinematic shorts, films, episodic shows,
custom narratives and explicit micro-drama on BytePlus Seedream, Seedance and
Seed Audio. HyperFrames Studio remains the editor and review surface. Format,
genre, medium, audience, language and delivery are independent choices.

## Production routing and readiness

- Use `film-production` for general narrative production, including an unspecified
  format. Route source-preserving development to `story-development` and compose
  `tig-scene-engine` for scene craft. Use `series-continuity` for shared state
  and character knowledge. Do not use micro-drama formulas as a generic fallback.
- Use `micro-drama` only for an explicit micro-drama format or an already selected
  micro-drama workflow. A vertical aspect alone does not select that format.
- The project-local `hyperframes` overlay routes narrative work to the existing
  orchestrator, without installing an absent upstream workflow.
- Follow [production brief](.agents/contracts/production-brief.md) and
  [production profiles](.agents/catalog/production-profiles.json).
  Disclose defaults and preserve confirmed
  choices, locks, optional market context and legacy episode fields.
- The local APIs implementing `PLAN_SEED_CINEMA_STUDIO.md` support validated
  `production.json` manifests and independent `units/<unit>/studio/` contexts.
  Without a manifest, retain root `studio/` and legacy commands. Use
  `studio_project.py COMMAND PROJECT --unit ID` for unit operations; multiple
  units require explicit selection, except aggregate `status` and shared canon
  operations. Invalid manifests fail closed. There is no automatic migration
  of active productions and no automatic repository or checkout rename.
  Validate candidates read-only with
  `production_context.py PROJECT --manifest production.plan.json [--unit ID]`.
  Candidate validation does not authorize activation.
- For forwarding commands, put scope before the project:
  `studio_project.py hf --unit ID PROJECT preview --no-open --json` and
  `studio_project.py record-render --unit ID PROJECT FILE ...`.
- Micro-drama has prior production evidence; synthetic technical render tests
  are not creative-pilot approval or a fully verified release. Feature-length
  readiness requires measured trials. Alternate cuts remain deferred; automated
  validation does not establish creative proof. The active technical pilot uses
  labeled synthetic decision fixtures for strict gate coverage, not genuine
  creative approvals.

## Markets and languages

- Micro-drama story only: use `microdrama-story-formats` for any market. A market
  pack (for example `filipino-micro-drama`) replaces it when one exists for the
  audience. These are not mandatory formats for general narrative development.
- Dialogue: use `seedance-prompt-25-dialogue` for any language. It checks the
  native-language list and routes unsupported languages; a market pack (for
  example `seedance-prompt-25-filipino`) adds language depth.
- New market: follow [docs/ADD_A_MARKET.md](docs/ADD_A_MARKET.md). Do not assume
  Filipino names, settings, honorifics or Taglish in a project for another market.

## Scope of this repo

This repo reuses the general production core and retains the micro-drama workflow.
The Python package metadata is `seed-cinema-studio-tools`, local only, with
dependency versions unchanged;
repository/checkout names, schema IDs, renderer lock namespaces and legacy
entrypoints are separate compatibility boundaries. No rename or publish is
implied by using the production APIs. Seed Audio 1.5
early-access skills are intentionally not included (also left out: Blender, ad
and UGC formats, VFX and effects skills, and the Lark showcase skill).

Edit skills only under `.agents/skills/<name>/`. `.claude/skills/<name>`,
`.claude/catalog`, `.claude/contracts` and `.claude/scripts` are relative symlinks
into `.agents/`; never replace a link with a copy.

## Scope and authority

Follow current user instructions and preserve authorization already given for the
task. Do not expand into unrelated global configuration, external publishing or
production edits. Ask for missing information that materially changes the result;
continue reversible work whose requirements are clear. Never revert, overwrite or
clean up work you did not create. Never commit or push unless asked.

## Legacy canvas

New projects use HyperFrames Studio only. The `showcase-html` skill and the `canvas.*`
rules are kept for projects that already have a `showcase.json` and because
`studio_project.py` reuses its `selection_service`. Do not start a canvas project, and
do not remove these files without first refactoring `studio_project.py`, the canvas
tests and the contracts together.

## Operational contracts

Load only the contract relevant to the current stage:

| Need | Source |
| --- | --- |
| Stages, approval, review, durable submission, Studio gates and QA | [Production policy](.agents/contracts/production-policy.md) |
| Scoped requests, decisions and legacy hash compatibility | [Production versions](.agents/contracts/production-versions.md) |
| Source-preserving story and continuity evidence | [Development](.agents/contracts/production-development.md) |
| Editorial snapshots and sound evidence | [Post evidence](.agents/contracts/production-post.md), plus the Studio integration in [Production policy](.agents/contracts/production-policy.md) |
| Explicit named delivery specifications, render bindings and locks | [Named deliveries](.agents/contracts/production-deliverables.md) |
| MCP, Ark CLI and capability routing | [Routing](.agents/contracts/routing.md) |
| Canon, props, screens and control references | [Element identification](.agents/contracts/element-identification.md) |
| File prefixes and numbering | [Asset naming](.agents/contracts/asset-naming.md) |
| Requested dialogue synchronization and assembly | [Audio-video alignment](.agents/contracts/audio-video-alignment.md) |
| Seedance 480p drafts, draft task IDs and later promotion | [Draft and promotion](.agents/contracts/draft-promotion.md) |
| Video-to-video inputs | [Video-to-video inputs](.agents/contracts/video-to-video-inputs.md) |
| Shot plan, camera, lens, lighting, acting and other axes | [Directorial axes](.agents/contracts/seedance-reference.md) |

Rule IDs live in `.agents/contracts/rules.json`; request, registry and review
schemas live in `.agents/contracts/schemas/`.

## Production invariants

- New projects are HyperFrames Studio projects (`studio_project.py init`, then
  `sync`, with `--unit` for selected manifest-backed work). Studio is the review
  and assembly surface. Locked assets live in the selected Studio's `assets/`
  as `LOCKED_<element>_<vNN>.<ext>`; unit copies do not own shared canon decisions.
- `project.md` and the manifest's unit brief own creative intent. Unit
  `BRIEF.md` is a generated, hash-bound adapter, not another editable brief.
  Reconcile user-authored or modified adapters explicitly.
- New scoped work uses request v3 and decision v2, binding typed context and
  the normalized shared project digest. Historical v1/v2 request hashes are
  unchanged. Keep decision upstream hashes tied to real production-relative files.
- Canon first: approve recurring characters, locations and story-critical props
  before dependent shot generation. Elements define identity.
- Draft first: Seedance 2.5 shots start as native 480p drafts (`draft: true`); review
  and select before any final-resolution generation. Record each draft task ID in
  `drafts.json` (`draft_ledger.py`) so the approved draft can be promoted to the
  final with `draft_task_id` within 7 days (see the draft and promotion contract).
  A final is a new paid request with its own review, and its output is inspected
  before it replaces the draft take.
- Persist every prepared operation in `task_ids.json` before submission
  (`prepare_request.py --register`); never submit the same paid generation twice or
  through two transports. A prepared but never submitted operation is closed
  terminal and re-registered under a new version.
- Run prompt review inline for every generation-bound prompt and resolve CRITICAL
  and MAJOR findings. Changed inputs invalidate review.
- Do not bake captions, taglines or overlay text into generated video; add text in
  post with FFmpeg or HyperFrames.
- Storyboards are planning and review artifacts. Never bind panels, grids, sheets or
  animatics as Seedance references; translate staging into prompt text and bind
  canonical elements. Seedream panel repairs may use the panel as an edit source.
- Real-person likeness and voice inputs go through authorized Advanced Creation
  Rights assets (`seedance-virtual-portrait`), never by disguising the input.
- Provider success sets `review`, not `approved`. Selections are hash-bound decisions
  under `approve_for_me` (default for new projects) or explicit user decisions under
  `ask_for_approval`.

## Micro-drama specifics

Only for an explicit micro-drama format or an existing micro-drama workflow:

- Market-neutral: names, settings, wardrobe and dialogue come from the project's
  optional market card or confirmed brief, never from the reference series.
- Default episode structure is Hook, Turn, Cliffhanger, 45 to 60 s, three scenes,
  9:16 and a to-be-continued card. Confirmed brief or market-card choices override
  these defaults. General narrative production inherits none of them.

## Shared scene and assembly practice

- Plan each shot with duration, size, angle, move, lens intent and a named light
  source. Preserve quiet held shots and wordless scenes when the brief calls for
  them; record their directing rationale.
- Blocking: crowd and multi-person scenes bind a position map (`tig-blocking-map`)
  as the last `reference_image`. Video extension and first-frame are not available
  for generated people, so keep blocking steady with one shared map and identical
  atmosphere text across clips.
- A location plate that shows a door will make Seedance draw that door. Give any other
  door its own prop plate and keep unwanted doors out of frame.
- Audio fixes are word-scoped. Replace only the wrong word, match pitch and loudness,
  cross-fade, and reject a replacement that needs more than about 10 percent pitch or
  tempo change. Prefer a retake with a pronunciation cue over a stretched splice.
- Track continuity of state across episodes: wardrobe, wetness, injuries, locked
  doors and where each character is, with `series-continuity`.
- Studio rebuild: `sync` appends new frames at the end and `place` refuses a take of
  a different length. Reconcile additions and retiming explicitly in Studio;
  never rebuild over manual edits automatically. `editorial.py export/check/reconcile`
  snapshots the actual edit without applying order.
- Route cut review to `editorial-review`, cue/mix/listening evidence to
  `sound-post`, sidecars to `subtitle-sidecars`, and delivered language versions
  to `production-localize`. Retain `microdrama-subtitles` and
  `microdrama-localize` as compatibility entrypoints.
- Named delivery uses `deliverables.py validate/bind/lock/status` by explicit ID.
  Bind an explicit unit render record, inspect the output and record its own
  final decision; never substitute the newest proxy or another unit's master.
  Units with named outputs need exactly one `primary: true` delivery index entry;
  completion requires that ID's current binding and named lock.
  Only `cut_id: main` is supported. Publishing remains separately authorized.

## Local production state

`projects/<production>/` is the durable local source of truth (one project per
production or connected series; retain the micro-drama series-production
reference for existing series) and is not committed
(`/projects` is ignored). Use lowercase kebab-case ids, scene ids with at least two digits and
shot ids with three digits in steps of ten. Keep a short `handoff.md` in each project.

## Security

Resolve credentials from runtime configuration (`BYTEPLUS_MODELARK_API_KEY`); never
output or commit credentials, `.env` files or signed URLs. Validate external data,
use subprocess argument arrays, confine project paths including symlinks.

## Verification

```bash
uv sync --locked
uv run python .agents/scripts/validate_workspace.py --offline
SHOWCASE_BROWSER_SMOKE=1 STUDIO_SMOKE=1 DELIVERABLES_MEDIA_SMOKE=1 \
  uv run python -m unittest discover -s tests -v
uv run ruff check .agents/scripts tests .agents/skills/scene-board-sheet/scripts \
  .agents/skills/subtitle-sidecars/scripts .agents/skills/microdrama-subtitles/scripts
uv run mypy .agents/scripts .agents/skills/scene-board-sheet/scripts
uv run mypy .agents/skills/subtitle-sidecars/scripts
uv run mypy .agents/skills/microdrama-subtitles/scripts
uv run python -m compileall -q .agents/scripts .agents/skills/scene-board-sheet/scripts \
  .agents/skills/subtitle-sidecars/scripts .agents/skills/microdrama-subtitles/scripts
git diff --check
```

Use the configured Node/Chrome and FFmpeg runtimes for gated tests. Run subtitle
type checks separately because both compatibility entrypoints share a module name.
For untracked runtime additions, use a prospective portable inventory with the
workspace validator; do not stage files merely to satisfy that check.
Report pass, fail or not-applicable for each. A missing runtime or unavailable tool is
not a passing test.
