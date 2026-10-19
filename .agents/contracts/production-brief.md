# Production Brief and Profiles

This defines brief/profile resolution and the scoped Studio adapter described
in `PLAN_SEED_CINEMA_STUDIO.md`, sections 3.3-3.4 and 4. Validated active
`production.json` manifests support unit production. Brief resolution and
candidate validation never migrate or activate a project automatically.
The [production policy](production-policy.md) still owns authorization, review,
rights, spending and durable submission.

## API

Import `.agents/scripts/production_profiles.py`:

```python
def load_profile(format_id: str | None = None) -> dict[str, Any]: ...

def resolve_brief(
    shared: dict[str, Any],
    unit: dict[str, Any] | None = None,
    format_id: str | None = None,
    workflow: str | None = None,
) -> dict[str, Any]: ...
```

Both functions return independent dictionaries. Invalid input raises `ValueError`
with the affected field or conflict. The resolver is pure: it does not read
projects, modify inputs, write briefs, authorize operations or call providers.
The bundled catalog is loaded once at module import. No runtime dependencies are
added. Callers parse YAML using the existing `validate_request.parse_frontmatter`
convention and pass metadata dictionaries, not Markdown text or file paths.

`load_profile` returns `id`, `revision`, `workflow`, `defaults`, and
`planning_outputs` from
[production-profiles.json](../catalog/production-profiles.json).
Revision 1 profiles are `cinematic-short`, `film`, `episodic-show`,
`micro-drama`, and `custom`. `None` selects the general production route without
an assumed format. Unknown profile IDs fail; genre and medium are never profile
lookup keys.

`resolve_brief` returns effective frontmatter-like metadata. `production` and
`delivery` are always mappings. It also supplies:

| Key | Meaning |
| --- | --- |
| `format` | Selected profile ID, or `None` for unspecified general production |
| `workflow` | `micro-drama` only for that profile; otherwise `film-production` |
| `profile` | Complete profile record, including revision and disclosed defaults |
| `production` | Normalized effective creative settings |
| `delivery` | Editorial delivery settings, not provider request parameters |

Other metadata is retained, including optional `market`, legacy `episode`,
creative intent and evidence. No missing market or episode block is invented.
Legacy blocks retained in this output are source metadata, not effective
settings: consumers must read `production` and `delivery` after resolution.
For example, a unit duration can differ from an inherited legacy
`episode.duration_s`. Never serialize this result back over a source brief.

## Format Authority

1. When a caller has a manifest, pass its validated `format` as `format_id`.
   Every explicit shared or unit format mirror must agree with it.
2. Without a manifest, explicit `production.format` or legacy top-level `format`
   selects a profile. Multiple explicit declarations must agree.
3. Only when no format is explicit does `workflow="micro-drama"` select that
   profile. `workflow="film-production"` or `None` retains the general route.
   An explicit format wins over a workflow hint. Other workflow names fail.

The effective format is top-level `format`; the resolver removes
`production.format` from the effective production mapping to avoid two
authorities. It never changes the original dictionary. Format mirrors are
compatibility inputs, not fields to add to new briefs.
Format locks (`locked.format` and nested or dotted
`locked.production.format`) are unsupported and fail explicitly, even when they
match the selected format. Select the format through the manifest or a supported
explicit mirror instead; a lock is never silently discarded during selection.

## Brief Fields and Precedence

`project.md` owns shared settings; a unit brief may provide creative overrides:

```yaml
production:
  genre: historical drama
  medium: ink animation
  target_duration_s: 180
market:
  dialogue_languages: []
  subtitle_languages: [en]
delivery:
  aspect: "239:100"
  resolution: "1080p"
  fps: 24
  width: 1912
  height: 800
  cards: []
```

These are examples, not defaults. Genre, medium, market, language and format
remain independent. Empty dialogue language lists allow wordless work. Unknown
descriptive fields are retained, not interpreted as provider capabilities.
Optional or partial `market` follows the existing
[market card](../skills/micro-drama/references/market-card.md) shape. Explicit
null `market` and `episode` remain valid for compatibility; other known groups
must be mappings.

Normalize each brief independently, then merge profile defaults, shared
settings, and explicit unit settings in that order. Nested mappings merge;
lists and scalars replace. Empty lists explicitly disable defaults. Explicit
old/new conflicts within either source fail even if a later override would
hide them.

| Legacy episode field | Effective field |
| --- | --- |
| `episode.duration_s` | `production.target_duration_s` |
| `episode.count` | `production.unit_count` |
| `episode.aspect` | `delivery.aspect` |
| `episode.scenes` | `production.scenes` |
| `episode.max_recurring_cast` | `production.max_recurring_cast` |

Equal legacy and modern values are accepted. Conflicting values produce an
error naming both paths. An episode block alone does not imply micro-drama.

