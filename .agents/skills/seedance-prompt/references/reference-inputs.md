# Reference Inputs

Focused reference for `seedance-prompt`. Read [the entrypoint](../SKILL.md) for
mode selection and caller responsibilities.

- [Reference materials](#reference-materials)
- [Precedence and accepted inputs](#precedence-and-accepted-inputs)
- [Multi-reference workflow (5 steps)](#multi-reference-workflow-5-steps)

## Reference materials

### Limits and selection

Verify image/video/audio counts, sizes, combined durations and role combinations
for the exact model, operation and destination. The
[parameter reference](parameter-reference.md) retains scoped historical snapshots,
not generic quotas. A family name or Flash suffix supplies no current evidence.
Choose only references whose role matters; more material is not automatically
better. Separate views can make one subject's structure clearer than a collage,
but no subject-count threshold guarantees stability.

### Role definition syntax

For each supplied or selected reference, specify exactly what it contributes. Add
exclusions only when a person, background, or composition could unintentionally
leak into the output.

Keep the caller's per-type order stable: `@Image 1`, `@Video 1`, `@Audio 1`.
These labels are a documented prompting convention, not upload instructions;
use destination-supported syntax and separate missing slots from real bindings.

**Three non-negotiable rules:**
1. Put the material mapping **directly in the prompt**.
2. **Never make the model guess** which asset belongs to which person, prop, or scene.
3. Add `"Do not use..."` exclusions only when leakage is genuinely possible.

```
@Image 1 defines <subject>'s <appearance, clothing, structure, or material>.
@Video 1 defines <motion, camera movement, or pacing>.
@Audio 1 defines <character or sound type>'s <voice, dialogue, ambience, or music>.

<Subject> completes <primary action or event> in <scene>.
The visuals feature <visual style>, with <camera treatment>.
```

Add `"Do not use..."` exclusions **only** when a person, background, or
composition in the reference could unintentionally leak into the output. You do
not need one for every asset.

### Stable subject definitions

For recurring subjects, define a unique label with stable visible traits such
as clothing, hairstyle, build or object structure, and reuse it through the
sequence. Keep transient expression or pose in the action rather than identity.
The 2.0 guide's `Define` notation is useful when supported, not a mandatory
section order for every model:

```text
Define the courier with a short dark haircut and blue jacket in @Image 1 as Courier.
Define the plain steel delivery case in @Image 2 as Case.
```

Short scenes can bind a subject inline. Never put internal asset IDs in place
of a visible subject description. Restate an applicable reference in a shot
when needed to disambiguate its owner, not as a repetition quota.

### Multiple views of the same subject

When several images show different angles of one person or product, state this
explicitly:

```
@Image 1 defines the front view of the same folding desk lamp.
@Image 2 defines the left-side structure of the same folding desk lamp.
@Image 3 defines the right-side structure of the same folding desk lamp.
@Image 4 defines the rear structure of the same folding desk lamp.
All four images define one folding desk lamp. The output must contain only one lamp throughout.
```

### Inheritance from reference videos

If a reference video already defines the motion, camera movement, and sequence
accurately, **state only which attributes to inherit** — do not restate every
action. Repeating the motion description may **conflict with the reference
itself**. A blockout video mainly provides motion and spatial structure, so the
prompt must still define the intended subjects, scene, action, and visual style.

### Reference classification

Classify each reference by how it may influence visible output:

- **Visible identity** — character, creature, costume, prop, or vehicle that should appear.
- **Visible environment** — location, lighting, weather, or production design that should appear.
- **Motion or camera reference** — movement language to transfer without copying pixels.
- **Control-only reference** — route map, blocking diagram, timing chart, or other planning material that must not appear.

Every supplied image can leak visible pixels, colors, lines, labels, or
composition into the result. For a control-only image, prefer translating its
information into concise textual choreography and omitting the image. Reference
content can overpower negative wording — if a character sheet contains an aura,
weapon, logo, or extra face that must not appear, clean or replace the reference
rather than relying on "no aura" constraints.

## Precedence and accepted inputs

- **A bound photo can outweigh text for details it shows.** Landing gear that is
  down in the reference may contradict the requested retraction. Flag the
  conflict and propose a scoped repair; do not change locked intent or replace
  an approved reference automatically.
- **People in video inputs.** Follow the workspace
  [video-to-video contract](../../../contracts/video-to-video-inputs.md) and
  exact operation eligibility. Identity, footage rights and voice authorization
  are independent. The caller may compose `seedance-virtual-portrait` for the
  authorized asset route; never disguise an input to pass a rejection.
- **Face/body crops and frame roles** need exact operation evidence. A rejected
  image is not permission to switch it into first-frame conditioning. Preserve
  the selected mode and resolve eligibility before execution.
- **Storyboards and boards are never inputs**; see
  [Keyframes Storyboards Blockouts](keyframes-storyboards-blockouts.md#storyboards-are-never-bound).

## Multi-reference workflow (5 steps)

When working with many references, the goal is **not** to put every reference
into one sentence. The goal is to define relationships and help the model
select the correct materials for each scene.

> **Define Each Material's Role → Map Subjects → Group by Type → Create Subject Profiles → Select References by Scene**

### Step 1: Name and map each subject individually

```
<Character A> corresponds to @Image 1. Use only the appearance, hairstyle, and clothing.
<Character B> corresponds to @Image 2. Use only the appearance, hairstyle, and clothing.
<Prop A> corresponds to @Image 3. Use only the structure, material, and color.
<Scene A> references @Image 4. Use only the spatial layout, architecture, and lighting. Do not use the people in the image.
```

Do **not** write `"@Images 1 through 4 define four characters respectively."` —
it never says which image maps to which character.

### Step 2: Group materials by type

```
[Characters]
<Conservator> corresponds to @Image 1. Use only the appearance, hairstyle, and clothing.
<Registrar> corresponds to @Image 2. Use only the appearance, hairstyle, and clothing.
<Exhibition Installer> corresponds to @Image 3. Use only the appearance, hairstyle, and clothing.
<Guide> corresponds to @Image 4. Use only the appearance, hairstyle, and clothing.
Do not interchange the four characters' appearances, clothing, actions, positions, or dialogue.

[Props]
<Sample Case> corresponds to @Image 5 and belongs only to <Conservator>.
<Record Board> corresponds to @Image 6 and belongs only to <Registrar>.

[Scenes]
<Conservation Lab> references @Image 7. Use only the space, materials, and lighting.
<Gallery> references @Image 8. Use only the space, materials, and lighting.

[Motion and Audio]
@Video 1 defines the motion of <Conservator> opening <Sample Case>. Do not use the person or scene from the video.
@Audio 1 defines <Guide>'s voice and specified dialogue.
```

### Step 3: Create a centralized profile for important subjects

When the same character uses several references across multiple scenes:

```
[Subject Profile: Conservator]
Appearance and clothing: @Image 1.
Fixed prop: <Sample Case> from @Image 5.
Locations: <Conservation Lab> and <Gallery>.
Motion references: the case-opening motion from @Video 1 and the sample-placement motion from @Video 2.
Do not use: other characters' clothing. Do not give this character <Record Board> or guide equipment.
```

### Step 4: Select references by scene

Each scene names **only** the assets it uses, the event, and the required end
state:

```
Scene 1 | Inspection in the Conservation Lab
Use: <Conservator>, <Sample Case>, <Conservation Lab>, and the case-opening motion from @Video 1.
Event: <Conservator> opens <Sample Case> at the workbench and inspects the sample inside.
End state: <Conservator> remains on the inner side of the workbench. <Sample Case> stays beside the
conservator's right hand, frame-left.

Scene 2 | Registration in the Gallery
Use: <Registrar>, <Record Board>, and <Gallery>.
Event: <Registrar> checks the number on <Record Board> beside the display case.
End state: <Registrar> still holds <Record Board> with both hands. No other character enters the
display-case area.
```

> The goal is to help the model select the correct materials for the current
> scene, **not** to make every material appear at the same time.
