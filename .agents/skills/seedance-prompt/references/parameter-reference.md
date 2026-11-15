# Parameter Reference

Focused reference for `seedance-prompt`. Read [the entrypoint](../SKILL.md) for
mode selection and caller responsibilities.

This is a historical 2.0/2.5 API snapshot, not a creative default or family-wide evidence. Bind exact
provider/model/operation/transport/tool revision and current validity before
execution. No Flash support is inferred; general craft uses `seedance-prompt`.

- [Quick reference card](#quick-reference-card)
- [Legacy 2.0 snapshot](#legacy-20-snapshot)
- [Draft mode](#draft-mode)
- [Guide disclaimer](#guide-disclaimer)

## Quick reference card

### Model IDs

| Variant | Model ID |
|---|---|
| Seedance 2.5 | `dreamina-seedance-2-5-260628` |
| Seedance 2.5 Premium (whitelist only) | `dreamina-seedance-2-5-premium-260915` |
| Seedance 2.0 Standard (legacy) | `dreamina-seedance-2-0-260128` |
| Seedance 2.0 Fast (legacy) | `dreamina-seedance-2-0-fast-260128` |
| Seedance 2.0 Mini (legacy) | `dreamina-seedance-2-0-mini-260615` |

**MCP tools:** `seedance_2_5_create_task` (submit), `seedance_get_task` (shared 2.0/2.5 poll), `seedance_list_tasks` / `seedance_cancel_or_delete_task` (shared with 2.0).

Preserve the selected exact ID. The [Model list](https://docs.byteplus.com/en/docs/ModelArk/1330310)
can identify models, but does not establish account access or transport support.
Never select another model automatically to satisfy a requested output.

### Historical standard 2.5 reference limits

| Material | Max | Recommended |
|---|---|---|
| Images | 30 (each ≤ 4K) | 1–8 subjects |
| Videos | 10 (combined ≤ 30s) | 1–5 subjects, 5–10s each |
| Audio | 10 (combined ≤ 30s) | Only what's directly relevant |
| **Total** | **50** | — |

### Audio syntax

These are 2.5 prompting conventions. Verify syntax for the selected operation
and destination; do not infer language, audio or reference support from a family name.

| Content | Syntax |
|---|---|
| Music | `()` |
| Sound Effects | `<>` |
| Dialogue | `{}` |
| Subtitles | `【】` (provider syntax; workspace footage stays text-free, so subtitles are a post layer) |

### Parameter auto-lock summary

Historical 2.5 operation behavior only. Source preservation is a separate
acceptance requirement: a documented duration tolerance never authorizes
trimming, rounding, padding, retiming or losing audio tails.

| Task | Aspect Ratio | Duration |
|---|---|---|
| Video editing | Locked to input | Locked to ~input (±0.3s) |
| First/last-frame | Locked to first image | Settable |
| Video extension | Locked to input | Settable |

### Camera techniques

| Technique | What to Specify |
|---|---|
| One-take shot | Subjects, spaces, events in order |
| Dolly zoom | Subject size; bg closer or farther |
| Aerial view | Height, direction, area to reveal |
| FPV | Flight path, speed, turns |
| Bullet time | Action to freeze; orbit direction |
| Handheld camera | Subject; amount of shake |
| Bounce speed ramp | Acceleration/deceleration points; final state |

### Reproducibility
- `seed`: not exposed by the Seedance 2.5 `seedance_2_5_create_task` tool; reproduce a look by reusing the approved prompt and references. Draft promotion reuses the draft's seed.
- `camera_fixed`: not exposed by the Seedance 2.5 `seedance_2_5_create_task` tool (checked 2026-10-06; see the [legacy 2.0 snapshot](#legacy-20-snapshot) for REST), so state a locked camera in the prompt and record its `static_reason`.
- `return_last_frame`: set to `true` to chain multi-shot continuity.

### Historical standard 2.5 output
- 4–30s per generation (up from 4–15s in 2.0).
- Output resolution: 480p, 720p, or 1080p. Preserve a locked 4K target and selected
  model; unavailable controls remain unresolved. Alternatives under the workspace
  [routing contract](../../../contracts/routing.md) require explicit selection.
- Multi-round extensions up to 180s (beta).

### Preview policy and cost
- In both review modes, use native Draft-first, then promote the selected draft
  (see [Draft mode](#draft-mode)).
  Exact standard 2.5/Premium retain mandatory native Draft policy; unsupported
  mechanics block execution, never a dropped-draft fallback.
- Keep resolution in request parameters, separate from prompt text and Studio
  canvas dimensions. A 480p request is not itself a native Draft: use `draft: true` and later
  `draft_task_id` as described in the workspace draft and promotion contract
  (`.agents/contracts/draft-promotion.md`), recording the draft task ID, and verify
  the live tool schema first. Final requests and outputs need fresh
  mode-appropriate preflight and output sanity under the workspace production
  policy; strict or explicit required rules need matching review reports.
- Video generation is billed per successful task completion; estimate final-resolution cost from the pricing page.
- Confirm current billing rules on the [Pricing page](https://docs.byteplus.com/en/docs/ModelArk/1544106).

### Language evidence

The historical 2.5 guide listed Chinese, English, Spanish, Indonesian, Malay,
Thai, Arabic, Portuguese, Vietnamese, Japanese and Korean. This list is not
proof of support or incapability for the selected exact model. Keep requested
language and approved words unchanged; verify current audio/voice controls.
The caller may compose the independent `seedance-prompt-25-dialogue` specialist
or an explicitly selected market pack such as `seedance-prompt-25-filipino`.
No annotation, translation or separate lip-sync track is automatic.

### Consistency rules
- The caller selects and approves recurring character, prop and scene sheets
  before dependent generation; missing sheets stay unresolved in prompt-only work.
- Storyboards are optional planning and review artifacts. Generate video from canonical Element references (R2V) or text-to-video, with the board's staging written into the prompt.
- Preserve approved reference identities across a scene; include only the
  selected assets relevant to each shot and verify every changed binding.
- Preserve a written locked-decisions and requested-delta record for every retry.
- Change only one of {prompt wording, reference bundle, motion design} per retry when practical.

### Storyboards are not video inputs

A storyboard grid, board or panel is never bound to a Seedance request
(`board.animatic_review_only`): panel numbers and the sketch or watercolour
medium leak into the video, and output-copyright rejections rise. Translate
the approved board into shot lines and bind the canonical character, location
and prop references instead.

| Need | Mode | Reference rule |
|---|---|---|
| Reproduce an exact opening frame | First-frame | A clean full-frame keyframe in the final medium, with no marks |
| Lock start and end states | First + last frame | Two clean keyframes that share one aspect ratio |
| Keep identities while following a planned composition | R2V | Canonical Element references only; the composition is written as text |
| No storyboard at all | R2V or T2V | Canonical Element references (R2V) or text only (T2V) |

Clean keyframes must be independently authored non-board production stills,
not crops, redraws or regenerated board derivatives. Planning origin persists.

Do not combine first/last-frame roles with an R2V bundle unless current exact
operation evidence confirms that combination. The caller records
the chosen mode, ordered reference roles, paths, hashes, selected variants, and
approval states in the shot manifest before submission.

## Legacy 2.0 snapshot

The [2.0 prompt guide](https://docs.byteplus.com/en/docs/ModelArk/2222480) and
[2.0 tutorial](https://docs.byteplus.com/en/docs/ModelArk/2291680) inform this
historical table. Revalidate every API fact for the exact binding before use.
These values are not the generic prompt's limits and do not imply Flash support.

| Topic | Historical 2.0 scope |
|---|---|
| Generation | 4-15 seconds through `seedance_create_task` |
| References | Up to 9 images, 3 videos and 3 audio; audio not alone; combined video and audio each at most 15 seconds |
| Resolution | Standard 480p through 4K; Fast/Mini 480p or 720p |
| Preview | MCP had no native Draft controls; supported ordinary previews are paid and non-promotable |
| REST-only controls | `seed`, `camera_fixed`, `frames`; do not send them to an MCP schema that lacks them |
| Frame modes | First-frame, first-plus-last and R2V combinations require independent verification |

Reference labels, stable subjects, ordered action, spatial continuity and
inline constraints remain useful craft without inheriting these limits or a
mandatory section order. No Mini-to-Fast-to-Standard ladder is authorized.

## Draft mode

The Seedance 2.5 tool documents a two-step draft (`draft`, `draft_task_id`;
checked 2026-10-17). Confirm the current tool schema before relying on it.
This sequence applies to exact standard 2.5/Premium bindings in both review modes.

The caller follows the [draft and promotion contract](../../../contracts/draft-promotion.md)
and [execution profiles](../../../contracts/seedance-execution-profiles.md).
The registry is authoritative for provider IDs and submission state;
`draft_ledger.py` owns expiry and promotion state in `drafts.json`.
Keep exact model, operation, transport, profile, request/prompt/reference hashes,
current selection and the seven-day window consistent. A provider ID or an
unverified approved flag is not sufficient promotion authority.

1. **Draft.** Submit the full request with `draft: true` and an explicit
   `resolution: "480p"`. Prompt, references, duration, ratio, `generate_audio` and task type
   are frozen here; make every change before this call.
2. **Review and select** the draft under the project's approval mode: motion,
   shot plan, continuity, speech timing and audio.
3. **Final.** Call again with only `draft_task_id` plus output settings
   (resolution `1080p`, or `4k` on 2.5 Premium, or omitted, `watermark`,
   `return_last_frame`, `execution_expires_after`, `priority`, `safety_identifier`).
   Verify each control's supported value schema for the selected operation and
   destination; documentation alone does not authorize a value.
   The provider reuses the draft's model, prompt, media, duration,
   ratio, seed, audio setting and task type, so those fields must be omitted.
   Omitted output settings take model defaults, not the draft's values, so set
   `watermark: false` again. A draft can be promoted for about seven days.
4. **Re-check the final.** Picture and soundtrack are not byte-identical to the
   draft; inspect playback, dialogue words and audio again before placing it.

For another exact model/operation profile with verified ordinary preview
support, a 480p request is a non-promotable paid generation and the final is a
new reviewed/registered request. Unknown preview or promotion support blocks
execution. Ordinary previews cannot satisfy mandatory native Draft policy.

## Guide disclaimer

The examples in this skill illustrate prompt-writing techniques only. Actual
generation results may vary depending on the input materials, task complexity,
and generation parameters.
