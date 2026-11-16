# Audio Performance Camera

Focused reference for `seedance-prompt`. Read [the entrypoint](../SKILL.md) for
mode selection and caller responsibilities.

- [Special audio and text syntax](#special-audio-and-text-syntax)
- [Choosing the audio route](#choosing-the-audio-route)
- [Emotional direction](#emotional-direction)
- [Scripted dialogue for all speaking characters](#scripted-dialogue-for-all-speaking-characters)
- [Describing screen and UI layout positively](#describing-screen-and-ui-layout-positively)
- [Camera language](#camera-language)
- [Video call scenes](#video-call-scenes)
- [Spatial continuity](#spatial-continuity)

## Special audio and text syntax

The following 2.5 guide conventions are authoring examples. Verify special
tokens, audio controls, language and reference support for the exact model,
operation and destination; natural-language direction remains useful when
syntax is unresolved.

| Content | Syntax | Example |
|---|---|---|
| **Music** | `()` | `(Soft, rhythmic piano music plays in the background)` |
| **Sound Effects** | `<>` | `<A bell rings in the distance>` |
| **Dialogue** | `{}` | `{Hello, welcome back.}` |
| **Subtitles** | `【】` | Provider syntax only: workspace footage stays text-free, so titles and subtitles are added in post (`video.text_free`) |

### Dialogue language reinforcement

Specify the requested language before the line; do not infer a default language:

```
The girl says softly in Japanese: {もう大丈夫です}
```

For regional accents or to prevent language mixing:

> **Dialogue Language + Regional Variety or Accent + Delivery Style + Speaker + {Dialogue}**

```
Dialogue language: American English. The girl says in natural, conversational American English: {I thought you weren't coming.}

Dialogue language: authentic Los Angeles English. The young man says in natural Los Angeles vernacular: {No way, you actually made it.}
```

### Unsupported languages and pronunciation guidance

The historical 2.5 guide listed Chinese, English, Spanish, Indonesian, Malay,
Thai, Arabic, Portuguese, Vietnamese, Japanese and Korean. Do not infer support
or incapability for an exact model from this list, a family name or a missing
entry. Preserve the requested language and approved words. Pronunciation notes
are hypotheses, not guarantees; a language change or separate audio-first
pipeline requires explicit scope and verified reference support.

For any dialogue language, the caller may compose the independent partner skill
`seedance-prompt-25-dialogue` for the language-support verdict, register,
accent and repair rules. When an installed market dialogue pack covers the
language (for example `seedance-prompt-25-filipino`), the caller may select it for
its pronunciation, intonation and audio-first guidance.

### Direct audio controls

```
No background music. Keep only the characters' dialogue, ambience, and action sound effects.
```

A control line like this is a request, not a switch. Pick the route below
before relying on it.

## Choosing the audio route

Resolve sound ownership from the brief before choosing `generate_audio`
(`audio.native_route`). Wordless does not mean picture-only. Native audio can
add unwanted speech, chants or music; negative wording is not a guarantee.

| Sound ownership | Route |
|---|---|
| Requested native dialogue, lip-sync, diegetic action or ambience, including wordless scenes | Native audio (`generate_audio: true` where supported); specify wanted voices/effects, synchronization and exclusions |
| Exact supplied master or controlled post soundtrack | Preserve the master unchanged; use picture-only generation where supported and place the approved master/bed in post |
| Purposeful silence | Disable native audio where supported; otherwise arrange authorized removal in post and verify silence; do not add a bed |
| Ownership unspecified or contradictory | Ask a focused question; keep the route unresolved rather than infer it from absent dialogue |

For mixed ownership, name which layers are native and which are post. Preserve
an approved provider master; additions require authorization. Separate lip-sync
audio remains opt-in. Confirm live model/mode support for switches and reference
roles; if the chosen route is unsupported, return the conflict before submission.
Keep rights, consent and source approvals unchanged.

Describe critical native contact sounds in `<>`, for example
`<the latch clicks as the door closes>`. Exclude unwanted voices and score, then
verify through playback and listening. If unwanted audio remains, reject the take
or propose an authorized repair; do not silently discard requested native sound.

Record that a post bed is not frame-synced, so hits that must land on an action
are placed in assembly. Re-check audio on a promoted final: do not assume it is
byte-identical to the draft's soundtrack. Exact masters must not be regenerated.

## Emotional direction

For character-performance scenes, consume the caller's `acting-direction`
plan and `seedance-acting-console` encoding. Carry each relevant beat's
pursuit, trigger, registration and response once. Give relevant listeners
a task or intentional non-response. Do not invoke those leaves yourself.
Missing material performance input is a handoff gap, not permission to choose
gestures from a mood label. Isolated cue studies remain provisional.

Visible or audible cues are consequences of the supplied tactic and must fit
the camera side, subject size, occlusion and speaking window. A subtle cue
that the frame cannot show is not evidence of an emotional beat.

> For a single emotional transition, **2–4 clear cues** are usually enough.
> This is an optional cue budget, not a quality gate or a mandatory minimum.
> Sustained attention, silence and restraint can carry the whole shot.

### Single emotional transition

```
The overall emotion shifts from <starting emotion> to <ending emotion>.
After <triggering event>, <subject> first shows <immediate observable reaction>.
Then, <eyes, brows, mouth, breathing, gaze, or hand movement> gradually <changes>.
Finally, <subject> expresses <target emotion> through <restrained or explicit outward behavior>.
```

### Multi-stage emotion

```
When <subject> hears or sees <first triggering event>, <first observable reaction>.
When <second triggering event> occurs, <change in expression, gaze, or breathing>.
After confirming <critical information>, the emotion that <subject> tries to restrain or conceal
gradually becomes visible through <observable behavior>.
Finally, <subject's final action, expression, or manner of speaking>.
```

### Tactic-first encoding example

Hypothetical supplied intent: B delays A's departure by keeping a shared
task unfinished. After A picks up a bag, B offers the remaining cloth corner
and says the locked line. A's supplied response follows. Preserve the held
two-shot and leave time to read that response.

This gives the model an event and a responsive attempt, not an arbitrary
"sad eyes, trembling lips" routine. It predicts readability, not a verified
generation improvement. Use the transition templates only when the selected
performance actually changes; do not manufacture an emotion arc.

## Scripted dialogue for all speaking characters

Budget every line for time; see
[Dialogue inside shots](shot-staging.md#dialogue-inside-shots).

Every character who speaks in the video — including background characters,
people on phone screens, voiceover narrators, and characters with a single line
— must have explicit scripted dialogue using the `Dialogue language` prefix.
Characters without scripted lines may produce unwanted speech. Exact scripted
words are intended output, not a fidelity guarantee; verify them by listening.

```text
Dialogue language: English. <Character> says in natural <accent> English: {exact line here}
```

This applies to:
- Main on-camera characters
- Characters visible only through phone/laptop screens during video calls
- Voiceover narrators (use "voiceover narration" after the accent qualifier)
- Characters with a single word or short phrase

Direct phone-screen character voices as "slightly distant through the phone
speaker" to differentiate them from on-camera dialogue.

## Describing screen and UI layout positively

When directing a phone, laptop or tablet screen, describe the intended layout
positively. Add exclusions only for a specific leakage risk. Neither positive
nor negative phrasing guarantees the model will reproduce the layout.

**Wrong (negative):**
```text
No selfie picture-in-picture. No small inset window. No secondary camera view.
```

**Right (positive):**
```text
The phone screen shows a single full-screen video feed — his face fills the
entire screen edge to edge. A plain blue header bar sits at the top, with
the exact call timer added in post. The generated screen has no readable copy.
```

The positive description clarifies the desired layout without guaranteeing it.
An explicitly selected, eligible UI mockup can supplement that direction.
Exact layout and readable UI copy remain deterministic post work.

## Camera language

Put camera facts on every shot of a clip that cuts, and choose each shot's size,
angle and move from the scene's shot plan; see [Shot Staging](shot-staging.md).
A prompt with no camera line leaves the model free to choose the flattest default.

### Basic terms

| Type | Common Terms |
|---|---|
| Shot size | extreme wide shot, wide shot, medium shot, close-up, extreme close-up |
| Camera movement | push in, pull out, pan, lateral move, follow shot, orbit, dive, dolly out, tilt up, handheld shake |
| Camera position and viewpoint | low angle, overhead view, first-person view |

### Popular techniques

These can be used directly. If the frame has several subjects, still state
**which subject** the camera follows, **where** the movement begins, and
**where** it ends.

| Technique | What to Specify |
|---|---|
| One-take shot | Subjects, spaces, and events the camera passes through in order |
| Dolly zoom | Subject size to preserve; whether background moves closer or farther |
| Aerial view | Viewing height, movement direction, environmental area to reveal |
| FPV | First-person flight/traversal path, speed, turns |
| Bullet time | Action to freeze/slow down; camera orbit direction |
| Handheld camera | Subject being followed; amount of shake |
| Bounce speed ramp | Where action accelerates, decelerates, or rebounds; final resting state |

### Uncommon cinematography terms

For niche or potentially unrecognized terms:

> **Cinematography Term + Target Subject + Visual Change + Foreground/Background Relationship + Direction or Speed**

```
Rack focus: shift focus smoothly from the leaves in the foreground to the person in the
background. The leaves gradually blur while the person's face changes from soft to sharp.
```

Rack focus wording is owned by `seedance-lens-presets`. Preserve the requested
sharp plane and focus-loss endpoint. Any failure observation needs exact model,
operation, transport and evidence; it does not establish a family inability.
An authorized post defocus or retake is optional, not automatic. A paid probe
requires explicit authorization and verified preview mechanics.

A timed light change such as "at 3.2 s the overhead lamp clicks off and the room
drops to the blue window light" is authored intent, not guaranteed timing.
Inspect its actual result and keep any timing observation scoped to its binding.

For a precise transition, also state the **trigger time**, **occluding object**,
**camera direction**, **transition method**, and the **composition or motion
trend** that should continue afterward.

Additional cinematography examples:

```
Shallow depth of field: keep <Pastry Chef>'s eyes and face sharp while the glass jars and lights
in the background become soft, circular bokeh.

Tracking shot: move horizontally at the same speed as <Skateboarder>, keeping the subject sharp
while the roadside wall forms horizontal motion blur from right to left.

Golden hour: warm, low-angle sunlight enters from behind and to the left of <Hiker>, casting
long shadows across the mountain ridge.

Natural vignette: darken the four corners gradually while keeping the brightness and skin tone of
<Pianist> in the center natural, without a black border.

Whip-pan transition: at 5 seconds, move the camera rapidly to the left. Cut when the foreground
bookshelf fully covers the frame, then continue moving left at a similar speed in the next scene.
```

> Aperture, focal length, and shutter values can be included, but the intended
> **visible result** is usually clearer than a numeric value alone.

## Video call scenes

Video calls (FaceTime, Messenger, Zoom, etc.) shown on a phone or laptop screen
need explicit layout and speaker ownership. A selfie picture-in-picture (PiP)
is a possible unwanted result, not an inevitable behavior of every model.
Inspect actual output before diagnosing a failure.

### Rules for video call scenes

1. **Propose a screen UI mockup when needed.** Use deterministic HTML/CSS/SVG for
   exact layout and copy (e.g., a full-screen single video feed). Use Seedream
   only when the screen itself needs synthesized or illustrative imagery, then
   finish exact UI/text deterministically. A selected solid-background mockup
   may be used as an `@Image N` layout reference, but exact text remains a post
   layer because image conditioning does not guarantee pixel fidelity. This
   prompt-only leaf does not create or upload the mockup.

2. **Preserve on-screen identity and motion separately.** If an actual take
   renders a caller as a still portrait, diagnose the selected reference's role
   and request the required speaking movement. Do not drop an approved identity
   anchor automatically. Text can clarify: "the caller has the approved canon's
   appearance and speaks naturally through the phone screen."

3. **Use a Camera and Blocking section.** When a scene alternates between
   showing the main character's face and showing the phone screen, define
   explicit shot types:

   ```text
   [Camera and Blocking]
   The camera alternates between two shots:
   1. <Character>'s face — the camera faces them directly, eye-level.
   2. The phone screen — over the shoulder, showing the screen clearly.
   ```

   Then label each stage with "Shot 1" or "Shot 2" so the model knows
   which view to render at each timestamp.

## Spatial continuity

For movement-heavy scenes, define a spatial continuity contract before writing
shots or stages:

```text
Spatial continuity:
Start: [subject positions and orientation]
Travel axis: [origin → boundary or waypoint → destination]
Subject order: [who leads, follows, blocks, or remains stationary]
Boundary behavior: [who crosses, stops, lands, exits, or disappears]
End: [final subject positions and travel direction]
Forbidden transitions: [reversal, position swap, offshore approach, pursuer crossing ahead, etc.]
```

Use physical locations and ordered states rather than relative verbs alone.
"Enter the beach" can be ambiguous; "forest interior → inland tree line → white
sand → along the shoreline" defines a testable trajectory. When screen direction
matters, state it explicitly and keep it consistent across cuts.

Every cut can reset relationships. Repeat critical invariants — lead/pursuer
order, travel direction, boundary state, and absences — in every shot or stage
where they matter. Describe the positive physical state first, then add the most
important exclusion.