Only explicit micro-drama selection supplies the 45-60 second range, three
timed scenes, hook/turn/cliffhanger beats, three recurring characters, vertical
aspect and title/to-be-continued cards. Explicit duration removes the default
duration range only when no explicit or locked range exists. An explicit or
locked target must fall within any explicit or locked range, including its
endpoints; conflicts fail and compatible ranges remain effective.
An explicit or locked target duration or duration range removes inherited timed
scenes, but never scenes supplied explicitly or by a lock, including legacy
episode scenes and empty scene lists. This is default cleanup, not scene-duration
validation or automatic retiming.
Explicit scenes replace the default scene list and remove default beats unless
beats are explicitly specified. Other profiles impose no duration, aspect,
beat, scene count or cards. Planning outputs are guidance, not proof of stage
completion or format readiness.

Positive finite numbers are required for duration and frame rate; counts and
explicit dimensions are positive integers. Dimensions must be even. Aspect is
a positive integer ratio, including `239:100`. The resolver does not verify
model limits, render capacity, aspect/dimension agreement, dialogue quality or
actual output streams.

## Locks and Authority

Shared `locked` entries use the existing flat axis convention
(`audio_mode: silent`) or nested/dotted effective field paths
(`delivery.aspect: "16:9"` or `delivery: {aspect: "16:9"}`).
Legacy episode lock paths normalize through the same mapping above.
Locked values become effective even when not repeated elsewhere. A conflicting
explicit shared or unit value fails rather than silently changing a lock.
Flat axis locks also constrain `directorial_axes.<axis>.value`.
The `locks` alias is unsupported in both shared and unit metadata and fails
explicitly, including empty or null values; use shared `locked` instead.
Locks cannot introduce or change authority fields.

Shared `directorial_axes` records with `source: user_confirmed` or
`agent_confirmed` are binding, including their evidence. Units may omit or
repeat them, not replace or downgrade them. Proposed/defaulted axes remain
editable. A changed lock requires a separately authorized update to shared
source metadata before resolution; this function never approves that change.

Units cannot replace, erase or introduce production-wide `approval_mode`,
`approval`, `authorization`, `rights`, `budget`, or `locked`. Identical copies are accepted;
otherwise the resolver fails conservatively. Budget policy comparison excludes
known bookkeeping fields (`estimated`, `confirmed`, `unknown`, `spent`,
`estimated_spend`, `confirmed_spend`, `unknown_spend`, `reserved`, and
`reservations`), so stale repeated totals do not block unrelated unit work.
The effective budget always retains the complete authoritative shared copy;
unit totals never replace it. Caps, currency and unknown policy fields remain
protected. The resolver does not invent approval
mode, rights, consent or spending authorization when absent. Tighter approval
or rights restrictions also require a shared-record update;
there is no speculative policy comparison engine.

An optional `unit_budget` supports a tighter allocation:

```yaml
budget:
  cap: 100
  currency: USD
  confirmed: 30
  unknown: 20
unit_budget:
  cap: 40
  currency: USD
```

`unit_budget` accepts only a finite nonnegative `cap` and optional matching
`currency`. It requires a numeric shared `budget.cap`, cannot exceed it, and
cannot increase an inherited unit allocation. The shared budget, including
estimated/confirmed/unknown spending and reservations, remains unchanged.
Shared, explicit unit and final locked/merged allocations are all validated.
No allocation resets spending or grants permission to spend. Actual aggregation,
reservation reconciliation and concurrent enforcement remain the operation
registry's responsibility; this resolver is not an accounting ledger.

Profile defaults contain creative settings only. No profile can waive rights,
review, locks, cost boundaries or durable submission.

## Active Context And Studio Adapter

`production_context.resolve_context(project, unit_id)` validates active
`production.json`, resolves the selected unit's effective settings and returns
its ordered scenes, brief, Studio root and typed identity. Without a manifest,
the existing root Studio layout remains. Unknown units, conflicting format
mirrors, duplicate or unowned scenes, unsafe paths and mixed root/unit ownership
fail closed. Candidate `--manifest production.plan.json` validation is separate
and read-only; no activation or source rewriting follows.

`studio_project.py init PROJECT --unit ID` and `sync PROJECT --unit ID` generate
`units/<unit>/studio/BRIEF.md`. Its frontmatter carries:

- `workflow` from the resolved profile and `flow: companion`;
- `unit_id`, typed `context` and effective `delivery`;
- `source_sha256` for the raw shared project and unit brief files;
- `studio_adapter.version: 1`, body hash and metadata hash.

The body carries the shared and unit brief prose. The adapter is generated
output, not a second editable brief or a new intake. Change authoritative source
briefs under existing lock/approval rules, then regenerate. A user-authored,
symlinked or manually modified adapter blocks overwrite and needs explicit
reconciliation. Legacy root Studio does not generate this adapter.

Unit canvas initialization uses effective delivery aspect/resolution/fps and
explicit even width/height when present; conflicting CLI choices fail. Existing
root composition dimensions remain authoritative after initialization, so a
brief change is not automatic retiming or reframing.

Operational request v3 and decision v2 bind normalized shared project identity
and typed scope, while adapter provenance records raw source hashes.
Historical request v1/v2 hashing is unchanged. See
[production versions](production-versions.md) for the exact distinction and
dependency invalidation. Normalized identity never overrides an explicit raw
upstream file dependency in a decision.
