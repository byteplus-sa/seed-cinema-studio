# Post Evidence and Read-Only Validation

This implements the Phase 4 contracts in `PLAN_SEED_CINEMA_STUDIO.md`.
Studio remains the editable timeline. Candidate JSON records describe edit
order and sound intent. The runtime snapshot service exports and checks actual
supported Studio edits, then explicitly reconciles the current snapshot record.
It never applies proposed JSON edit orders to Studio.

## API for Integration

Import `.agents/scripts/production_post.py`:

```python
@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    message: str

def validate_editorial(
    project: Path,
    document: Any,
    *,
    unit_id: str | None = None,
    selected_takes: Mapping[str, str] | None = None,
) -> list[Finding]: ...

def validate_sound(
    project: Path, document: Any, *, unit_id: str | None = None,
) -> list[Finding]: ...

def validate_localization(
    project: Path, document: Any, *, unit_id: str | None = None,
) -> list[Finding]: ...
```

Functions read local files, never mutate input dictionaries or project files,
never call providers, and return findings rather than approvals. Schema errors
stop semantic interpretation. Bundled schema/read failures can raise filesystem
errors; malformed project records produce findings. Empty findings mean only
that the supplied record is structurally valid and current against its declared
references. No context resolver or Studio lifecycle is imported here.

The caller supplies a validated unit ID and its current selected-take mapping
(`shot_id -> project-relative take path`) to enforce editorial membership.
Without that map, validation cannot establish selection or scene membership.
The CLI deliberately performs structural validation only.

```bash
uv run python .agents/scripts/production_post.py editorial projects/<slug> \
  --record editorial/<unit>/main.json --unit <unit>
uv run python .agents/scripts/production_post.py sound projects/<slug> \
  --record sound/<unit>/cues.json --unit <unit>
uv run python .agents/scripts/production_post.py localization projects/<slug> \
  --record localization/<unit>/<language>/record-v01.json --unit <unit>
```

Exit 0 means valid record; exit 2 means findings. JSON stdout contains `valid`,
`findings` and `review_status: not_evaluated`. A stable legacy scope label such
as `main` is allowed; merely writing these records never activates unit Studio.
`--record` is a project-relative path, so versioned candidates can be validated
without replacing `main.json`.

## Editorial Schema Version 1

Canonical snapshot location: `editorial/<unit>/main.json`.
Schema: [editorial.schema.json](schemas/editorial.schema.json), with shared
types from [post-common.schema.json](schemas/post-common.schema.json).

```json
{
  "schema_version": 1,
  "unit_id": "short",
  "cut_id": "main",
  "duration_s": 120,
  "source_edit": {"path": "studio/index.html", "sha256": "<actual-sha256>"},
  "entries": [
    {
      "id": "clip-010",
      "shot_id": "s100_sh010",
      "take": {"path": "scenes/scene-100/s100_sh010/take-v01.mp4", "sha256": "<actual-sha256>"},
      "source_in_s": 2,
      "source_out_s": 14,
      "source_duration_s": 18,
      "timeline_start_s": 0,
      "note": "Retain the quiet hold before the exit."
    }
  ]
}
```

Use real hashes, not the illustrative placeholders above. Array order is
explicit edit order. Clip IDs are unique; shot IDs may repeat for a split take.
Ranges are seconds, source out is exclusive, speed is 1, and the placed length
is `source_out_s - source_in_s`. Trims must fit the declared source duration;
placements must fit the declared cut. Long timelines have no arbitrary
episode-length ceiling. Declared durations must come from actual media probes;
the validator does not probe media or prove their accuracy.

Version 1 permits straight nonoverlapping cuts and gaps. A gap remains a gap;
validation does not add black or silence. Overlaps/dissolves, speed changes,
overlays, audio-only edits and alternate-cut application are not represented.
Do not flatten a complex manual Studio edit to satisfy this schema. Retain
Studio and report unsupported coverage instead.

`source_edit` binds one current Studio entrypoint or supplied exported edit
snapshot, not the entire Studio tree. Changed source/take hashes are stale.
Before import, main must resolve current context, validate scope/selection,
check whole-tree provenance and expected revisions, show an explicit diff and
preserve manually edited sections. Reconcile to Studio only through an
authorized transactional writer; never rebuild automatically during sync.

