# Seed Cinema Studio

An agent-driven production workspace for cinematic shorts, films, episodic shows
and micro-drama with BytePlus Seedream, Seedance and Seed Audio. HyperFrames Studio
remains the editor and review surface; this is not a new standalone application.
Format, genre, medium, audience, language and delivery are independent choices.

The local implementation of `PLAN_SEED_CINEMA_STUDIO.md` supports validated
`production.json` manifests, scoped request/decision lifecycles, independent unit
Studio stages, explicit editorial snapshots and named delivery bindings. This
describes available APIs, not a fully verified release. Micro-drama retains prior
production evidence. The active technical pilot uses explicitly labeled synthetic
decision fixtures to exercise strict selection gates; those are not genuine
production decisions. Synthetic render/decode results are not creative-pilot
approval. Feature-length readiness requires measured
trials; custom formats also need scoped capacity and creative checks.

Legacy projects retain root `studio/`; manifest-backed projects use
`units/<unit>/studio/`. There is no automatic migration of active productions and
no automatic repository or checkout rename. The local Python package metadata is
`seed-cinema-studio-tools`, with dependency versions unchanged. This does not
rename schemas, lock namespaces, commands or production paths, publish a package,
or install additional workflows.

Generation does not require a project/unit budget or cost estimate, and legacy
spending caps do not gate preparation, registration, submission or retakes.
`budget_report.py PROJECT` remains a read-only cost report: it separates
estimates, confirmed billing, reservations and unknown exposure by currency.
Native drafts, rights/consent, review, provider limits, duplicate protection and
registry locks remain in place. Existing budget metadata is not rewritten.
New context version 2 ignores budget-only metadata edits. Historical context
version 1 remains readable for reconciliation; new submissions require explicit
re-preparation instead of silently migrating old hashes or approvals.

## Production routing

| Intent | Owner |
| --- | --- |
| Cinematic short, film, episodic show, custom narrative, or unspecified production format | `film-production`; follow the supplied script or treatment |
| Explicit micro-drama format | `micro-drama`; retain market writers and episode conventions |
| Existing composition edit or render | HyperFrames domain skills and `studio_project.py` |

The project-local HyperFrames entry point applies this routing before its upstream
workflow table. Narrative work does not need the absent `general-video` workflow.
Hook/Turn/Cliffhanger, 45-60 s episodes, 9:16 and to-be-continued cards are
micro-drama defaults only, not requirements for a cinematic short.

Scene craft and performance have separate owners in both narrative workflows:
`scene-craft` writes or audits scenes under the selected framework; its five-element
engine is optional. `acting-direction` supplies the scene's `## Performance plan`
before `seedance-shot-design`, and `seedance-acting-console` encodes the supplied
intentions, triggers and responses for Seedance. `seedance-fight-choreography`
adds readable staged exchanges when fights are in scope, preserving the selected
style, medium and outcome. `blocking-map` supplies planning geometry, not a
default video reference. These leaves do not invoke one another or submit media.
Quiet holds and source-preserving edits retain their approved intent. See the
[performance contract](.agents/contracts/performance-direction.md) for
`acting.plan_bound`, `fight.readable_exchange` and actual-take review requirements.

Shared choices and compatibility rules live in the
[production brief contract](.agents/contracts/production-brief.md) and
[production profiles](.agents/catalog/production-profiles.json). Profiles disclose defaults; confirmed
creative choices and locks win. No market is assumed. `project.md` remains the
canonical shared brief; a manifest's unit brief supplies scoped creative choices.
`init`/`sync` generate the selected unit's HyperFrames `BRIEF.md` adapter with
context and source hashes. It is not a second editable authority. User-authored
or manually changed adapters require explicit reconciliation.

## Production scope

Without a manifest, existing commands address root `studio/`. A validated
`production.json` selects ordered scene membership and unit briefs; scene/shot
IDs and shared `elements/`, `task_ids.json` and `drafts.json` stay at the production
root. Invalid or ambiguous manifests fail closed, never fall back to legacy.
One unit can be selected implicitly; multiple units require `--unit` for
unit operations. `status` without `--unit` returns aggregate unit status.

For an already validated manifest-backed project, the unit command forms are:

```bash
uv run python .agents/scripts/production_context.py /path/to/project --unit ep001
uv run python .agents/scripts/studio_project.py init /path/to/project --unit ep001
uv run python .agents/scripts/studio_project.py sync /path/to/project --unit ep001
uv run python .agents/scripts/studio_project.py stage /path/to/project --unit ep001 show
uv run python .agents/scripts/studio_project.py status /path/to/project --unit ep001
```

For forwarding commands put `--unit` before `PROJECT`:
`studio_project.py hf --unit ep001 PROJECT preview --no-open --json` and
`studio_project.py record-render --unit ep001 PROJECT FILE ...`. Shared
canon decisions remain production-scoped through `lock-element`; `sync-elements`
copies only each unit's declared required canon. Unit selections, stages,
provenance and renders cannot stand in for another unit's evidence.

