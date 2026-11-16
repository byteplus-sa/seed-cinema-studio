# Scene Action

Focused reference for `seedance-prompt`. Read [the entrypoint](../SKILL.md) for
mode selection and caller responsibilities.

- [Scene staging](#scene-staging)
- [Action description](#action-description)
- [Counts, hands and surfaces](#counts-hands-and-surfaces)
- [Progressive change](#progressive-change)

## Scene staging

Use consecutive stages when they clarify the story. A shot or stage may contain
several readable ordered actions or reveals, or a sustained state. Describe the
critical action, its causal order and the perceptual outcome; do not split an
exchange merely to give every event its own stage. Deliberate stillness, waiting
and listening may end unchanged. Preserve the requested rhythm and reveal timing.

A clip that cuts uses shots rather than stages; see
[Shot Staging](shot-staging.md). Stages suit a continuous take or a story that
changes state without changing camera setup.

**Preserve each scene's natural duration and requested rhythm.**
Keep creative timing separate from verified duration controls. Do not pad a
scene to fill a model limit or shorten a locked source to fit a recipe.
The caller may propose chaining approved scenes via supported `return_last_frame` /
`first_frame` roles and assembly, with authorization for additional clips.
Add a shared reference bundle only when
the selected live tool/model explicitly supports mixed frame/reference roles;
a chaining recipe never overrides input compatibility.

```
[Generation Goal]
Generate a <video type>. The central subject is <subject>, and the primary event is <story summary>.

[Stage 1]
Initial state: <initial state of characters, props, and scene>.
Action: <critical ordered actions, reveal, or sustained state>.
Camera and light: <size, angle, move, and light source for this stage>.
End state: <character positions, prop ownership, or visible scene state>.

[Stage 2]
Continue from the previous stage: <state that must remain unchanged>.
Action: <critical ordered actions, reveal, or sustained state>.
Camera and light: <size, angle, move, and light source for this stage>.
End state: <observable state>.

[Stage 3]
Primary event: <closing event>.
Camera and light: <size, angle, move, and light source for this stage>.
End state: <final visible state>.

[Maintain Consistency]
Keep <character identity, number of characters, clothing, prop ownership, spatial direction,
and audio relationships> consistent.
```

### Continuous takes and extension

Choose a continuous take, staged sequence or extension from the brief, not a
fixed duration recipe. Verify exact-model and operation limits independently.
Possible creative reasons for a supported longer take or extension include:

- **Single continuous take** — a one-shot with no cuts where seamless motion
  across 30s+ matters more than per-scene iteration control.
- **Minimal scene variation** — same location, same characters, gradual change
  that the model handles well in one pass.
- **Audio-driven long dialogue** — preserve requested continuous delivery
  across scene boundaries; verify actual synchronization rather than promise it.

For a selected extension, follow [Video Extension](video-extension.md).
Preserve the supplied source and boundary state. Additional base clips or
extension rounds need their own authorization; do not manufacture scene changes
at a fixed timestamp.

- **Audio with extension (only when separate lip-sync audio is requested).**
  Preserve the exact supplied or separately authorized audio master and its
  full timeline. Bind it only when the selected operation supports that role;
  this writing leaf does not generate a track or guarantee synchronization.
- **Validate seams.** Extension boundaries are not pixel-identical; inspect the
  boundary image, motion trend, and audio continuity on both sides of each seam.
  Validate every authorized extension boundary before selecting it.
- **Aspect ratio** follows verified operation constraints, preserving source intent.

### Timestamps and pacing

Use stages by default for a continuous take, and shots when the clip cuts (see
[Shot Staging](shot-staging.md)). Use precise timestamps only for critical handoffs,
entrances/exits, transitions or explicit beats. Preserve supplied fractional
timing; one-second examples are not a rounding rule.

| Pattern | Example |
|---|---|
| Time range | `0-3 seconds... 3-7 seconds... 7-12 seconds...` |
| Exact time point | `At 5 seconds, the camera whip-pans rapidly to the left.` |
| Relative timing | `Three seconds after the character presses the button, the lights dim.` |

Rules:
- Time ranges must be **consecutive and non-overlapping**.
- They are a **time budget**, not a precise edit point — actions may occur slightly before or after a boundary.
- Too little content gives the model too much freedom; too much causes excessive cutting or omitted events.
- Density estimates are provisional, not action-count quotas. Judge readability
  at the requested speed; flag demonstrated lost critical action or timing
  conflicts, not the number of actions alone. Preserve approved action and
  timing; return conflicts for authorization rather than automatically slowing,
  splitting or adding holds.

## Action description

The Subject and Action slots identify who or what matters and what the audience
must perceive. Describe critical action or sustained attention concretely; leave
incidental execution open. "She enters the lab" may be sufficient when entry is
all that matters. Specify the hand, contact or gaze when it carries the beat.

- **Relevant physical detail.** Name body parts, range, speed or force only
  when needed to communicate the critical action.
- **Physics grounding.** Clarify weight, balance, contact, momentum and recovery
  where they determine continuity or feasibility, not as an exhaustive checklist.
- **Body energy follows approved intent and action.** Set speed, amplitude,
  interruptions and recovery from the performance plan, not a slow or gentle
  default. Stillness, urgent reaching, repeated attempts and abrupt withdrawal
  are all available. Ground each in balance, contact and momentum.
- **Separate actor energy, camera energy and edit rhythm.** Speech does not
  automatically lower any of them; preserve the required readable evidence.
  Slow motion or a single burst bracketed by holds is an optional repair for
  a demonstrated failure, not a universal burst limit. Identify the failed
  moment and preserve source action and timing; return conflicts to the caller.
- **Describe transitions between actions** for continuity: "use the inertia of
  turning around to naturally raise a hand."
- **Externalize emotions as physical detail**, never bare emotion labels. Use
  the [Emotional direction](audio-performance-camera.md#emotional-direction) cues below.
- **Stay inside the stage budget.** Preserve readable ordered actions and
  sustained attention; return concrete timing conflicts rather than imposing
  a per-stage event count.

### Selective motion grammar

When intended movement is underspecified, use the relevant motion grammar
below for subjects, props, effects, light or background. Describe only the
axes needed for readability; intentional stillness needs no invented motion,
loop or light change. A missing motion term alone does not prove a failed take:

| Axis | Question to answer |
|---|---|
| **Motion type** | translate / rotate / scale / parallax / drift / float-bob / pulse / flicker / color-cycle / twinkle / shimmer / sway / wave / slide / zoom / rotation |
| **Direction** | up/down, left/right, toward/away, clockwise/counterclockwise, along what axis |
| **Speed** | slow / medium / fast, or a frequency (e.g. "~0.5Hz sway") |
| **Amplitude** | how far ("~5% of body height", "full spectrum cycle") |
| **Easing** | constant / sinusoidal / accelerating / smooth |
| **Loop period** | only for intended repetition; how often it repeats ("~2s per cycle") |

Separate subject motion from the planned camera path or hold. Specify light or
color motion and its rate only when the effect needs it. An organic one-off
movement needs no easing curve, numeric amplitude or loop period.

Optional repeating-effect example: instead of "the neon figure floats, a rainbow beam shines from its
head", write "the featureless neon figure floats with a gentle up-down bob
(~0.5Hz sine, ~5% of body height) in a leaning pose, while a fan-shaped rainbow
beam projects from its head with the color bands continuously scrolling along
the beam (~1s full-spectrum cycle) and the background stars twinkle randomly."

## Counts, hands and surfaces

These three failures recur across takes and are cheap to prevent in text.

**Counts** (`prompt.exact_counts`). Track total identity separately from the
visible count. Name counted items by identity, size or position; account for
hidden, off-screen, entering, exiting and occluded subjects where relevant.
Restate counts and positions after relevant changes, without requiring all
subjects in frame one. Preserve deliberate reveals. Flag contradictory totals,
unexplained duplication or incompatible positions, not concealment itself.

```text
Three ceramic cups stand in a row on the counter from the first frame: small at
frame-left, medium in the center, large at frame-right. She lifts only the
medium cup; the small and large cups stay where they are. Three cups in total
throughout.
```

For a reveal: three people total; two visible at the table, the third hidden
behind the closed door until it opens. The same third person enters, making
three visible; the reveal does not create a fourth identity.

**Hands** (`prompt.hand_frame_side`). The model reads left and right as the
character's own side, so a bare "left hand" is often mirrored. Name anatomy and
frame side together: "her right hand, frame-left". When the character faces
away from the camera the two sides agree; say so anyway.

**Surfaces** (`video.text_free`). Generic tubes, jars, jugs, hard-shell cases,
garment neck labels, tickets and generated screens grow invented lettering.
Describe a recurring non-sheet prop positively as plain ("a plain white ceramic
jug, smooth solid surface, nothing printed"), leave it out, or give a story prop
a reference sheet with its real markings. Exact copy is a post layer.

## Progressive change

A change that spreads across the body or frame over time (an outfit changing
only on the part of the body that has crossed a line) is staged by timestamp
and body part in a pure reference-to-video prompt, never as an instant swap or
an image-edited first frame. The working recipe and the wordings that failed
live in `seedance-pacing-presets` (Progressive change); compose with it.