## Runtime Editorial Snapshots

`.agents/scripts/editorial.py` exports supported actual Studio placements,
including source trims and gaps. Its additional `runtime` binding includes the
whole Studio tree, current context and selected-take evidence. It probes source
durations and rejects unsupported edits instead of flattening them.

```bash
uv run python .agents/scripts/editorial.py export projects/<slug> --unit <unit> \
  --output editorial/<unit>/snapshots/edit-v01.json
uv run python .agents/scripts/editorial.py check projects/<slug> --unit <unit> \
  --record editorial/<unit>/snapshots/edit-v01.json
uv run python .agents/scripts/editorial.py reconcile projects/<slug> --unit <unit> \
  --record editorial/<unit>/snapshots/edit-v01.json --expected-revision absent
```

Export paths are immutable. Reconciliation updates only
`editorial/<unit>/main.json`, archives its prior content and requires its current
SHA-256 (or `absent` for the first write). Unit and shared transaction locks
protect the write; context, selection and edit changes trigger revalidation.
The optional `--expected-tree-sha256` pins the expected Studio tree.
Neither export nor reconciliation changes Studio HTML, grants approval or
applies proposed trims/reordering. Omit `--unit` for legacy root Studio.

## Sound Schema Version 1

Canonical location: `sound/<unit>/cues.json`.
Schema: [sound-cues.schema.json](schemas/sound-cues.schema.json).

```json
{
  "schema_version": 1,
  "unit_id": "short",
  "cut_id": "main",
  "duration_s": 120,
  "edit": {"path": "editorial/short/main.json", "sha256": "<actual-sha256>"},
  "cues": [
    {
      "id": "room-010",
      "kind": "ambience",
      "start_s": 0,
      "end_s": 120,
      "intent": "Continuous room tone beneath dialogue and the quiet hold.",
      "gain_db": -6,
      "source": {"path": "sound/room-v01.wav", "sha256": "<actual-sha256>"}
    }
  ],
  "mix_notes": "Keep dialogue foregrounded; delivery loudness target awaits confirmation.",
  "listening": {"status": "unverified", "evidence": [], "note": "No listening pass yet."}
}
```

Cue kinds: `dialogue`, `ambience`, `music`, `sfx`, `silence`. IDs must be unique,
ranges must fit the cut, and overlapping cues are allowed. `gain_db` is a
planned decision, not a measured loudness claim. `source` is optional for
unacquired/planned cues, but when supplied must exist and match its hash.
Silence cannot have a source. An intentionally silent cut still uses an
explicit silence cue and rationale. Empty cue arrays are invalid.

The referenced editorial record must itself validate and match unit, cut and
duration. Retiming or changing it invalidates its cue sheet hash. This does
not automatically retime cues, subtitles or masters.

## Evidence Is Not Approval

Review status is `unverified`, `pass`, `fail` or `not_applicable`, with a
nonempty note and an evidence array of path/hash pairs. Pass/fail requires at
least one current evidence file. Sound `not_applicable` requires only silence
cues; no-dialogue is not the same as no-audio.

Evidence documents must record reviewed media/hash, reviewer, method, actual
covered ranges, observations, limits and unresolved defects. The validator
only verifies the files exist and hashes match, not their truth or adequacy.
Do not invent listening, native-speaker review, playback or creative approval.
Unverified records remain useful planning artifacts but cannot satisfy a
delivery gate.

The production policy's hash-bound, mode-authorized picture/audio/final
decisions remain the only approval route. Main must validate evidence meaning,
current authorization, source scope, actual streams and render provenance
before any later gate. Snapshot reconciliation is not edit application.

## File Safety

References use project-relative POSIX paths. Absolute paths, `..`, dot/empty
segments, backslashes, missing files and symlink escapes fail. File hashes are
streamed. All numeric values must be finite; booleans are not numbers.
Localization also rejects outputs aliasing source files by path, symlink or
hardlink. Checks describe the current filesystem snapshot; they are not locks
and cannot authorize a later write against changed files.