Validate an explicitly supplied project-relative candidate without activating it:

```bash
uv run python .agents/scripts/production_context.py /path/to/project \
  --manifest production.plan.json --unit ep001
```

The candidate must reference existing briefs and scenes. Validation checks
membership, paths, profiles and context identity without writing production state;
it is not migration authorization. Do not activate or relocate an existing
production as a side effect. Active scoped work uses request v3 and decision v2.
V3 binds typed context and a normalized shared project digest; historical v1/v2
hashes remain unchanged. See [version boundaries](.agents/contracts/production-versions.md)
and [Studio/approval commands](.agents/contracts/production-policy.md).

## Editorial and delivery

`editorial.py export`, `check` and explicit `reconcile` capture and validate the
actual selected unit's Studio edit. They never apply a proposed order to Studio.
The snapshot supports straight cuts, trims and gaps, not arbitrary effects or
alternate cuts. `sync` preserves manual timeline edits.

`deliverables.py validate|status|bind|lock PROJECT DELIVERABLE_ID` resolves the
unit from the indexed deliverable. Binding requires an explicit `--render-record`
from `studio_project.py render` and `--expected-revision`; locking additionally
requires a reviewed, mode-authorized `--decision`. A proxy, language version or
another episode's render does not replace a named lock merely by being newer.
For units with named outputs, mark exactly one delivery index entry in
`production.json` as `primary: true`. Unit completion validates that ID's current
binding and named lock; missing or ambiguous primary selection blocks completion.
Only the primary cut `main` is supported. Technical validation is not playback,
listening, native-language review or creative proof. No automatic creative
approval, provider generation or publishing follows from these commands.

## Markets and languages

| Need | Skill |
| --- | --- |
| General narrative development from a supplied script or treatment | `story-development`; the `film-production` orchestrator composes `scene-craft` for scene craft |
| Explicit micro-drama stories for any market, language or genre | `microdrama-story-formats` |
| Spoken dialogue in any language, with a native-language check | `seedance-prompt-25-dialogue` |
| Filipino market pack (reference example) | `filipino-micro-drama` and `seedance-prompt-25-filipino` |
| Add a new market pack | [docs/ADD_A_MARKET.md](docs/ADD_A_MARKET.md) |

Seedance 2.5 speaks Chinese, English, Spanish, Indonesian, Malay, Thai, Arabic, Portuguese, Vietnamese, Japanese and Korean natively; other languages need an annotation, subtitle or audio-first route, which the dialogue skill records.

## Layout

| Path | Contents |
| --- | --- |
| `.agents/skills/` | Production orchestrators and independent specialist skills, one folder per skill |
| `.agents/contracts/` | Production, routing, identity and naming contracts the skills cite |
| `.agents/scripts/` | Request preparation, task registry, catalog sync, validation and `studio_project.py` (HyperFrames Studio bridge) |
| `docs/` | How to add a market |
| `projects/<production>/` | Local, uncommitted: shared canon/registry and either legacy root Studio or validated manifest-backed unit Studios |
| `tests/` | Studio, registry, approval and validation tests |

## Skills

Edit skills only under `.agents/skills/`.

