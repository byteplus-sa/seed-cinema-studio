---
name: editorial-review
description: Review actual cuts for coverage, pacing and continuity with hash-bound notes. Use for assembly or editorial feedback. Do not use for generation, rendering or automatic timeline edits.
---

# Editorial Review

Act as an independent leaf. Review the supplied edit and write evidence;
never invoke sibling skills, place clips, render, or approve a stage. Read the
[post contract](../../contracts/production-post.md).

## Inputs

Require an actual watchable cut, its hash, available Studio edit snapshot,
selected take paths/hashes, source durations and relevant story/continuity
intent. A shot plan alone supports a coverage proposal, not a cut review.
Record the unit, primary cut `main` and exact artifact reviewed.

## Procedure

1. Inventory the actual ordered placements and source trims. Preserve Studio
   as the editable authority. Draft `editorial/<unit>/main.json` only as a
   candidate snapshot or reconcile an existing record explicitly; never
   silently replace an accepted snapshot. Preserve previous versions.
2. Validate the snapshot with the read-only command below. Version 1 represents
   straight cuts, source trims and timeline gaps. For overlaps, dissolves,
   speed changes or unsupported layers, record the limitation and retain the
   actual Studio edit; do not flatten it to make validation pass.
3. Watch the entire relevant cut at playback speed. Log player/method, artifact
   hash and covered ranges. If only stills or a partial preview are available,
   mark temporal criteria `unverified`.
4. Write timecoded notes for narrative clarity, coverage, eyelines, screen
   direction, state continuity, entrances/exits, pacing, transitions and
   opening/ending intent. Evaluate a quiet hold by its purpose; do not
   prescribe extra cuts merely because the camera is static.
   For character performances, compare the cut with the supplied performance
   beat IDs and critical criteria under
   [Performance direction](../../contracts/performance-direction.md).
   Check that trims retain registration, listening, response and state across
   cuts; fights retain readable exchanges and prop/participant continuity.
   Missing plan evidence stays unresolved, not invented. Do not report vocal
   delivery as verified unless the actual sound was heard.
5. Separate observed defects, artistic suggestions and unavailable evidence.
   Each proposed trim/reorder names clip ID, old/new range, rationale and
   downstream effects on sound and subtitles. Never apply it in this leaf.
6. Return a versioned review with outstanding blockers and required rechecks.
   A passing technical validator does not certify the cut or close Studio.

```bash
uv run python .agents/scripts/production_post.py editorial projects/<slug> \
  --record editorial/<unit>/main.json --unit <unit>
```

## Outputs

Return the explicit edit record and `editorial/<unit>/review-vNN.md`, with
hash-bound observations. A candidate's `source_edit` binds the current Studio
entrypoint or a supplied exported edit snapshot; it is not a whole-Studio-tree
fingerprint. The calling integration must compare current selections, full
provenance and render state.

This leaf and its structural validator do not apply edits. The calling
integration can use `editorial.py export`, `check` and explicit `reconcile` to
bind the actual supported Studio edit and update its versioned snapshot record.
That runtime service validates whole-tree provenance and current selections;
it never changes Studio HTML. Do not claim that a proposed order is already
on the timeline.
