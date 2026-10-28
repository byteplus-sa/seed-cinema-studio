# Production Request And Decision Versions

This documents the scoped integrity and lifecycle APIs implementing
`PLAN_SEED_CINEMA_STUDIO.md`, Sections 3.4-3.6. Validated active manifests support
unit production; explicitly supplied candidate manifests remain read-only.
Neither path automatically migrates an existing project or authorizes providers.

## Version Matrix

| Record or layout | Read-only validation | Operational behavior |
| --- | --- | --- |
| Historical canvas/request v1 | Original schema and hash algorithm | Existing compatibility remains; explicit approval modes require request v2 |
| Root Studio or versioned canvas/request v2 | Original schema, hash and decision evidence | Existing preparation, registration, adoption, transition and promotion rules remain |
| Decision v1 | Historical unscoped evidence | Existing root/canvas approval rules remain; not reinterpreted as a unit decision |
| Active unit/request v3 | Typed unit context and normalized shared project digest | Scoped preparation, registration, adoption, transitions and same-context draft promotion |
| Active shared canon/request v3 | Typed `kind: production`, no unit ID | Explicit production-scope preparation and canon decisions; not unit shots or stage locks |
| Decision v2 | Typed context, current project/mode, actual upstream file hashes | Scoped selection and lock writers validate current authority and scope |
| Task registry envelope v1 | Request v1, v2 and v3 records | One shared registry; retain immutable operation identity and history |
| Studio stages/provenance/render v1 | Legacy root Studio evidence | Existing root commands and readers remain |
| Studio stages/provenance/render v2 | Unit context and ordered scene membership | Selected unit's Studio tree, selections, stage ledger and render gates |
| Candidate `production.plan.json` | Explicit `--manifest` validation | No registration, unit initialization or operational authorization from a candidate |
| Active `production.json` | Schema and semantic validation | Valid unit contexts operate; invalid, mixed-root, escaped or ambiguous layouts fail closed |

The decision schema accepts v1 and v2. Structural validity alone never
authorizes a decision: scoped readers must recompute the typed context. A valid
unit Studio authorizes scoped agent/chat decisions without a dummy root
`studio/`. Shared canon requires production scope and at least one initialized
valid unit Studio. Current production-wide approval mode remains authoritative.

## Hash Contract

`compute_request_hash` keeps the v1 and v2 canonical algorithms unchanged:
sorted JSON keys, compact separators, UTF-8, `ensure_ascii=False` and
`allow_nan=False`. Existing calls without an explicit version retain their
historical behavior.

- V1 binds prompt bytes through SHA-256, model, operation, parameters and
  ordered reference hashes, roles and bindings.
- V2 additionally binds approval mode, the raw project file hash and each
  reference's approval evidence.
- V3 requires `schema_version=3`, valid typed `context`, approval mode and
  `project_sha256`. It uses the v2 body plus the complete context object, but
  operational `project_sha256` is the normalized shared production digest from
  `production_context.context_project_sha256`, not the raw `project.md` hash.
- Context with an omitted, v1 or v2 hash version is rejected, never ignored.
  A missing or malformed v3 context is rejected.
- Context canonicalization belongs to `production_context.py` and
  `production-context.schema.json`. Changing that projection requires a new
  context version. The self-contained request/registry/decision schema copies
  are parity-tested against the context schema.

New context version 2 includes shared creative/authorization inputs and prose-body
hash, selected format/profile revision and effective settings. Unit identity
also includes the selected unit ID, normalized unit-brief hash and ordered scene IDs.
Production canon identity omits unit membership. Normalization excludes the
defined operational metadata paths and all root `budget`, `unit_budget` and
`spending_cap` values, including budget-only lock entries. Unit-brief hashing
ignores empty lock containers left after removing legacy fields. Authority
checks still reject explicit attempts to erase non-budget locks. Unit hashing
uses canonical parsed metadata with those same exclusions plus decoded prose;
formatting-only YAML and line-ending changes are not creative changes.
Normalized unit metadata encodes mappings as `["mapping", sorted key/value
pairs]`, lists as `["sequence", items]`, and YAML dates/timestamps as
`["timestamp", ISO text]`; JSON scalar types retain their values. These
distinct encodings prevent timestamps from aliasing user-authored structures.
Non-budget incidental unit metadata remains bound. Exclusions are path-specific,
not a recursive removal of fields such as `story.budget`.