| Skill | Summary |
|---|---|
| **acting-direction** | Plan character intentions, listening and performance beats before shot design; prompt-only direction, with no generation or take approval. |
| **story-development** | Prepare source-preserving premises, treatments, outlines and script-led scene lists without imposing a format formula. |
| **series-continuity** | Maintain shared story state and character-knowledge continuity with scoped, evidence-backed contradiction audits. |
| **editorial-review** | Review actual cuts and explicit edit snapshots for coverage, pacing and continuity without applying Studio edits. |
| **sound-post** | Write edit-bound sound cue sheets, mix decisions and honest listening evidence without generating or mixing media. |
| **subtitle-sidecars** | Write multilingual SRT/WebVTT from locked text and measured timing using the retained shared subtitle engine. |
| **production-localize** | Localize delivered films, shorts and episodes through explicit routes with source preservation and honest language and lip-sync QA. |
| **ark-mcp** | Uses the Ark multimodal MCP server for image, video, audio and 3D workflows, durable artifacts, and Advanced Creation Rights face/voice assets with existing authorization reuse and privacy rejection triage. |
| **brief-intake** | Shape intent-led briefs; hand off footage for native-first, capability-checked analysis while preserving confirmed decisions. |
| **color-grade-palettes** | Maps a named color grade palette or film look (teal & orange, bleach bypass, golden hour warm grade, etc.) into a canonical grade sentence for the Seedance Visual Style slot or the Seedream `Style:` section, with an optional matching FFmpeg filter graph for cross-shot matching. |
| **ffmpeg** | Video and audio processing with FFmpeg. Use for format conversion, resizing, compression, audio extraction, and preparing assets for editing and assembly. Covers converting GIF to MP4, resizing video, extracting audio, compressing files, and any media transformation task. |
| **filipino-micro-drama** | Opt-in Filipino-market micro-drama stories and episode briefs with genre formulas and cultural context, preserving approved words and requested language, register, code-switching and subtitle choices. Story material only. |
| **film-production** | General narrative orchestrator for cinematic shorts, films, shows and custom production, with scoped Studio edits and preserved legacy workflows. |
| **html-graphic-render** | Author and render exact-size static posters, cards, product grids, UI, and transparent overlays from one project-local HTML entrypoint with CSS/SVG dependencies, exact-copy checks, and schema-valid provenance. |
| **hyperframes** | HyperFrames entry point with local narrative routing to film-production, preserved micro-drama workflows, and composition/editing domains; no workflow installation. |
| **hyperframes-animation** | Atomic motion rules, multi-phase scene blueprints, transitions, and the seven runtime adapters (GSAP, Lottie, Three.js, Anime.js, CSS, WAAPI, TypeGPU). |
| **hyperframes-audio** | Mixing audio already placed in a composition — fades, crossfades, ducking, effect chains, automation envelopes, and submix buses. |
| **hyperframes-cli** | HyperFrames CLI development loop — init, add, catalog, capture, lint, check, snapshot, and render workflows, run through the pinned workspace entry. |
| **hyperframes-core** | Composition contract for renderable HTML video — timing data-attributes, clips, tracks, sub-compositions, variables, determinism rules, and validation. |
| **hyperframes-creative** | Non-animation creative direction — design specs, palettes, typography, narration, beat planning, audio-reactive visuals, and brand style. |
| **hyperframes-keyframes** | Seek-safe 2D/3D keyframes — punch-ins, camera moves, Ken Burns, match-cut handoffs, masks, SVG morph/draw, and runtime-specific APIs. |
| **hyperframes-registry** | Search, install, and wire hosted registry blocks and components into compositions before hand-building named visuals. |
| **hyperframes-studio** | Working with a person in HyperFrames Studio — when a message asks for a change at all, how a new film is planned and built, and timeline layout conventions with safe zones; the final gate runs through studio_project.py check. |
| **media-review** | Emergency OS-player fallback when the required HTML/browser review surface is unavailable. |
| **microdrama-story-formats** | Offer micro-drama story formats for the requested market and language; preserve custom structures, confirmed scripts and subtitle choices. |
| **microdrama-localize** | Orchestrates localizing a delivered episode to another language: register-preserving translation, subtitles, route choice (subtitles only, line-scoped re-voice, full regenerate), and approval, reconciliation and QA gates. |
| **microdrama-subtitles** | Writes per-language SRT/WebVTT sidecars from locked dialogue and measured timing, with CJK and right-to-left safe wrapping, reading-speed and cue-length limits, and episode offsets. |
| **micro-drama** | Produce source-led vertical micro-drama with optional templates, mode-aware review, native drafts, multilingual subtitles and Studio delivery. |
| **prompt-review** | Review BytePlus prompts in strict review_mode or for explicit review/required rules; default generation uses minimal inline preflight without full checklists. |
| **scene-board-sheet** | Derive a scene's storyboard record from its shot plan at L1, L2 (default) or L3, register generated and edited panels, plan panel-only repairs, and build annotated sheets, an animatic and a static review page. |
| **seed-audio-prompt** | Write structured Seed Audio 1.0 prompts for full-soundscape audio generation including dialogue, music, SFX, and ambience. |
| **seedance-acting-console** | Encode supplied performance plans as concise Seedance intent, trigger and response cues; preserve framing, restraint and dialogue locks. |
| **seedance-camera-presets** | Compose prompt-only camera moves and framing, including optical zoom, Dutch angle, dolly, orbit, FPV, whip pan, and single, two-shot, over-the-shoulder, point-of-view and insert framing. |
| **seedance-fight-choreography** | Plan fictional screen-fight beats with stable participants, readable reactions and prop continuity; prompt-only, with style explicitly selected and outcome locks preserved. |
| **seedance-lens-presets** | Translates a lens, focal length, aperture, focus or sensor request into a canonical visible-result phrase for Seedance prompts or Seedream style, and routes unreliable focus pulls and tape looks to post. |
| **seedance-lighting-presets** | Translates a named lighting setup (rim light, backlight, golden hour, night and moonlight, soft/hard light, three-point, Rembrandt, practicals, silhouette, contre-jour) into a Seedream `Lighting:` recipe and a matching Seedance phrase, and words timed light cues inside a shot. |
| **seedance-motion-recast** | Write Seedance 2.5 Motion Transfer prompts that keep a clip's motion, camera and cuts while rebuilding cast, wardrobe, product, location and style from locked references, with per-subject dispositions, Virtual Portrait identities, a muted source with post audio and a 480p probe ladder. |
| **seedance-object-swap** | Write Seedance 2.5 Object Swap prompts that replace one character, outfit, product, prop, object or location in existing footage and keep the rest of the shot, with the five-part swap contract, Virtual Portrait characters, a muted source with post audio and swap QA. |
| **seedance-pacing-presets** | Compose prompt-only rhythm, speed ramps, time-lapse, freeze frame, progressive part-by-part changes and named picture/audio transitions, including match cuts, dissolves, wipes and J/L cuts. |
| **seedance-prompt-20** | Legacy Seedance 2.0 prompt skill. Use when you need 4K output (unsupported by 2.5), Fast/Mini speed variants, or lower cost per generation. Provides reference-role classification, subject definitions, spatial continuity, shot sequencing, and native audio direction. |
| **seedance-prompt-25** | Write Seedance 2.5 prompts from shot plans and canonical elements, with native 480p drafts, approved promotion, language-aware dialogue and planning-only storyboards. |
| **seedance-prompt-25-dialogue** | Direct spoken dialogue for Seedance in any language: native-language check, register and accent, code-switching, and word-scoped repairs. |
| **seedance-prompt-25-filipino** | Opt-in Filipino dialogue support preserving approved words and requested language, register, code-switching and subtitle choices; separate accent notes, listening-based pronunciation review and opt-in separate lip-sync audio. |
| **seedance-restyle** | Write Seedance 2.5 Restyle prompts that redraw a whole clip in one of 24 visual styles or a custom style reference while keeping its content, motion, camera and cuts, with medium-matched Virtual Portrait anchors, an environment-image recipe that keeps the same place and restyles the background too, a muted source with post audio and a 480p probe ladder. |
| **seedance-shot-design** | Plan per-shot coverage for Seedance scenes: shot count and jobs, size, framing, angle, camera move, lens intent and light per shot, with variety rules and an energy level. |
| **seedance-virtual-portrait** | Prepares authorized face and voice references for Seedance Advanced Creation Rights, reuses completed onboarding and active assets without repeating verification, binds asset:// references, and resolves Seedance privacy and guardrail flags on real-person inputs through the registered asset route. |
| **seedream-character-outfit** | Writes Seedream image-to-image prompts that change the outfit on an approved character sheet, with always-worn accessories, a change contract, and identity-drift QA. |
| **seedream-character-sheet** | Writes structured Seedream prompts for three-panel character sheets and identity references. Produces the canonical character turnarounds that Seedance uses as face anchors. |
| **seedream-character-sheet-cleanup** | Cleans Seedream character sheets by removing the head from the full-body panels so only the close-up panel keeps a readable face. |
| **seedream-edit** | Guide for using the `seedream_edit_image` MCP tool for interactive image editing with Seedream 5.0 Pro. Use for point-based and bounding-box precision editing — replace objects, change regions, add elements at specific positions. |
| **seedream-location-asset** | Writes structured Seedream prompts for cinematic location assets and reusable environment sheets. Use for creating locations, interiors, exteriors, set references, or establishing stills. |
| **seedream-prompt** | Write Seedream prompts for synthesized or edited imagery while routing exact typography, pricing, CTA, product grids, logos, and pixel layouts to deterministic graphics. |
| **seedream-prop-asset** | Writes structured Seedream prompts for prop and product identity sheets after the prop threshold and acquisition-first check. Shows front and back views by default, adding a side view when the user asks or the object needs it. Use for held, recurring, story-critical, or scene-variant objects that Seedance must reproduce. |
| **seedream-storyboard** | Create, revise, and optionally generate production-ready cinematic storyboards—from one hero panel with alternatives to a multi-panel continuity sequence—with BytePlus Seedream. Boards are planning and review artifacts, never Seedance references. |
| **showcase-html** | Maintain the HTML production canvas of pre-Studio canvas projects and build ad-hoc comparison pages (optional for Studio projects). |
| **template-factory** | Native-first narrative reference recipes with permitted tool fallbacks; preserve selected units, script-led format and draft-ledger contracts. |
| **blocking-map** | Tigran's project-agnostic method for giving Seedance character DISPOSITION via a color-coded outline schematic — a "staging reference" (blocking map). |
| **scene-craft** | Apply the five-element dramatic engine when selected, preserving supplied scripts, alternative narrative structures and intended shot duration. |

## Setup

```bash
uv sync --locked
uv run python .agents/scripts/validate_workspace.py --offline
uv run python -m unittest discover -s tests -v
```

Credentials come from runtime configuration (`BYTEPLUS_MODELARK_API_KEY`); never commit `.env` files.
