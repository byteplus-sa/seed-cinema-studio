# Prompt Patterns

These are authoring patterns, not tested Seedance outputs. Use only after the
required approved image and authorized vocal recording are available, with
caller-supplied inspection evidence. Do not emit unresolved placeholders as
submission-ready text.

## Split-panel animated sheet

Use this pattern when the two-panel layout is selected. Image numbers reflect
the actual transport: one supported approved sheet input, or separate approved
views when the rights route requires them. Explicitly assign every bound view.

```text
Task: Create an animated identity-and-detail reference of <character>,
preserving the approved <medium>.

References:
<Map each @Image N to the face, body, costume or detail of the same character.>
These images define one character's exact appearance, not separate people.
@Audio 1 supplies <character>'s authorized vocal performance from the approved
excerpt: preserve its exact words, language, voice, accent, pacing, pauses
and delivery. Only this character speaks.

Layout and light:
Two fixed side-by-side panels. The right panel continuously
shows <character>'s readable face in a close-up, near frontal to slight
three-quarter view. The left panel shows the body and detail sequence below.
Both panels depict the same character and matching approved wardrobe.
Plain neutral studio background, soft even studio light, stable exposure.

Right panel, 0-<end>s:
Keep the face visible and in focus throughout. Small natural head adjustment,
natural blink and quiet breath where compatible with the supplied performance.
Mouth and jaw follow @Audio 1; no exaggerated acting or unrelated gestures.
The camera stays locked with no cuts or orbit in this panel.

Left panel:
<start>-<end>s: Full-body view, <supported modest turn or held pose>.
<start>-<end>s: Cut to <approved costume/material detail>.
<start>-<end>s: Cut to <approved face/ear detail>.
<start>-<end>s: Cut to <approved hand/accessory detail>.
<start>-<end>s: Cut to <approved footwear detail>.
Each camera is fixed during its hold. Cuts affect only the left panel.

Audio:
At <speech window>, <character> performs @Audio 1 in <verified language>:
{<exact approved transcript>}
Keep the supplied vocal performance continuous across the left-panel cuts.
No extra words, second voice, background music or added vocal effects.

Continuity:
Preserve <source-supported identity, outfit and permanent accessory locks>
across every view. No outfit changes, added props, labels or on-screen text.
```

Choose fewer inserts when required to keep details readable, but ask before
dropping locked coverage. A full-body turn is not a camera orbit. A rear view
requires approved rear design evidence, not a guess from a coat's front.

## Continuous reference

Keep the same explicit image mappings, audio binding, exact dialogue and
source-supported appearance locks. Replace the split-panel layout and detail
sequence with:

```text
One continuous <approved framing> view of one character against a plain
neutral studio background, stable soft light and fixed camera. Keep the face
readable throughout. A small natural head turn, blink and breath accompany
the supplied vocal performance. Mouth movement follows @Audio 1.
No split screen, internal cuts, orbit, outfit changes or on-screen text.
```

## Handoff cautions

Keep total duration, aspect ratio, resolution and API settings in the request
handoff, outside the creative prompt; retain event timestamps for synchronization.
Resolve duration against
the measured audio excerpt and the selected model/route's current limits.
Do not treat a clip labeled "10 seconds" as exactly 10.000 seconds or assume
several such clips fit a future reference-duration limit.

For downstream identity-only reuse, specify allowed temporal appearance
attributes and exclude the sheet's panels, detail edits, background, turn,
gestures and dialogue unless explicitly wanted. This is proposed reference
semantics, not provider-validated video identity support. Voice reuse requires
its own authorized audio role; do not assume a video soundtrack supplies it.
