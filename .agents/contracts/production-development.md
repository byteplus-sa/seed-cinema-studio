# Development Evidence

This is the Phase 4 development contract from `PLAN_SEED_CINEMA_STUDIO.md`.
It adds evidence formats, not a second lifecycle. The
[production policy](production-policy.md) retains approval, rights and
generation authority. Nothing here activates unit Studio layouts.

## Source Fidelity

Keep the supplied screenplay, treatment, glossary and locked dialogue unchanged.
Record project-relative paths and SHA-256 before deriving material. New prose
and proposed revisions live in new versioned artifacts. Never silently convert
a faithful extraction into an adaptation.

Use the effective brief supplied by the caller. Do not infer story formula,
market, language, runtime or aspect from one another. A quiet scene, a wordless
sequence or a resolved ending is preserved when requested. No automatic
Hook/Turn/Cliffhanger, fixed scene count or to-be-continued card applies outside
the explicitly selected micro-drama route.

## Artifact Layout

Use `development/<unit>/` as an evidence namespace. A stable legacy label such
as `main` is allowed when explicitly documented; it is not a production
manifest or a new Studio root. Preserve the existing `project.md`, source
scripts, global scene/shot IDs and shared `continuity.md`.

| Artifact | Required content |
| --- | --- |
| `sources.json` | Version 1, scope label, source path/hash pairs, source role and extraction limits |
| `treatment-vNN.md` | Source inventory reference, premise, characters, progression and ending; supplied facts versus proposed additions |
| `outline-vNN.md` | Ordered scene IDs, narrative purpose, state changes and source section references |
| `script-vNN.md` | Only when requested or needed; exact locked words preserved, proposals distinguished |
| `scene-list-vNN.md` | Source page/section, ID, setting/time, cast, visible action, purpose, incoming/outgoing state, dialogue references and optional estimated duration |
| `continuity-vNN.md` | Scoped state/knowledge audit, source references, contradictions, proposals and unresolved items |

Omit an output that merely duplicates a supplied locked artifact. All derived
documents identify their source hashes and status (`draft`, `proposed`,
`confirmed` with actual evidence). These labels do not replace mode-valid
production decisions. Estimated scene durations never become subtitle timing.

Example source inventory:

```json
{
  "schema_version": 1,
  "unit_id": "short",
  "sources": [
    {
      "path": "source/screenplay.md",
      "sha256": "<actual-sha256>",
      "role": "supplied-screenplay"
    }
  ],
  "limits": ["No footage reviewed; continuity is script-level only."]
}
```

This inventory is a documented development format, not a newly enforced
machine schema. Never fabricate a hash or invent source authorization.

## Continuity Records

Keep identity invariants in canon and mutable state in a ledger. Suggested
shared tables, added without deleting existing prose:

| Subject | Property | Incoming | Outgoing | Unit/Scene/Shot | Story Time | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Stable element ID | Wardrobe, location, injury, wetness, prop custody or door state | Supported value or unknown | Supported value or unknown | Existing IDs | Chronology separate from edit order | Path/hash plus page or playback range | Scripted, observed, confirmed or unknown |

| Fact ID | Character | Knows Before | Learns At | Knows After | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Stable fact | Stable character ID | Yes, no or unknown | Scene and supported event | Yes, no or unknown | Path/hash plus source locator | Scripted, observed, confirmed or unknown |

Audience knowledge is distinct from character knowledge. A flashback's screen
position is not its story-time position. An offscreen change needs supporting
source or a labeled proposal. Contradictions retain both evidence references,
severity, affected units and suggested repair scope; never silently pick one.

## Completion Boundary

`story-development` and `series-continuity` are independent document leaves.
They do not invoke sibling skills, generate assets, migrate projects or approve
stages. The caller can compose scene craft and perform authorized changes.

Development completion means the requested documents exist with source
provenance and unresolved items disclosed. It does not certify creative quality,
historical accuracy, footage continuity or cultural correctness. Script-only
review must never be presented as actual playback evidence.
