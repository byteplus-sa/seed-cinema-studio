# seed-microdrama-studio

Skills, contracts and tooling for making vertical micro-dramas with BytePlus Seedream, Seedance and Seed Audio. It supports any market, language and genre (romance, hidden heir, revenge, family conflict, thriller, horror, comedy, historical and more). The story-to-delivery pipeline was proven end to end on a first series for the Filipino market (the reference market pack): brief, cast and location canon, blocking maps, Seedance 2.5 shot prompts, review, a HyperFrames Studio timeline, and per-episode export for TikTok.

Status: the skills, contracts, scripts and tests started as copies from `byteplus-sa/ark-director` and now carry the lessons from the first series. The target market is always chosen by the user (an optional market card in the `micro-drama` skill); no market is built in or assumed.

## Markets and languages

| Need | Skill |
| --- | --- |
| Stories for any market, language or genre | `microdrama-story-formats` |
| Spoken dialogue in any language, with a native-language check | `seedance-prompt-25-dialogue` |
| Filipino market pack (reference example) | `filipino-micro-drama` and `seedance-prompt-25-filipino` |
| Add a new market pack | [docs/ADD_A_MARKET.md](docs/ADD_A_MARKET.md) |

Seedance 2.5 speaks Chinese, English, Spanish, Indonesian, Malay, Thai, Arabic, Portuguese, Vietnamese, Japanese and Korean natively; other languages need an annotation, subtitle or audio-first route, which the dialogue skill records.

## Layout

| Path | Contents |
| --- | --- |
| `.agents/skills/` | The micro-drama skills, one folder per skill |
| `.agents/contracts/` | Production, routing, identity and naming contracts the skills cite |
| `.agents/scripts/` | Request preparation, task registry, catalog sync, validation and `studio_project.py` (HyperFrames Studio bridge) |
| `docs/` | How to add a market |
| `projects/<series>/` | Local, uncommitted: one folder per series, with its own Studio project |
| `tests/` | Studio, registry, approval and validation tests |

## Skills

Copied from `byteplus-sa/ark-director`; edit them only under `.agents/skills/`.

