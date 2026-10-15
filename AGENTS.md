# AGENTS.md — seed-microdrama-studio

Workspace for producing vertical micro-drama series on BytePlus Seedream, Seedance
and Seed Audio, from brief to per-episode delivery. It supports any market,
language and genre: romance, hidden-heir, revenge, family, thriller, horror,
comedy, historical and more. The workflow was proven on a first series, "Dalawang
Anak ng Don" (Filipino teleserye, 11 episodes, 9:16), which remains the reference
market pack.

## Markets and languages

- Story: use `microdrama-story-formats` for any market. A market pack (for example
  `filipino-micro-drama`) replaces it when one exists for the audience.
- Dialogue: use `seedance-prompt-25-dialogue` for any language. It checks the
  native-language list and routes unsupported languages; a market pack (for
  example `seedance-prompt-25-filipino`) adds language depth.
- New market: follow [docs/ADD_A_MARKET.md](docs/ADD_A_MARKET.md). Do not assume
  Filipino names, settings, honorifics or Taglish in a project for another market.

## Origin

The skills, contracts, scripts and tests under `.agents/` and `tests/` are copies
from `byteplus-sa/ark-director`. Treat this repo as the home of the micro-drama
workflow; sync shared fixes from upstream deliberately rather than editing copies in
passing. Seed Audio 1.5 early-access skills are intentionally not included (also left out: Blender, ad and UGC formats, VFX and effects skills, and the Lark showcase skill).

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
  `sync`). Studio is the review and assembly surface; locked assets live in
  `studio/assets/` as `LOCKED_<element>_<vNN>.<ext>`.
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
- Real-person likeness and voice inputs go through authorized Advanced Creation
  Rights assets (`seedance-virtual-portrait`), never by disguising the input.
- Provider success sets `review`, not `approved`. Selections are hash-bound decisions
  under `approve_for_me` (default for new projects) or explicit user decisions under
  `ask_for_approval`.

## Micro-drama specifics

- Market-neutral: names, settings, wardrobe and dialogue come from the project's
  market card, never from the reference series.
- One episode is Hook, Turn, Cliffhanger; length, aspect and scene split come from the market card (default 45 to 60 s, three scenes). Plan the shot list with
  duration, size, angle, move, lens intent and a named light source per shot.
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
  doors and where each character is.
- Studio rebuild: `sync` appends new frames at the end and `place` refuses a take of
  a different length, so rebuild in shot-id order when clips are added or retimed.

## Local production state

`projects/<series>/` is the durable local source of truth (one project per connected series; see the micro-drama series-production reference) and is not committed
(`/projects` is ignored). Use lowercase kebab-case ids, scene ids with two digits and
shot ids with three digits in steps of ten. Keep a short `handoff.md` in each project.

## Security

Resolve credentials from runtime configuration (`BYTEPLUS_MODELARK_API_KEY`); never
output or commit credentials, `.env` files or signed URLs. Validate external data,
use subprocess argument arrays, confine project paths including symlinks.

## Verification

```bash
uv sync --locked
uv run python .agents/scripts/validate_workspace.py --offline
uv run python -m unittest discover -s tests -v
uv run ruff check .agents/scripts tests
uv run mypy .agents/scripts
git diff --check
```

Report pass, fail or not-applicable for each. A missing runtime or unavailable tool is
not a passing test.
