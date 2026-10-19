# Restyle QA

Focused reference for `seedance-restyle`. Read [the entrypoint](../SKILL.md)
for routing and caller responsibilities.

- [Picture checks](#picture-checks)
- [Audio checks after mux](#audio-checks-after-mux)
- [Failures and repairs](#failures-and-repairs)

## Picture checks

Play the silent output at full speed, then step through it beside the source.
Record each item as pass, fail or not applicable.

- **Medium coverage.** Every person, prop, surface, sky and effect is in the
  style. No photographic patches, especially faces, hands and backgrounds.
- **Style stability.** Line weight, texture scale and palette hold across the
  clip and across cuts; no frame-to-frame crawl beyond the style's intended
  boil.
- **Content kept.** Subject count, screen positions, actions, key props and set
  layout match the content inventory.
- **Identity cues.** Each person keeps hair shape, wardrobe colours and
  silhouette on every appearance; anchored characters match their Virtual
  Portrait.
- **Motion and timing.** Poses at each beat, contacts, camera path and cut times
  match the source. Stepped styles still hit beat poses.
- **No lettering.** No generated text, logos or signage copy; source text
  surfaces show abstract shapes.
- **Same place.** The background reads as the source's own place in the new
  medium; no different city, landscape or interior has been substituted.
- **Reference authority.** An environment image is optional. When selected,
  it supplies same-place surfaces, palette and texture, not geometry, layout,
  camera parallax or timing. Reject conflicting references and omit absent
  image roles; words-only requests still cover the whole frame.
- **Technical.** Clean decode, no audio stream. On both routes, measure decoded
  timestamps, duration, playback speed and cut boundaries against the full
  source or specifically approved span. Neither 8n+1 nor whole-second settings
  guarantee exact timing, and no blanket tolerance establishes a pass. Report
  mismatches; any trim, padding, rounding or retiming requires current capability
  evidence, specific user approval and a separate derivative record with source
  span, hashes and audio consequences. Check for new black side bars.

Follow Cinema's draft and promotion policy using current route capabilities.
An unsupported native Draft or promotion capability stays open for an approved
alternative. Propose a short probe only for a current inspected difficulty with
approval of its span; old probes neither gate a new case nor prove another
medium's limitations.

## Audio checks after mux

Apply after the post-audio route is muxed, following the
[video-to-video inputs contract](../../../contracts/video-to-video-inputs.md#post-audio).

- Measure picture and audio before muxing; do not hide a mismatch with padding
  or `-shortest`. Any corrective padding, trim or retiming needs specific user
  approval and a recorded derivative. Muted picture and saved audio derive
  from the same selected source span.
- Two or three sync points land on the picture.
- On-screen speech stays on the redrawn mouths. Simplified mouths in drawn
  styles tolerate less precision; a visible offset still routes to the
  re-voiced route or a new take.

## Failures and repairs

Change one variable per retry: wording, style reference, anchor or route.

| Symptom | Likely cause | Repair |
| --- | --- | --- |
| Output stays photographic | Medium instructions were not realized in this result | Name the failed surfaces and repair wording or try a currently supported alternative route; do not infer universal route limitations |
| Subject redrawn but street, plant, table and sky stay photographic | Background medium coverage failed in the current result | Name those surfaces in a scoped wording repair or try a supported route; honor words-only scope. An approved same-place image remains optional, not an automatic generation step |
| The scene moved to a different place (city became sea), or layout changed | Prompt or selected reference conflicts with source place or geometry | Reject the conflicting reference, restore source authority and use words-only guidance or an approved corrected same-place image |
| Extra chair, ashtray or cup appears | The environment image holds objects the shot lacks | Name each in the Environment Reference Role as not to be used; remove them from the image |
| Hair or face colour changes toward a style frame | A style frame carries a different look | Say the source owns identity and keep hair colour in the scope; prefer an environment image to person-bearing frames |
| Faces stay photographic inside a drawn world | Face protection or photoreal anchor | Remove photoreal wording; use a medium-matched anchor |
| Layout or subjects change | Style image read as content | Use a style image with different content, or drop it |
| Style drifts between cuts | Fragment too long or conflicting | Shorten to the medium lock; one style only |
| Extra people or props appear | Count not stated | State per-cut counts in the scope |
| Lettering appears on signs | Text surfaces not given a disposition | State abstract shapes for each text surface |
| Stepped cadence misses key poses | Stop-motion timing over fast action | Add the cadence note and name the beat poses |