| Skill | Summary |
|---|---|
| **ark-mcp** | Uses the Ark multimodal MCP server for image, video, audio and 3D workflows, durable artifacts, and Advanced Creation Rights face/voice assets with existing authorization reuse and privacy rejection triage. |
| **brief-intake** | Shape intent-led briefs and treatments; hand off brand-ad / footage inspiration for watchable-media analysis; preserve confirmed decisions. |
| **color-grade-palettes** | Maps a named color grade palette or film look (teal & orange, bleach bypass, golden hour warm grade, etc.) into a canonical grade sentence for the Seedance Visual Style slot or the Seedream `Style:` section, with an optional matching FFmpeg filter graph for cross-shot matching. |
| **ffmpeg** | Video and audio processing with FFmpeg. Use for format conversion, resizing, compression, audio extraction, and preparing assets for editing and assembly. Covers converting GIF to MP4, resizing video, extracting audio, compressing files, and any media transformation task. |
| **filipino-micro-drama** | Write Filipino-market micro-drama stories: proven Pinoy formulas, locked episode briefs with English-dominant Taglish dialogue, honorifics, authentic settings and subtitle translations. |
| **film-production** | Orchestrates multi-scene, multi-modality production one stage at a time while keeping one HyperFrames Studio project synchronized for review and handoff. |
| **html-graphic-render** | Author and render exact-size static posters, cards, product grids, UI, and transparent overlays from one project-local HTML entrypoint with CSS/SVG dependencies, exact-copy checks, and schema-valid provenance. |
| **hyperframes** | Mandatory HyperFrames entry point — resumes project state, selects the owning workflow (nothing is installed), and routes all video, animation, and motion-graphic capabilities. |
| **hyperframes-animation** | Atomic motion rules, multi-phase scene blueprints, transitions, and the seven runtime adapters (GSAP, Lottie, Three.js, Anime.js, CSS, WAAPI, TypeGPU). |
| **hyperframes-audio** | Mixing audio already placed in a composition — fades, crossfades, ducking, effect chains, automation envelopes, and submix buses. |
| **hyperframes-cli** | HyperFrames CLI development loop — init, add, catalog, capture, lint, check, snapshot, and render workflows, run through the pinned workspace entry. |
| **hyperframes-core** | Composition contract for renderable HTML video — timing data-attributes, clips, tracks, sub-compositions, variables, determinism rules, and validation. |
| **hyperframes-creative** | Non-animation creative direction — design specs, palettes, typography, narration, beat planning, audio-reactive visuals, and brand style. |
| **hyperframes-keyframes** | Seek-safe 2D/3D keyframes — punch-ins, camera moves, Ken Burns, match-cut handoffs, masks, SVG morph/draw, and runtime-specific APIs. |
| **hyperframes-registry** | Search, install, and wire hosted registry blocks and components into compositions before hand-building named visuals. |
| **hyperframes-studio** | Working with a person in HyperFrames Studio — when a message asks for a change at all, how a new film is planned and built, and timeline layout conventions with safe zones; the final gate runs through studio_project.py check. |
| **media-review** | Emergency OS-player fallback when the required HTML/browser review surface is unavailable. |
| **microdrama-story-formats** | Write micro-drama stories and episode briefs for any market, language or genre: proven formats, light casts, culturally grounded settings, locked dialogue and subtitle translations. |
| **microdrama-localize** | Orchestrates localizing a delivered episode to another language: register-preserving translation, subtitles, route choice (subtitles only, line-scoped re-voice, full regenerate), and approval, reconciliation and QA gates. |
| **microdrama-subtitles** | Writes per-language SRT/WebVTT sidecars from locked dialogue and measured timing, with CJK and right-to-left safe wrapping, reading-speed and cue-length limits, and episode offsets. |
| **micro-drama** | Produce vertical micro-drama episodes end to end for any market: hook, reveal and cliffhanger clips with text-free storyboard conditioning, dialogue-accuracy QA, loudness-matched delivery and a full-episode showreel. |
| **prompt-review** | Review and fix BytePlus Seedance, Seed Audio, and Seedream prompts against the repo's best practices inline by default; use a sub-agent only when explicitly requested for a project or specific generation. |
| **seed-audio-prompt** | Write structured Seed Audio 1.0 prompts for full-soundscape audio generation including dialogue, music, SFX, and ambience. |
| **seedance-acting-console** | Turn playable motives and tactics into observable acting cues appropriate to framing, visibility and intensity. |
| **seedance-camera-presets** | Compose prompt-only camera moves and framing, including optical zoom, Dutch angle, dolly, orbit, FPV, rack focus and whip pan. |
| **seedance-lens-presets** | Translates a lens, focal length, aperture, or sensor request into a canonical visible-result phrase for Seedance prompts or Seedream style. Covers 35mm, 50mm, 85mm, wide angle, telephoto, anamorphic, fisheye, macro, f-stop, depth of field, bokeh. |
| **seedance-lighting-presets** | Translates a named lighting setup (rim light, backlight, golden hour, soft/hard light, three-point, Rembrandt, practical lights, silhouette, contre-jour) into a canonical Seedream `Lighting:` recipe and a matching Seedance visual-style lighting phrase. Ensures the same lighting intent works for both images and video. |
| **seedance-motion-recast** | Write Seedance 2.5 Motion Transfer prompts that keep a clip's motion, camera and cuts while rebuilding cast, wardrobe, product, location and style from locked references, with per-subject dispositions, Virtual Portrait identities, a muted source with post audio and a 480p probe ladder. |
| **seedance-object-swap** | Write Seedance 2.5 Object Swap prompts that replace one character, outfit, product, prop, object or location in existing footage and keep the rest of the shot, with the five-part swap contract, Virtual Portrait characters, a muted source with post audio and swap QA. |
| **seedance-pacing-presets** | Compose prompt-only rhythm, time-lapse, freeze frame and named picture/audio transitions, including match cuts, dissolves, wipes and J/L cuts. |
| **seedance-prompt-20** | Legacy Seedance 2.0 prompt skill. Use when you need 4K output (unsupported by 2.5), Fast/Mini speed variants, or lower cost per generation. Provides reference-role classification, subject definitions, spatial continuity, shot sequencing, and native audio direction. |
| **seedance-prompt-25** | Write production-grade Seedance 2.5 video prompts with the flexible six-part formula, 50-material multimodal referencing, variable-duration scene staging (4-30s), timestamp pacing, structured video editing (subject replacement, background replacement, audio editing), forward and backward video extension, keyframe sequences, storyboard grids,. |
| **seedance-prompt-25-dialogue** | Direct spoken dialogue for Seedance in any language: native-language check, register and accent, code-switching, and word-scoped repairs. |
| **seedance-prompt-25-filipino** | Write Filipino and Taglish dialogue direction while preserving exact words and register; use evidence-based pronunciation hypotheses and opt-in separate lip-sync audio. |
| **seedance-restyle** | Write Seedance 2.5 Restyle prompts that redraw a whole clip in one of 24 visual styles or a custom style reference while keeping its content, motion, camera and cuts, with medium-matched Virtual Portrait anchors, an environment-image recipe that keeps the same place and restyles the background too, a muted source with post audio and a 480p probe ladder. |
| **seedance-shot-design** | Plan per-shot coverage for Seedance scenes: shot count and jobs, size, angle, camera move, lens intent and light per shot, with variety rules and an energy level. |
| **seedance-virtual-portrait** | Prepares authorized face and voice references for Seedance Advanced Creation Rights, reuses completed onboarding and active assets without repeating verification, binds asset:// references, and resolves Seedance privacy and guardrail flags on real-person inputs through the registered asset route. |
| **seedream-character-outfit** | Writes Seedream image-to-image prompts that change the outfit on an approved character sheet, with always-worn accessories, a change contract, and identity-drift QA. |
| **seedream-character-sheet** | Writes structured Seedream prompts for three-panel character sheets and identity references. Produces the canonical character turnarounds that Seedance uses as face anchors. |
| **seedream-character-sheet-cleanup** | Cleans Seedream character sheets by removing the head from the full-body panels so only the close-up panel keeps a readable face. |
| **seedream-edit** | Guide for using the `seedream_edit_image` MCP tool for interactive image editing with Seedream 5.0 Pro. Use for point-based and bounding-box precision editing — replace objects, change regions, add elements at specific positions. |
| **seedream-location-asset** | Writes structured Seedream prompts for cinematic location assets and reusable environment sheets. Use for creating locations, interiors, exteriors, set references, or establishing stills. |
| **seedream-prompt** | Write Seedream prompts for synthesized or edited imagery while routing exact typography, pricing, CTA, product grids, logos, and pixel layouts to deterministic graphics. |
| **seedream-prop-asset** | Writes structured Seedream prompts for prop and product identity sheets after the prop threshold and acquisition-first check. Shows front and back views by default, adding a side view when the user asks or the object needs it. Use for held, recurring, story-critical, or scene-variant objects that Seedance must reproduce. |
| **seedream-storyboard** | Create, revise, and optionally generate production-ready cinematic storyboards—from one hero panel with alternatives to a multi-panel continuity sequence—with BytePlus Seedream. |
| **showcase-html** | Maintain the HTML production canvas of pre-Studio canvas projects and build ad-hoc comparison pages (optional for Studio projects). |
| **template-factory** | Reverse-engineer a reference video and soundtrack into a timed visual and audio recipe, with reviewable assets and shot takes reviewed in a synchronized Studio project. |
| **tig-blocking-map** | Tigran's project-agnostic method for giving Seedance character DISPOSITION via a color-coded outline schematic — a "staging reference" (blocking map). |
| **tig-scene-engine** | Writes and audits screenplay scenes and sequences using a five-element dramatic engine — Goal, Obstacle, Tactic, Reversal, Value Shift — with custom definitions. Use to write new scenes, draft options, develop sequences, or audit/test/diagnose existing scenes for structural strength. Default scene-craft skill for thriller and psychological drama. |

## Setup

```bash
uv sync --locked
uv run python .agents/scripts/validate_workspace.py --offline
uv run python -m unittest discover -s tests -v
```

Credentials come from runtime configuration (`BYTEPLUS_MODELARK_API_KEY`); never commit `.env` files.
