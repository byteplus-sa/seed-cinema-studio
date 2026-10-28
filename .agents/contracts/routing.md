# Tool and skill routing

## Production format routing

Apply these workspace routes before the vendored HyperFrames creation table or
intent interview. A specific edit, inspection or render remains that operation,
not a new production intake. Match the requested format, not aspect, genre,
runtime or the presence of music. An explicit format takes precedence over a
workflow hint; an existing selected micro-drama workflow supplies defaults only
when the format is otherwise unspecified. A conflicting lock still requires a
recorded, authorized change before production continues.

| Intent | Route |
| --- | --- |
| Explicit micro-drama format | `micro-drama`; an existing selected workflow retains its episode defaults and market writers |
| Cinematic short, film, episodic show, or custom narrative production | `film-production`; preserve the supplied script or treatment and confirmed delivery choices |
| Unspecified production format | `film-production`; develop a general brief, never assume micro-drama |

The local `hyperframes` entry point hands narrative orchestration to
`film-production`; its domain skills still own composition, editing and rendering.
Do not install `general-video` to make a narrative route resolve. Independent
prompt-only or storyboard-only requests still use their specialist, not a full
production lifecycle. Only explicit micro-drama selects
`microdrama-story-formats` or its market pack as the story-format writer.

Use [production brief](production-brief.md) and
[production profiles](../catalog/production-profiles.json) for shared settings,
disclosed defaults and legacy compatibility. General production follows confirmed creative
choices, without imposed Hook/Turn/Cliffhanger beats, duration, aspect or cards.
Rights, approval, review and registration gates remain universal.

`project.md` is the canonical shared brief; a validated `production.json`
selects unit briefs and ordered scenes. Without a manifest, retain root Studio
commands. With one, resolve the selected `--unit` to `units/<unit>/studio/`;
multiple units require explicit selection for unit operations. Invalid manifests
fail closed. Candidate `production.plan.json` validation stays read-only and
never activates or migrates a project.

Do not replace the brief with a fresh HyperFrames interview or a second editable
`BRIEF.md`. Unit `init`/`sync` generate a scoped adapter with context and source
hashes. Reconcile existing user-authored or modified adapters explicitly.
Shared canon remains production-scoped; unit stages, selections, provenance and
renders bind their own context. Follow [version boundaries](production-versions.md)
and [Studio commands](production-policy.md), not unscoped upstream examples.

## Development And Post Routes

| Intent | Route |
| --- | --- |
| General premise, treatment, outline or supplied-script scene list | `story-development`; source-preserving document leaf, with `scene-craft` composed separately by the orchestrator for dramatic craft |
| Character objectives, tactics, listening and performance beats | `acting-direction`; establish the source-bound performance plan before shot design |
| Seedance performance cue encoding | `seedance-acting-console`; consumes the plan without redoing scene analysis |
| Staged fight choreography | `seedance-fight-choreography`; stable actors/props and readable action/reaction chains |
| Story bible, mutable state or character-knowledge audit | `series-continuity`; evidence and proposals, never automatic canon changes |
| Coverage, pacing or continuity review of an actual cut | `editorial-review`; `editorial.py export/check/reconcile` supplies current Studio snapshots without applying order |
| Sound cues, mix decisions or listening evidence | `sound-post`; caller owns any authorized audio generation, mixing and rendering |
| Locked-text multilingual SRT/WebVTT | `subtitle-sidecars`; the retained `microdrama-subtitles` command uses the same engine |
| New language or market version of a delivered film, short or episode | `production-localize`; retain `microdrama-localize` for explicit micro-drama compatibility |
| Explicit named master, proxy or language delivery binding | `deliverables.py validate/bind/lock/status`; resolve by ID and bind an explicit unit render record, never newest-project-wide output |

Leaves do not invoke siblings. Localization is an explicit orchestrator with
source-preservation and honest lip-sync/language QA. Neither subtitle command
translates, transcribes or burns text into generated footage.
Editorial export/reconcile writes evidence records only; Studio remains the
editable authority and `sync` does not auto-apply their order. Only primary cut
`main` is supported. Sound/localization record validation is not listening,
native-speaker review or creative approval. No provider, publish or migration
authorization follows from choosing one of these routes.

## Tools and specialist capabilities

