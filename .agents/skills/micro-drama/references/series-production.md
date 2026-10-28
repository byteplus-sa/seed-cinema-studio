# Series Production (Legacy Only)

Read [the entrypoint](../SKILL.md). This single-Studio layout is retained only
for existing connected series without an active `production.json`, whose
episodes share cast, locations and story. It is not the default layout for new
manifest-backed work or a migration recipe.

When `production.json` exists, its ordered unit/scene membership and selected
unit are authoritative: use `units/<unit>/studio/` and `--unit ID` for unit
operations. Multiple units require explicit selection before editing; invalid
manifests fail closed rather than falling back to this legacy layout.
Candidate validation never authorizes activation or migration. Shared canon
remains production-scoped under the
[production policy](../../../contracts/production-policy.md).

## Legacy layout

| Situation | Layout |
| --- | --- |
| Connected series: shared cast, locations, running plot | One project `projects/<series>/` with one scene folder per episode (`scene-00` for a pilot) and one Studio project, task registry and canon |
| Independent episodes or standalone dramas | One project per episode, produced in parallel |
| A second season or spin-off with the same canon | A new project that copies the locked canon files and keeps their hashes in the new `project.md` |

Per-episode files are exported from the single Studio project at the end; each
episode is a contiguous run of shots.

## Series bible and ladder

Write the bible first with the story skill's series-bible template (for any
market, `microdrama-story-formats`). The ladder records each episode's approved
purpose, attention carrier, ending and continuity consequences. Hook, turn and
cliffhanger fields apply only when that optional template is selected; preserve
resolved or open source endings. Treat the ladder as planning data: propose
changes under the existing approval mode and record accepted changes below.

## Continuity ledger

Keep `projects/<series>/continuity.md` next to `project.md`. Append a row at every
stage exit, so a replacement agent can resume.

| Episode | Character | Location at end | Wardrobe and state | Objects that changed | Knows |
| --- | --- | --- | --- | --- | --- |

- State changes carry forward until a scene shows them resolved (wet, injured,
  locked in, missing object).
- Before adding a bridge clip, check the ledger for a gap it would create.
- Facts the audience knows but a character does not belong in the `Knows` column.

## Shared canon

- Lock each recurring character, location and prop once as an element; every
  episode reuses the locked file and records its hash.
- Give a second door, window or similar landmark its own prop plate so the
  location plate does not leak it into unrelated shots.
- Bind one staging map to every clip of a crowd scene and repeat identical
  atmosphere text.
- A change to a locked element invalidates dependent prompts; revalidate them
  before generating again.

## Production order

1. Bible, ladder and canon for the whole season, then lock elements.
2. Pilot episode end to end; use its defect list to adjust the playbook.
3. Remaining episodes in story order, or in parallel waves of independent
   scenes, with serialized edits to the shared Studio project and registry.
4. A continuity pass over all episodes before final export.
5. Per-episode export, subtitles per language, covers and posting order. Platform
   norms (length, cadence, AI-content labels) come from the platform the user
   names and are checked at posting time.

## Studio notes

- `sync` appends new frames at the end of the timeline; it does not apply edit
  order. Never rebuild the edit in shot-id order. Preserve manual order, trims
  and transitions, and reconcile additions or retiming explicitly in the
  selected Studio. `editorial.py export/check/reconcile` snapshots the actual
  edit without applying order; follow the existing review and lock gates.
- A cited timestamp is recomputed from Studio start times; every cut or new clip
  shifts all later times.
- Keep `handoff.md` current: stage, selected variants, operations in flight with
  registry ids, open defects and the next action.
