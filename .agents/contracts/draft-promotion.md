# Draft and promotion

In `review_mode: strict`, Seedance 2.5 generates a cheap 480p **Draft** first and renders the approved Draft
as the higher-resolution **final** later, reusing the Draft's seed and inputs. The
Draft task ID is the handle for that later render, so it is recorded the moment
the provider acknowledges it. In `review_mode: default` (also when absent),
direct final generation is permitted within approved scope and budget; no draft
or draft-assembly pass is compulsory. This contract applies when a draft or
promotion is actually requested, not as a prerequisite to direct finals;
`production-policy.md` owns approval, review and registry rules.

## Verified provider behavior

Source: the `seedance_2_5_create_task` and `seedance_2_5_premium_create_task`
tool schemas in `ark-mcp`, read through `ark_job_capabilities` on 2026-10-14,
where both listed `draft` and `draft_task_id`. Check it again through
`ark_job_capabilities` before the first submission of a project and record the
result as capability evidence.

| Step | Request | Result |
| --- | --- | --- |
| 1. Draft | `draft: true`; explicit `resolution: "480p"`; prompt, references, duration, ratio, `generate_audio` as for a normal request | A 480p preview, billed as a normal 480p video. Its provider `task_id` is the **draft ID** |
| 2. Final | `draft_task_id: "<draft ID>"` only, plus optional `resolution`, `return_last_frame`, `watermark`, `execution_expires_after`, `priority`, `safety_identifier` | The approved Draft rendered at the family's final resolution (1080p for Seedance 2.5; 4k for Seedance 2.5 Premium), billed independently |

- `draft` and `draft_task_id` are mutually exclusive.
- The final reuses the Draft's model, prompt, media, duration, ratio, seed,
  `generate_audio` and `omni_reference_task_type`. Do not send `prompt`, `images`,
  `videos`, `audios`, `duration`, `ratio`, `generate_audio` or
  `omni_reference_task_type` with `draft_task_id`.
- Omitted optional settings (for example `watermark`) use the model defaults, not
  the Draft's values; set them again deliberately.
- The Draft must have succeeded, been created by the same tool, and be **at most
  7 days old**. After that the Draft cannot be promoted; the shot needs a new
  generation, which can change picture, timing and audio.
- Because the final reuses the prompt, **edit the prompt only before the Draft**.
  A changed prompt is a new Draft.

## Recording the draft ID

1. Prepare and register the Draft as its own operation (`prepare_request.py
   --register`) with params `draft: true` and `resolution: "480p"`. Save the
   acknowledged provider task ID in the registry at once (`provider_task_id`).
2. Add the Draft to `projects/<project>/drafts.json` with `draft_ledger.py record`.
   Each entry holds the shot or asset, the Draft operation ID, the **draft task
   ID**, the prompt and request hashes, the take file, the submission date, the
   expiry (submission date plus 7 days), a status and, later, the final operation.
3. Status moves `drafted` to `approved` (the Draft passed review and a mode-valid
   selection) to `promoted` (a final operation exists). A Draft past its expiry
   that was never promoted is `expired`.
4. Keep the ledger in step with the registry: the registry is authoritative for
   provider IDs and submission state, the ledger for expiry and promotion state.
   `draft_ledger.py list` reports both and flags Drafts about to expire.

## Promoting a Draft

1. Confirm the registered native 480p Draft completed successfully, has a
   passing review and a selection authorized by the current approval mode, is
   `approved` in the draft ledger, is within 7 days, and its take is the one
   placed in Studio. A provider task ID or an unverified `approved` flag alone
   is insufficient.
2. Prepare a new operation for the final: params `draft_task_id`, `resolution`
   (final resolution) and the settings to repeat (`watermark: false` unless the
   user wants it). Put the Draft operation ID, draft task ID and Draft request hash
   in the request's `extensions.draft_promotion` so the link is auditable. The
   request carries no prompt or references; the prompt snapshot stays the Draft's.
3. Preflight and register it like any other paid request (complete request hash,
   capability evidence listing `draft_task_id`, estimated cost at final
   resolution). Strict or explicit required rules need a matching report;
   default needs minimal inline preflight. Any supplied report must pass.
   Then submit through the same transport. Never submit a final
   through a second transport.
4. Save the final's provider task ID, run `draft_ledger.py record` to mark the
   Draft `promoted` with the final operation ID, and download the final.
5. Inspect the final output (picture, audio, timing) before it replaces the Draft
   take in Studio; a promotion does not skip QA, and a different output is a new
   take with its own selection.

## Cost and planning

- Draft cost is a normal 480p generation. The final is billed again at its own
  resolution. Estimate both with the pricing formula in the production recipe and
  report estimated and confirmed costs separately.
- When using drafts, promote in batches within the 7-day window. Run
  `draft_ledger.py list` at session start; plan promotions before expiry.
- If the user explicitly asks for 480p delivery, the Draft can be the delivery
  take after delivery QA and no promotion is needed.

## When native promotion is unavailable

If the tool, model or operation does not support `draft` or `draft_task_id`
(an older tool, another transport, an edit or extension operation, or an expired
Draft), a 480p request is only a cheap iteration. The final is then a fresh paid
generation using the selected prompt and approved inputs, with its own registry
entry and mode-appropriate preflight/review, and it can change picture, timing and audio. Record
the constraint in the project handoff.