| Intent | Route |
| --- | --- |
| Platform administration, catalog, pricing, billing, interactive generation | Available Ark CLI skills and current CLI help |
| In-agent durable generation | `ark-mcp` preferred; persist project-local media and request/task evidence |
| MCP unavailable before submission | Equivalent Ark CLI transport if it supports the same required contract and authorized operation |
| User explicitly requests direct HTTP/curl generation | Use the documented endpoint and exact API contract; resolve credentials from runtime configuration, record `curl` as the transport, and preserve the same review, registry, persistence and reconciliation gates |
| Timeout after possible submission | Reconcile the existing operation; changing transport is not permission to submit twice |
| Prompt composition only | Relevant independent prompt skill; no asset-generation or production-lock ceremony for a writing-only task |
| Scene storyboard detail, panel lineage and repair, review sheets or animatics | `scene-board-sheet`; planning and review only, never a Seedance generation reference |
| Multi-scene production | `film-production`; declared orchestrators route specialist work |
| Exact static copy, poster, UI, title/end card, product grid, logo/price/CTA layout, or transparent overlay | `html-graphic-render`; keep source and inputs local, render exact-size PNG, and preserve provenance |
| Invented photographic or illustrative still | Appropriate Seedream skill; hybrid work finishes exact copy/layout through `html-graphic-render` after the image is selected |
| Animated exact graphic or timed overlay | HyperFrames for animation; HyperFrames or FFmpeg for final video composition |
| Media sourcing or generation: images, icons, voiceover, music, SFX, captions | Generate through `ark-mcp` (Seedream, Seed Audio, `speech_to_text`); acquire authorized real assets per [Element identification](element-identification.md); finish, including grades and LUTs, with FFmpeg or HyperFrames. The upstream `media-use` skill is not installed; ignore its pointers inside vendored HyperFrames skills |
| Media inspection | Native playback/listening when available and sufficient for the required criteria; supported provider analysis when coverage is insufficient or explicitly requested. Record temporal, dialogue and listening evidence and any unresolved checks; Studio stage gates still apply |
| Production stage review | Selected legacy or unit HyperFrames Studio through `studio_project.py` (`sync`, `stage complete` with its `status` and `check`; `--unit` where applicable); pre-Studio canvas projects with `showcase.json` keep the `showcase-html` canvas |
| Interactive editing, assembly and final render of a production | HyperFrames Studio; `studio_project.py render` is the only authority for final files and writes the hash-bound render record; post work made elsewhere is placed in Studio and rendered. Skills stay local; no `hyperframes skills` installs; `publish`, `cloud`, `lambda`, `cloudrun` and other account commands only on explicit request |
| Ad-hoc media comparison, also an optional look at a Studio project's elements, audio or candidate takes (never a gate) | `showcase-html --quick`; `media-review` only for an explicitly requested OS player or unavailable browser |
| Mermaid system/process diagram | `design-doc-mermaid` when available; cinematic blocking requests use `blocking-map` |
| Narrative reference-video inspiration | Obtain decodable local media first. Use capable native inspection and timestamped measurements; use permitted `ark-mcp` analysis when coverage is insufficient or explicitly requested. Full reverse-engineering follows `template-factory`. Preserve selected unit, source writing, quiet holds and format; scripts, article text and sparse frame samples alone do not establish motion grammar |
| Reference soundtrack analysis | Native audio input or a capable local audio model first; permitted audio-understanding tools or documented human listening when needed. ASR and separation may assist, but do not establish listening. Record full-soundtrack coverage and provenance under privacy and explicit offline constraints; unresolved sound is not approved post evidence |

Deterministic HTML/CSS/SVG is a production route, not a provider fallback. In
this workspace, that shorthand means one HTML entrypoint with project-local CSS
and SVG dependencies; standalone CSS or SVG is not a renderer entrypoint.
Choose it when exact copy, alignment, repeated brand assets, safe areas, or
transparent geometry are the primary fidelity risk. It does not create a model
prompt or provider operation. A hybrid retains normal generation evidence for
its synthesized image layer and a separate deterministic render record for its
exact graphic layer.

## Capability evidence

Resolve the actual tool schema/model binding before selecting operation, resolution, duration, reference roles/counts, or optional flags. A capability record contains model, source, verified_at, operations, parameter JSON Schemas, required_parameters, reference_roles, max_references, and supports_first_frame_with_reference_images. Recheck when the tool, binding, or operation changes; cached evidence is historical, not a live guarantee.

The workspace default remains Seedance 2.5; legacy 2.0 may be selected for a verified capability such as an available lower-cost variant. Requested 4K needs 2.0 or, when the operator has enabled it, the whitelist-only 2.5 Premium model (the 2.5 feature set plus 4K); standard 2.5 tops out at 1080p. Skills defer to this paragraph for 4K routing. A face in a shot is a QA concern, not an automatic model switch. Chaining does not override unsupported mixed frame/reference inputs.

Credential names are BYTEPLUS_MODELARK_API_KEY and BYTEPLUS_SEED_AUDIO_API_KEY. A transport may document compatibility aliases. Resolve secrets, region, and base URL at runtime; never serialize credentials into requests, fixtures, snapshots, or logs.

## Operation names

New requests set `operation` to the short verb, not the provider tool name: `generate` (the dominant value in existing registries), `edit`, `extend`, `generate_variations`, `text_video_to_audio`, `enhance`, or the legacy hyphenated `erase-subtitles`. `validate_request.py` checks `operation` against the `operations` list in the capability evidence, so a value must appear there. The provider tool is identified by `model` and `transport`. Submit long-running work through `ark_job_submit`. Existing records that carry a tool name such as `seedance_2_5_create_task` are read as-is; constrain the schema to an enum only after the legacy-registry migration preview.

## Directorial axes

For applicable character-performance work, first follow
[Performance direction](performance-direction.md), including its prompt checks
and actual-take acceptance. Static camera choices do not exempt acting;
source-preserving edits inherit it. Static assets need no performance plan.

Read [seedance-reference.md](seedance-reference.md) when composing a generation-bound shot. Plan the shots first with `seedance-shot-design` (per-shot camera, lens intent and light, with a recorded reason for any static camera or constant light), then load only the preset skills the plan or the user's request needs for camera, lens, lighting, grade, acting, pacing, blocking or medium. Keep one grade per clip, one dominant lighting direction per shot and one or two camera moves per shot unless the explicitly requested choreography needs more.
