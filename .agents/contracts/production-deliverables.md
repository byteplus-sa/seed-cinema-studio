# Named Production Deliveries

Implements Phase 5 of `PLAN_SEED_CINEMA_STUDIO.md`, sections 3.6 and 5.
Named delivery state is separate from the primary unit's eight-stage ledger.
The service does not generate media, change Studio edits, complete stages,
replace the unit's `final_master` lock, publish, or migrate legacy projects.

## Specification

`production.json` is the only deliverable index. Every entry identifies an
existing manifest under `deliverables/`:

```json
{
  "id": "ep001-en-master",
  "unit_id": "ep001",
  "manifest": "deliverables/ep001-en-master.json",
  "primary": true
}
```

For a unit with named outputs, mark exactly one index entry `primary: true`.
The ID of that entry explicitly selects the unit's delivery-stage output.
Missing or multiple primary entries block completion, even with a valid legacy
`final_master` lock. The marker is optional while planning, binding and locking;
those operations do not select a primary implicitly. Other units' markers do
not select this unit's output. Adding a proxy or language version without the
marker never changes the selection.

The initial manifest contains the specification, without invented state:

```json
{
  "schema_version": 1,
  "id": "ep001-en-master",
  "unit_id": "ep001",
  "cut_id": "main",
  "kind": "master",
  "language": "en",
  "spec": {
    "width": 1920,
    "height": 1080,
    "fps": "24000/1001",
    "audio": {
      "required": true,
      "channels": 2,
      "sample_rate": 48000
    },
    "subtitles": [
      {"language": "en", "mode": "sidecar", "path": "subtitles/master.en.srt"}
    ]
  }
}
```

The [schema](schemas/deliverable.schema.json) validates manifests, immutable
bindings, and immutable locks. Kinds are `master` and `proxy`; language variants
are separately indexed IDs, not a mutable language selector on another master.
Language accepts a language-tag-shaped label, including `zxx` for wordless
output. It does not certify the language actually spoken.

Only `cut_id: main` is supported. Alternate cuts, aspect-changing reframes,
burned-in subtitle requirements, and cut-scoped Studio roots are not implemented.
Do not relabel a main render as an alternate cut.

Dimensions are positive even integers. FPS is a positive number or rational
string. `audio.required: false` means **no audio stream**, not optional audio.
With audio required, optional `channels`, `sample_rate`, and `language` constrain
every audio stream. Audio/subtitle language tags are compared literally to the
probe, without assuming equivalence between two- and three-letter codes.

Subtitles are explicit `sidecar` files or `embedded` streams. Empty requirements
permit no embedded subtitle streams. Sidecar SRT/VTT files must be nonempty
UTF-8 and are hash-bound; timing, text, reading speed, translation, and sync
remain the subtitle workflow and actual review's responsibility.

## Commands And API

```bash
uv run python .agents/scripts/deliverables.py validate PROJECT ep001-en-master
uv run python .agents/scripts/deliverables.py status PROJECT ep001-en-master
uv run python .agents/scripts/deliverables.py bind PROJECT ep001-en-master \
  --render-record units/ep001/studio/renders/master.mp4.render.json \
  --expected-revision SHA256_FROM_STATUS
uv run python .agents/scripts/deliverables.py lock PROJECT ep001-en-master \
  --decision review/final-decision.json \
  --expected-revision SHA256_FROM_STATUS
```

Read status again after binding, before locking. `--expected-revision` is the
SHA-256 of the current deliverable manifest bytes, not a counter. Every command
prints JSON and exits `0` when current evidence is valid, otherwise `1`.
No `--unit` is needed: the explicit ID resolves its unit through `production.json`.
There is no newest-render fallback and no aggregate all-units completion gate.
Input render and decision paths can be absolute within the project or
project-relative; durable paths are always production-relative.

Public Python interfaces in `.agents/scripts/deliverables.py`:

```python
def validate(root: Path, identifier: str) -> list[str]: ...
def status(root: Path, identifier: str) -> dict[str, Any]: ...
def primary_gate(context: ProductionContext) -> tuple[list[str], dict[str, Any]] | None: ...
def bind(
    root: Path, identifier: str, render_record: Path | str, *,
    expected_revision: str, runner: studio.Runner = subprocess.run,
) -> dict[str, Any]: ...
def lock(
    root: Path, identifier: str, decision: dict[str, Any], *,
    expected_revision: str, runner: studio.Runner = subprocess.run,
) -> dict[str, Any]: ...
```

Mutations fail with `ValueError` subclasses for rejected evidence or conflicts;
unreadable files can raise `OSError`. `validate` converts these into findings.
Read-only status never creates locks, recovers a transaction, or writes state.
Malformed indexed manifests fail closed rather than falling back to root Studio.

## Binding And Technical Gate

Binding calls `studio_project.delivery_gate(context, exact_record_path)`, never
the newest-render form. The selected record must be schema-version 2, made by
Studio's `render` command at standard-or-higher quality, including for proxies.
It must match the selected unit context, ordered scenes, current placed takes,
output bytes/hash, and current Studio tree. Manual and draft-quality exports do
not qualify. A proxy is an independent delivery specification, not permission
to bypass those checks.

