# Seedance Legacy Checklist

Seedance 2.0 generation (4K, Fast, Mini) and the legacy video-to-video VFX path.
Apply the universal items in [the
index](review-checklists.md#universal--all-prompts) first.

For applicable character performance and staged fights, also apply the
model-independent [Performance direction](../../../contracts/performance-direction.md#prompt-review)
criteria: `acting.plan_bound` and `fight.readable_exchange`. Include these checks
even if the caller omitted them. Missing material input is incomplete; material
omissions or contradictions are MAJOR. Static assets and preservation-only edits
record a concrete applicability reason; source performance still needs
preservation review.

## Seedance 2.0

Source skill: `seedance-prompt`

Use the consolidated creative grammar. The legacy examples below retain
useful subject, reference and continuity checks, not another required prompt
format. Verify tokens, role combinations and limits for the exact model,
operation and destination; historical API snapshots are not current evidence.

### Structure

1. **Readable structure.** Subject and action are clear, with applicable
   reference roles, task intent and constraints. Section order is flexible.

2. **Ordered references.** Each reference has a stable per-type label and role,
   using verified destination syntax. No uploads follow from writing the list.

3. **Reference limits.** Verify counts, combined durations and input combinations
   against the exact operation. Do not inherit limits from another variant.

### Subject definitions

4. **Stable subjects.** Use unique labels and relevant stable static traits,
   keeping expression and pose in the action. `Define` is an optional convention.

5. **Label reuse.** Keep each label tied to the same subject throughout;
   repeat it where needed to disambiguate ownership, not in every shot.

6. **No Asset IDs.** Use destination-supported reference labels and visible
   subject descriptions, not internal asset IDs in creative text.

### Reference classification

7. **Classification.** Each reference is classified as: Visible identity, Visible
   environment, Motion/camera reference, or Control-only reference.

8. **Control-only handling.** Translate analysis-only images to text and omit
   them. Intentional conditioning requires explicit selection, eligible roles,
   current hashes and QA; a control-only label never grants approval.

9. **Face restriction.** No direct uploads of real human faces. Uses recent model
   outputs, preset digital characters, or authorized `asset://` portrait
   assets (CRITICAL when a raw real-person photo is bound).

9a. **No storyboard binding (`board.animatic_review_only`).** Board panels and
   grids are never bound; their staging is written in the shot lines (CRITICAL
   when bound).

### Task type declaration

10. **Task intent declared.** Distinguish generation, reference-guided work,
    editing and extension. API operation values need independent verification;
    a historical task heading is not required.

11. **Edit/extend intent.** Name the source and requested operation directly,
    keeping it distinct from motion inspiration. Verify actual mode controls;
    wording alone does not select or enable an API operation.

### Shots

12. **Ordered action.** Use shots when cutting and stages when useful for a
    continuous take. Readable ordered actions or sustained states may share one
    shot; no event-count quota or named heading is required.

12a. **Shot plan carried (`shot.plan_bound`, `shot.variety`, `shot.axis_carry`).**
    The Seedance 2.5 shot-plan items (`shot.plan_bound`, `shot.variety`, `shot.axis_carry` in [the 2.5 checklist](checklist-seedance-25.md#shot-plan-and-structure)) apply to a 2.0 prompt: each shot line carries
    its size, angle, camera move (or a recorded static reason) and a declared
    light source with its key side, and coverage serves the approved intent.

13. **Per-shot ownership.** Keep applicable bindings unambiguous across cuts;
    repeat a reference only where needed to clarify ownership.

14. **Per-shot facts.** Carry camera, subject action, spatial changes, light
    and sound where relevant. Their order is a readable convention, not a gate.

15. **Coherent camera movement.** Preserve requested paths with sequence and
    endpoints; flag competing simultaneous directions or unreadable evidence,
    not the number of moves alone.

16. **Complexity budget.** Density estimates are provisional; preserve requested
    rhythm within verified request limits. Flag demonstrated lost action or
    continuity, not a numeric beat or shot quota. Additional generated clips
    require authorization.

17. **Action detail.** Include body parts, range, speed and force where needed
    for critical action readability, not as an exhaustive checklist.

18. **Intent-led body energy.** Speed, amplitude, interruptions and recovery
    follow approved action with grounded physics. No slow-body preference or
    universal burst limit applies. Actor energy, camera energy and edit rhythm
    are separate; speech requires readable performance, not automatic restraint.

19. **Emotion externalization.** Emotions are externalized as physical details,
    never bare labels.

20. **Dialogue format and budget (`dialogue.speech_budget`).** Spoken text in
    `{curly braces}` or quotes for lip-sync, with speaker labels for several
    speakers. Use measured delivery or a native-language-informed read with
    pauses, onset and tail. Words / 2.2 is an English planning estimate, not a
    universal rejection rule. Derive onset and tail from measured delivery,
    required response and the intended ending without fixed margins or final
    state quotas; without evidence, fit is provisional.
    Preserve approved text; propose retiming or splitting before an authorized
    wording change.

### Timing

21. **Duration via API.** Total video length uses verified request controls.
    Creative timestamps describe action timing, not an API duration setting.

22. **Natural pacing.** Event-relative timing is valid. Add precise timing for
    requested or critical synchronization; do not round measured source times.

23. **Timestamp format.** If used: concise ranges (`Shot 1 (0-4s):`), contiguous,
    non-overlapping, consistent with API duration.

### Spatial continuity

24. **Spatial continuity.** When geography matters, clarify start, travel axis,
    subject order, boundary behavior, end and forbidden transitions. These are
    useful questions, not mandatory headings for a simple held shot.

25. **Physical locations.** Uses physical locations and ordered states, not relative
    verbs alone.

### Quality and constraints

26. **Inline constraints.** All constraints go inline in the text prompt (no separate
    negative_prompt field).

27. **Prioritized constraints.** Prioritizes constraints instead of accumulating a
    long blacklist.

28. **Positive phrasing.** States required physical behavior positively. Repeats only
    the few exclusions that prevent expensive failure.

### Preflight review (6-point)

29. **Parameter agreement.** Prompt and API resolution, duration, ratio, and audio
    setting agree.

30. **Reference indexing.** Every reference is indexed, classified, and bound only
    where intended.

31. **Spatial fields.** Material positions, travel, order, boundaries and end
    state are explicit; stationary scenes need no invented trajectory.

32. **No contradictions.** No contradictory instructions (e.g., "single continuous
    shot" plus several cuts; "no powers" plus an emitting aura reference).

33. **Focus.** Prompt is focused; repetition compressed before removing critical
    spatial state.

34. **Beats fit duration.** Return concrete timing conflicts. Splitting,
    retiming and extra generation require authorization, never an automatic fix.

### Revision contract (if revising)

35. **Locked decisions carried.** Approved identity, action, camera, environment,
    audio, boundary behavior carried into revised prompt.

36. **Requested delta.** Change only the requested behavior; separate prompt
    wording, reference bundle and motion design changes when practical.

37. **Acceptance criteria.** Observable conditions for the next take to pass are
    stated.

38. **Known rejections.** Behaviors from earlier takes that must not return are listed.

---

## Seedance VFX (video-to-video)

Self-contained checklist for legacy video-to-video edits.

Historical examples are optional, not capability evidence. Preserve fractional
source duration, frame timing, cuts and audio tails; missing measurements stay
unresolved. Adaptation needs explicit approval, source/derivative hashes, exact
window and timing/audio consequences. Never round, trim, pad or retime silently.

### Core principle

1. **Source clip is the lock.** The prompt preserves what to keep (subject identity,
   performance, camera motion) and describes only what should change. It does not
   re-describe the entire scene from scratch.

### Asset preparation

2. **Source role.** The source is explicitly an editing master, not motion
   inspiration. `Edit @Video 1` is a convention; verify actual operation syntax.

3. **Source described.** Subject, action, camera motion, and duration of source clip
   are described in asset preparation.

4. **Source inspected.** The source clip was inspected before writing (duration, fps,
   aspect ratio probed). Prompt is built from footage, not user's one-line summary.

5. **Texture references labeled.** Texture references say "texture only" — "appearance
   and fur/skin texture reference only; ignore the photo's background and lighting."

### Subject definitions

6. **Stable subject.** A unique label and relevant stable traits bind each
   subject to the source. `Define` and `<Label>@Video 1` are optional conventions.

### Locks (preservation)

7. **Locks declared.** Identity (face, body, costume, props), Performance (gait,
   gestures, expressions, timing), Camera (motion type, framing, lens, bob),
   Continuity are locked with `<Label>@Video 1`.

### Change

8. **Change named with timestamp.** The exact change and when it happens are stated
   (`At 0:NN` for localized changes). Global changes at `0:00`.

9. **Subject reaction.** Whether the subject reacts or does not react is stated.

### New world

10. **Full description.** Replacement/added environment/element is fully described.

### Lighting (embedded)

11. **Lighting lives in the world.** Light sources are physically present in the new
    world. Not described as a layer pasted on top.

12. **No generic lighting terms.** Does not say "cinematic lighting" or "dramatic
    lighting" alone — names the source.

13. **Light on subject.** Where light falls on subject (direction, color, intensity)
    is described.

14. **Light-environment interaction.** How light interacts with environment
    (volumetric mist, reflections, shadows) is described.

15. **Integration fork decided.** Either "preserve subject's lighting; grade only new
    elements" (default) OR "relight the whole frame under one look" is explicitly
    chosen.

16. **"Looks pasted in" recipe applied.** Light (direction, softness, shadow density),
    environmental bounce, optics & atmosphere (lens, micro-contrast, haze, DOF, grain),
    edges & grounding (no hard cut-out, no halos, matched rims) are addressed.

### Space

17. **Layered space.** Foreground (parallax elements), Midground (subject + primary
    environment), Background (atmosphere and scale) are described.

### Timing

18. **Sequential timestamps.** When each event triggers and how it progresses.

19. **Timed camera moves dual-anchored.** Semantic anchor ("At the line '<exact
    words>,' the camera <move>") AND numeric anchor ("At about <T> seconds...").

20. **Zoom type specified.** Crash zoom = fast hard punch-in. Smooth push-in = slow
    steady glide.

21. **Tail after trigger.** Use the approved trigger and required response.
    A short clip does not authorize moving the trigger, truncating speech or
    adding time; return an actual conflict for authorization.

22. **Reveal pull-back.** If used: opens tight on added element, moves outward to land
    on real plate, demands 100% match of source composition at landing.

23. **Lip-sync window checked.** If lip-sync preservation: line quoted verbatim,
    anchored twice (in change/action and in audio), `SFX and source dialogue only`
    requested, "lips matching the source exactly" in Locks, line fits surviving
    dialogue window.

### Audio

24. **Diegetic only.** Only sound that physically exists in the new world. Preserves
    source-clip diegetic sounds that still make sense.

25. **No non-diegetic audio.** Does not request background music, score, or voiceover
    unless part of source footage.

### Quality and constraints

26. **NON-IP.** No recognizable real persons, no copyrighted characters, no brand logos.

27. **Face protection.** "Real human skin with pores, stubble, and catchlights — never
    waxy, smoothed, or warped."

28. **Supported model/mode (`model.supported_mode`).** Resolve exact model,
    operation and destination first. Resolution and face-input support require
    current evidence; preserve a locked target without switching models.
    Face/detail fidelity needs output QA, not an assumed resolution guarantee.

### Creature/element integration (if applicable)

29. **Photoreal demanded.** "Fully photoreal, real fur with depth and individual
    strands, true anatomy, never CG, plastic, or cartoonish."

30. **Tied into plate.** Same sun direction, real soft-edged contact shadow, same hazy
    atmosphere.

31. **Scale explicit.** Scale is explicit for giant creatures.

32. **Texture fallback.** If still reads CG: second input — reference photo of real
    animal as texture-only `@Image N`.

33. **Species behavior.** Behavior matches the species (sloth slow, chimp twitchy,
    snake coils and forked tongue, snakes don't blink).

34. **Living micro-movements.** For static creature holds: slow blink, jaw shift,
    steady breath.

### Duration discipline

35. **Source runtime default.** Defaults to source clip's exact runtime.

36. **Recomputed timing.** Only after an approved runtime adaptation, reconcile
    numeric cues with the recorded derivative timeline.

37. **Prepended-intro budget.** Added material must leave the full source
    performance and audio tail intact. A conflict remains unresolved; altered
    placement, total runtime or truncation is a proposal requiring approval.

### Iteration discipline

38. **Only named change.** Only the named thing changes; rest of prompt stays stable.

39. **Refine via edit.** When refining a generated still/frame, edits the chosen result
    (passes it back as base) and fixes only what is off.

### Voice

40. **No generic adjectives.** No "beautiful," "stunning," "amazing," "cinematic."

41. **Concrete language.** Names exact materials, behaviors, scale, lenses, angles,
    moves. Uses texture words. Does not inflate, soften, or explain what things
    "represent."
