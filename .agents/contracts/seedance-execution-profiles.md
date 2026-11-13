# Seedance Execution Profiles

Implementation follows `PLAN_Seedance_Model_Neutral.md` (2026-11-13).
Creative writing uses `seedance-prompt`; retained 2.0/2.5 adapters serialize
only their applicable bindings. A model name, price row or announcement is
not execution evidence. No Flash capability profile is bundled.

## Version 2 Evidence

Opt in with `schema_version: 2` in capability evidence. Retain legacy fields
`model`, `source`, `verified_at`, `operations`, `parameters`, `reference_roles`
and `max_references`. Add:

- `profile_id`, `provider`, one exact `operation`, `transport`,
  `tool_schema_revision`, `valid_from` and `expires_at`.
- `operations` contains exactly that one operation.
- `parameter_constraints`: self-contained JSON Schema constraints applied to
  the complete parameter object. Remote `$ref` and `$dynamicRef` are rejected.
- `modality_limits`: image/video/audio entries with nonnegative `max_count`
  and optional positive `max_duration_seconds` for the total bound duration.
  Missing modality evidence permits no inputs of that modality.
- `preview`: `native_draft`, `promotion`, `ordinary_preview`, each explicitly
  `supported`, `unsupported` or `unknown`. Unknown never grants execution.

Evidence must be currently valid, with `valid_from <= verified_at <= now <
expires_at`. Parameter schemas still reject unknown controls and mixed
first/last-frame and reference-image roles remain independently verified.

## Destination And Digest

`prepare_request.py --capabilities <file> --provider <intended-provider>
--tool-schema-revision <intended-revision>` uses independently supplied
destination values, together with `--model`, `--operation` and `--transport`.
Do not derive the intended destination from the same untrusted evidence file.
Preparation persists `extensions.execution_profile`:

```json
{
  "destination": {
    "provider": "<independently intended provider>",
    "model": "<exact selected model>",
    "operation": "<one intended operation>",
    "transport": "ark-mcp",
    "tool_schema_revision": "<independently intended revision>"
  },
  "evidence": {"schema_version": 2}
}
```

This abbreviated example is not valid execution evidence. The complete
snapshot must pass the capability schema and exact destination checks.
For measured timed references, `--ref-duration path=seconds` stores optional
`reference_durations` by content SHA-256 inside the same binding. Measurements
must come from actual source inspection, not estimates or a model name.

Only profile-bearing requests add this binding to the request digest.
Profile-free v1/v2/v3 request bodies and typed context hashing remain unchanged.
Preparation and registration validate before writes; the existing
`prepared -> submitting` path revalidates the persisted digest, evidence
validity, destination and preview policy, not just a later capabilities file.
Reconciliation of already-submitted profile-free historical jobs retains the
existing adoption path; it does not authorize a new plain final or resubmission.

## Policy Is Not Mechanics

Exact standard `dreamina-seedance-2-5-260628` and Premium
`dreamina-seedance-2-5-premium-260915` retain mandatory native 480p Draft
policy in both review modes. Boolean `draft: true` and explicit `480p` are
required before selected promotion. Unsupported native mechanics block
execution; never remove `draft` to satisfy the schema.

Other exact bindings use only verified profile mechanics. A supported
ordinary preview is paid and non-promotable. It does not satisfy mandatory
native Draft policy. A final from it is a new reviewed/registered request.
Unknown capability support blocks paid execution, not prompt-only writing.

## Promotion And History

Promotion names one unique, selected, terminal successful native provider
task. It preserves prompt, ordered reference hashes, model, operation,
transport, profile and current production scope. Inputs are inherited or
preserved, not replaced; changed creative parameters require a new Draft.
The selected output and review evidence must remain current. Profile-aware
selection includes `requests/request_<asset_id>.json` in `upstream_sha256`,
with its exact file hash and registered `request_sha256`. An output-only
selection cannot authorize a changed profile-bearing request.

The ledger stays `schema_version: 1`; no migration occurs. New profile-bearing
entries store exact model/operation/transport/profile beside immutable
request/prompt/context hashes. Profile-bearing promotion requires matching
ledger identity, approved selection and the seven-day expiry window.
Scoped historical checks remain active. Old records are readable but cannot
be reinterpreted as native Draft by adding a new profile or model substring.
Final provider success is not artistic approval: inspect final playback and
sound freshly, then select under the existing approval authority.
