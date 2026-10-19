# Shared Localization Protocol

This is the Phase 4 localization route from `PLAN_SEED_CINEMA_STUDIO.md`.
`production-localize` and retained `microdrama-localize` are explicit
orchestrators following this protocol. Neither invokes the other. The
[production policy](production-policy.md) retains lifecycle, rights, cost and
approval authority. Localization is not permission to rewrite source material.

## Inventory and Translation

Require the selected unit, delivered master/hash, locked source lines and
their timing, current canon, target language/variety/register, user locks and
budget. Preserve source scripts, manifests, dialogue, master, stems and earlier
renders. Record their hashes before work and recheck them after producing the
new version. Never write the target text over the source column or source file.

One translation-sheet row per source line:

| Field | Meaning |
| --- | --- |
| `line_id`, speaker, addressee | Stable IDs and relationship register |
| Source text and source path/hash | Exact locked source words |
| Target text, target language | Proposed or accepted translation |
| Register/glossary notes | Names, honorifics, formality, fixed terms, untranslated words |
| Measured source window | Start/end on the source edit, not prompt seconds |
| Fit and alternatives | Natural-speed fit; shorten wording rather than stretch speech |
| Text status | Draft or accepted with actual authorization |
| Cultural status | Unverified until a native speaker supplies evidence |

Translation acceptance and cultural verification are independent. A machine
translation can be accepted as text without certifying dialect, slang, taboo
terms or cultural suitability. Do not borrow a market from an example.
Preserve each scene's meaning and reveal placement, including quiet passages,
wordless work and the supplied ending. Only micro-drama inherits its existing
hook/turn/cliffhanger intent.

## Explicit Routes

| Record route | Audio | Picture | Lip-sync verdict |
| --- | --- | --- | --- |
| `subtitles` | Source unchanged | Source unchanged | `not_applicable` |
| `revoice` | Changed lines only, background soundtrack kept | Source picture/timing kept | `unverified` until inspected, then `approximate` |
| `regenerate` | Target speech on new clips | New version, new reviews | `unverified` until inspected, then `native` only if demonstrated |

Prefer the least-cost route that satisfies the confirmed requirement. Subtitles
need no new master render. Spoken audio or regenerated footage requires explicit
scope and budget, not an automatic fallback. The native-language check precedes
spoken generation; audio tools need their own verified capability evidence.
Unsupported languages remain experimental or use a confirmed fallback.

Re-voice must retain source music, effects and room tone. Use original audio
with a verified full-soundtrack video-conditioned tool when available, or
verified voice/background separation plus scoped new speech and mixing.
Do not infer a video-to-audio binding from text-to-audio support. Do not
replace the entire soundtrack with dialogue alone. Initial localization is
line-scoped; correction of one wrong word is word-scoped. Inspect pitch, tempo,
speaker identity and audible continuity against the actual source and intended
delivery. A fixed percentage from another production neither approves nor
rejects a patch; unavailable listening leaves it unresolved.

Regenerate uses current canon bindings, the existing production workflow,
inline prompt review, registered 480p drafts, inspected selections and
separately reviewed finals. Regeneration can change picture despite identical
references. Treat it as a new version with new picture, continuity, sound
and final decisions.

## Durable Execution and QA

The orchestrator sequences specialists; independent leaves never sequence each
other. Any generation-bound prompt receives inline review. Register prepared
operations before submission, persist acknowledged task IDs, and reconcile
timeouts from `task_ids.json`. Do not resubmit unknown paid operations through
another transport. Rights and authorized face/voice references remain required.
Track estimated, unknown and confirmed cost separately.

For each target version, record actual evidence or `unverified`:

- Locked-line transcript comparison, speaker/order and missing/extra words.
- Listening for pronunciation, accent, register, voice identity, cut tails,
  room tone, background preservation, peaks and loudness target.
- Actual picture/timing review. Subtitles/re-voice require unchanged picture;
  verify stream identity when possible and explain any remux/re-encode. A
  changed container hash alone says nothing about picture equality.
- Subtitle timing on the delivered version, warnings and real-player display,
  including RTL/mixed-direction languages.
- Full-cut continuity and ending for regenerate; no invented hook requirement
  for a general narrative.
- Native-speaker cultural evidence when available, otherwise unresolved.
- Honest route-specific lip-sync verdict, never inferred from tool success.

Audio/video decode and stream probes do not replace playback/listening.
Wordless work has no invented dialogue gate; audible ambience/music still
needs listening. Studio remains the supported assembly/review surface; no
new automatic import/reconcile path is introduced here.

## Preservation Record Version 1

Store `localization/<unit>/<language>/record-vNN.json` following
[localization.schema.json](schemas/localization.schema.json).

```json
{
  "schema_version": 1,
  "unit_id": "short",
  "target_language": "es",
  "route": "subtitles",
  "source_master": {"path": "deliveries/master-v01.mp4", "sha256": "<actual-sha256>"},
  "source_inputs": [
    {"path": "source/script.md", "sha256": "<actual-sha256>"},
    {"path": "subtitles/source-lines.json", "sha256": "<actual-sha256>"}
  ],
  "outputs": [{"path": "deliveries/master-v01.es.srt", "sha256": "<actual-sha256>"}],
  "lip_sync": {"verdict": "not_applicable", "evidence": []},
  "cultural_review": {"status": "unverified", "evidence": [], "note": "Native review unavailable."}
}
```

Replace illustrative hashes with real values. List every preserved source
input and every completed output. Planning may record the inventory separately;
this completed-file validator requires outputs to exist. Source hashes must be
the pre-work hashes, not refreshed after an unauthorized source edit.

The read-only `validate_localization` interface is documented in
[production-post.md](production-post.md). It checks current hashes,
containment, unit matching when supplied, output/source aliasing (including
hardlinks), and route/verdict consistency. Both `native` and `approximate`
require a current playback evidence reference; cultural pass/fail requires evidence. It does not validate
translation coverage, native-speaker identity, evidence truth, streams or
approval authority. It cannot detect an omitted source file or a falsely
rebaselined source hash. Main must bind the inventory to its trusted source
decision/render before treating preservation as a delivery gate.

Retain all old skill/script/reference paths. There was no legacy localization
executable to replace; the shared implementation is this protocol and the new
read-only validator. Subtitle commands call one engine through the documented
[subtitle compatibility route](subtitle-sidecars.md).