The service probes the selected output again with `ffprobe -show_format
-show_streams`, checks duration and recorded stream fields against its render
record, then checks dimensions, frame rate, audio, and embedded subtitles
against the specification. FPS allows a 0.001 rounding tolerance and checks
both nominal and average rates when available; this is not exhaustive
per-frame constant-rate certification.

Before binding, the **entire video and any audio are decoded**:

```bash
ffmpeg -nostdin -v error -xerror -err_detect explode -i OUTPUT \
  -map 0:v -map '0:a?' -f null -
```

Unavailable tools, timeout, missing video, decode error, malformed probe, and
spec mismatch fail binding. There is no header-only success fallback.
The immutable binding records `ffmpeg-full-audio-video-decode: pass`, actual
probed streams/duration, context, scenes, specification, Studio tree digest,
exact render-record/output hashes, shot-manifest/take hashes, and sidecar hashes.
Context and dependency hashes are rechecked after decoding before committing.
Locking relies on that decode evidence and unchanged bytes; it does not decode
again. Technical decode is not creative, language, continuity, or listening
approval.

## Approval And Prerequisites

Binding never approves. Locking consumes an actual supplied version-2
`stage_lock` decision with `stage_id: delivery`, `lock_kind: final_master`,
the current unit context, and exact output path/hash. Its
`upstream_sha256` **must include the immutable binding record path and hash**
returned by `bind`, so approval includes the delivery identity, specification,
render, streams, and dependencies. Existing scoped-decision rules also require
the real unit brief and current project authorization inputs.

The shared selection validator checks schema, review and upstream hashes,
current mode, actor, authorization, subject, and approved result. A passing
video review requires temporal/playback evidence, and an audiovisual delivery
also requires listening evidence. User decisions require quoted chat
authorization; agent decisions require current `approve_for_me`. The service
does not fabricate a review, quote, decision, or stage approval. An agent cannot
replace an existing user delivery lock.

Every earlier unit stage must be complete (or legitimately skipped where
optional), and delivery must be in review or complete. Locking re-runs the
brief and assembly-review gates, including the pinned browser check, current
shot selections, and picture/audio locks. It never calls the primary
delivery-stage gate: that gate consumes the resulting named lock, so invoking
it from lock prerequisites would create a cycle. It stores that prerequisite
snapshot hash and actual assembly gate evidence in the named lock.

## Unit Completion

`studio_project.py stage PROJECT --unit ep001 complete delivery` calls
`primary_gate` for units with named definitions. It revalidates the selected
delivery's current specification, binding, output, dependencies, named lock,
review, authorization and stage prerequisites. The latest named lock must
approve the current binding, not merely an earlier version of the same ID.
An unbound specification or a new binding without its own lock cannot complete
delivery, even when standalone `status` has no findings.

The stage retains its browser, scoped selection, canon and assembly-lock
checks, including required audio locks when audio preparation was skipped.
Completion evidence records `primary_deliverable_id`, the exact `render_record`,
and hash/version-bound `delivery_binding` and `delivery_lock` references.
No duplicate unit-ledger `final_master` lock is required or written. Newer
proxy/language renders do not redirect this evidence. Changes to the selected
specification or evidence block subsequent gate checks and completion attempts;
read-only checks do not rewrite historical completed ledgers.

`primary_gate` returns `None` only for legacy root projects or units with no
named definitions. Those keep the existing newest-eligible-render and
unit-ledger `final_master` behavior. The low-level `delivery_gate` remains an
exact-render technical check for binding, independent of primary selection.

## History, Transactions, And Staleness

Bindings append immutable `<id>.v000001.json` records; locks append immutable
`<id>.lock000001.json` records beside the indexed manifest. The manifest's
`versions` and `locks` lists contain path/hash/version references. The last
binding and last lock are independent: binding another version leaves the
previous lock untouched. New languages, proxies, and other episodes have
different manifests and never displace it. Previously bound output/record
paths cannot be rebound with changed hashes; use new render names.

Writers acquire the existing unit Studio lock, then the shared selection
writer lock, in the same order as Studio. They recover pending selection
transactions, recheck the expected manifest revision, validate all immutable
history, and atomically journal the new history file, manifest, and supplied
decision file together through `selection_service.commit_targets`.
Existing history, artifacts, and decision files are never overwritten.
An interrupted transaction retains its journal; the next writer recovers it
or reports a conflict. After recovery, stale expected revisions still fail.
No separate lock namespace or competing recovery protocol is introduced.
Traversal and symlinked delivery paths are rejected, including internal aliases.

Status checks immutable history, current context/tree/dependencies, the exact
render gate, and current lock authorization, review, selections and stage
prerequisites. It does not rerun the browser or media decode. A changed source
flags the affected current binding or lock in `findings`, while retaining its
history. Superseded version drift is reported separately in `history_findings`;
it does not prevent a newly reviewed current version from becoming valid.
Unrelated episode brief changes do not invalidate this unit.

A successful write can still report a stale older lock, because binding does
not silently replace that lock. Inspect the returned revision and history
before retrying; do not assume a nonzero status means no state was committed.
Local manual edits do not participate in advisory locks. Final rechecks detect
changes during the expensive gates; as with Studio's existing writer protocol,
this does not provide filesystem isolation against an uncooperative process
changing files at the instant of commit.
