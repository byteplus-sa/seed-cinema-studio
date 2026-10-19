---
name: series-continuity
description: Maintain story-bible, state and character-knowledge continuity records. Use for connected scenes or episodes and continuity audits. Do not use for generation or changing canon.
---

# Series Continuity

Act as an independent leaf for any narrative format, including a single
multi-scene film. Never invoke sibling skills, generate assets, select takes,
or change canon. Follow the
[development contract](../../contracts/production-development.md).

## Inputs

Read the shared bible, locked canon, source scripts, ordered scene membership,
existing continuity records and the selected unit's available reviews. Missing
canon, unseen footage or unknown scene order must remain explicit unknowns.
Preserve an existing `continuity.md`; propose bounded updates, not a replacement.

## Procedure

1. Separate invariant identity from mutable state. Identity comes from approved
   canon; wardrobe, wetness, injuries, carried props, locked doors, character
   locations and who knows which fact belong in the state ledger.
2. Record each state as a row with subject ID, property, value, unit/scene/shot,
   story-time position, source path/hash and page or observed time range.
   Distinguish `scripted`, `observed`, `confirmed` and `unknown`.
3. Record knowledge separately for each character. Include the fact ID,
   who knows it, the acquisition scene, evidence and any uncertainty. Audience
   knowledge does not imply every character knows the fact.
4. Compare each scene's incoming state with the prior relevant outgoing state.
   Follow story chronology for flashbacks; keep screen order separately.
   An offscreen change needs source support or a labeled proposed explanation.
5. Return contradictions with both evidence references, severity, affected
   units/shots, uncertainty and the smallest proposed repair. Do not choose a
   conflicting source silently or repair a locked source in place.
6. Preserve history. A later episode updates only its supported changes and
   records dependencies on earlier facts. A planned episode does not prevent
   reporting another unit's completed continuity review.

## Outputs

Write a scoped audit under `development/<unit>/continuity-vNN.md`; propose
shared bible/ledger updates separately. Use the contract's state and knowledge
tables, then list unresolved items and required inspection. Mark a visual
continuity claim `unverified` when only a script or isolated still was read.

The caller owns approvals and any regeneration. A consistent ledger is not a
creative approval, an assertion that footage was watched, or permission to
rewrite shared canon.