Unrelated unit edits do not change another unit's identity. A changed shared
creative setting or authorization can affect every dependent unit; legacy
budget-only edits do not stale new requests. A raw
file listed in a decision's `upstream_sha256` still invalidates that decision
when it changes, even if normalized scope is unchanged. Computed digests belong
in typed context, never under invented upstream file paths.

Version 1 context records remain schema-readable for historical reconciliation.
They are not automatically rehashed or migrated. A new submission from an old
context needs explicit re-preparation and current review; already-submitted jobs
remain subject to duplicate protection and historical reconciliation. Legacy
request v1/v2 and decision v1 raw-file hashes are unchanged.

## Context And Operational APIs

All context helpers are read-only:

```python
resolve_context(project, unit_id=None)
resolve_production_context(project)
resolve_candidate_context(project, manifest, unit_id=None)
validate_production(project, manifest=None)
discover_unit_shots(context)
context_project_sha256(project)
context.identity()
```

No manifest and no unit selects legacy root `studio/`. One active unit can be
implicit; multiple units require selection for unit operations. The Studio CLI
has aggregate `status` and production-wide canon commands. Scene and shot IDs
remain production-global; paths remain relative to the production root.

`prepare_request.py` accepts `--schema-version 3` and mutually exclusive `--unit`
or `--production-scope`. Active manifests default to v3 and reject v1/v2 for new
work; legacy layouts reject v3. The matching flags on `validate_request.py`
select the expected scope rather than reinterpreting a foreign record.
`prepare_operation` and `adopt_submitted_operation` accept keyword
`unit_id`/`production_scope`; `transition_operation` uses the registered identity.

Preparation, registration and transition to `submitting` revalidate current
scope, reference approvals, prompt and project digests. Unit decision v2 also
requires the actual unit brief in `upstream_sha256`. Shared `elements/` requests
and decisions require `kind: production`; selecting a unit cannot grant canon
authority or expand rights.

## Candidate Compatibility

`production_context.py PROJECT --manifest production.plan.json [--unit ID]`
validates an explicit candidate without activating it. A candidate is not an
active `production.json`, and validation refuses mixed legacy/root ownership.
`request_hash_findings` checks structure and prompt/request hashes only.
`candidate_scope_findings` recomputes candidate unit identity;
`candidate_request_findings` additionally checks the current approval mode and
retains the candidate helper's raw-project-hash binding. That historical
validation helper is not the operational v3 normalized-project contract.

Candidate checks do not validate reference approvals, review adequacy,
capability evidence, provider status, promotion eligibility or
stage/delivery completion. Candidate shared production scope is not resolved by
`candidate_scope_findings`. Structural decision schema checks are not approval.
Do not reuse a candidate request as an operational authorization.

## Recovery And Compatibility

Registered request identity is immutable. After submission, reconciliation may
record the known provider outcome even if creative context has since changed;
this preserves task history, not approval for stale media. Revalidate current
scope before selection, promotion or delivery. Scoped success enters `review`,
never `approved`. Unknown acceptance never becomes a fresh submission.

Draft ledger entries retain their scoped context. V3 promotion requires the
registered native draft and final to share the same current context, model and
prompt, successful provider outcome and current hash-bound selection. Foreign
or unscoped drafts cannot satisfy a scoped promotion. Preserve original IDs,
versions, decisions and outputs; never downgrade them to resume work.
Historical submitted board-bound jobs retain the explicit adoption exception.

Request board guards cover `scene-\d{2,}` board directories and `s\d{2,}`
panel, clip-board, sheet, overview, animatic and `kfNN_board` filenames.
Ordinary `sNNN_kfNN_vNN` keyframes and approved blocking maps are not boards.
Resolved aliases/symlinks remain subject to the same reference guard.

## Studio And Delivery Evidence

Unit stages, provenance and render records use v2 with typed context and ordered
membership; root records retain v1. Selection transactions target the selected
unit ledger. A changed context requires explicit reopening of
`brief-development`; the writer archives the prior ledger and invalidates later
locks. `init`/`sync` generate the scoped `BRIEF.md` adapter but refuse to overwrite
user-authored or modified adapters.

`editorial.py export/check/reconcile` binds snapshots to the current Studio
tree and selections without applying edits. `deliverables.py` uses an explicit
render record and immutable per-ID binding/lock history. See
[production policy](production-policy.md) for the distinction between the
unit stage's newest eligible render and named delivery selection.

Only primary cut `main` is supported. No automatic migration, alternate-cut
workflow, provider idempotency, creative-pilot approval or feature-length
readiness follows from schema or synthetic technical tests.
