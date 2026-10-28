---
name: seedance-shot-design
description: >-
  Design the shot plan for a Seedance scene before any prompt is written: shot
  count and duration, the job of each shot, size, framing (single, two-shot,
  group, over-the-shoulder, over-the-hip, point of view, insert), angle, camera
  move, lens intent, named light sources and key side, the contrast between
  neighboring shots, and a variety check (V1-V10) at a chosen energy level
  (restrained, standard, kinetic). Use for narrative, ad, micro-drama,
  music-video and showcase clips when camera and light are not already locked,
  when a scene reads flat or static, or when the user asks for a shot list,
  coverage, shot framing, or more dynamic camera work and lighting. Returns a
  shot plan record and the per-shot facts a Seedance 2.5 prompt carries. Not
  for static assets, source-preserving edits (object swap, restyle, recast), or
  task submission.
---

# Seedance Shot Design

A Seedance prompt reads flat when nobody decided what the camera and the light
do for each beat. This skill makes those decisions explicit, one shot at a
time, before the prompt is written. It is planning only: it never calls a tool,
never generates media, and never replaces the grammar owned by the prompt
skill.

## Why clips read flat

The table describes coverage problems to investigate, not established causes
of every flat performance. A held setup, soft light or subtle action can be
intentional. Preserve the approved scene and consult its performance plan;
more cuts or camera movement cannot substitute for acting intent.

| Cause | What the plan does instead |
| --- | --- |
| Coverage hides the intended event | Choose a held setup or several shots that reveal the event (V1) |
| No camera-move statement, so the model holds a neutral frame | Every shot states its move with a start and an end, or records a `static_reason` (V3, V6) |
| Soft, hedged words ("gentle", "subtle", "slight") on every line | Active verbs with a speed: the camera drives in, sweeps, rises, snaps; the light rakes, cuts out, floods |
| Camera, lens and light presets used only when the user names them | The plan assigns them by default at the chosen energy level; a user lock still wins |

### Intent-led coverage

Choose clip boundaries from what the audience needs to perceive, the approved
action, sound/editorial intent and verified generation limits. An ad, trailer
or showcase has no automatic five-second sequence, shot-count or `wow` quota.
Short sequences and standout images are optional techniques. A sustained take,
equal durations or repeated framing can carry the idea without special waiver.
Record each shot's purpose, lens intent, move or hold and motivated light.

## Boundary

| Need | Where it lives |
| --- | --- |
| Resolve a named move or a framing type into canonical Camera phrasing | `seedance-camera-presets` |
| Resolve focal length, aperture or depth of field | `seedance-lens-presets` |
| Resolve a named light setup into recipes and phrases | `seedance-lighting-presets` |
| Speed ramps and montage rhythm | `seedance-pacing-presets` |
| When cuts land on a song (cut timing, beat contract) | the song owns the timing; this skill plans what each shot is |
| Character geometry and blocking | `blocking-map` |
| Dramatic structure of the scene | `scene-craft` |
| Performance intentions, triggers and listening | `acting-direction`; consume the supplied plan |
| Readable staged-fight exchanges and actor/prop states | `seedance-fight-choreography`; consume its ledger |
| Six-part formula, per-shot prompt block, references, audio syntax | `seedance-prompt-25` |

These are prose pointers for the calling agent. This skill decides *which*
choices a shot needs; the preset skills decide *how* each one is worded.

## When a plan is not needed

Record an exemption instead of a plan. The exemption reason is the plan. An
agent cannot choose an exemption to avoid the work: a `proposed`, `defaulted`
or `agent_confirmed` axis is not a user lock. A user lock fixes only what it
names; the plan still fills the rest.

| `static_reason` | Applies to |
| --- | --- |
| `user_lock` | The user, or a `user_confirmed` lock, fixed the camera or light |
| `format_static_by_design` | A format whose mode is a fixed frame: the `ugc`, `ugc-how-to`, `ugc-unboxing`, `product-review` and `ugc-virtual-try-on` modes, named UGC presets whose camera block is locked-off, talking-head, avatar and news-desk takes, frame-break. The `product-showcase`, `tv-spot`, `wild-card` and `virtual-try-on` modes take a plan |
| `skill_owned_camera` | Another skill supplies an explicit per-shot camera plan (a reverse-engineered pin plan). Derive the plan from it; V1-V3 are advisory. A music-video genre lock is vocabulary only and does not exempt: plan the shots |
| `plate_for_cutdown` | A source plate generated to be cut later; name the cut target |
| `source_preserved` | An edit, swap, recast or restyle that must keep the source camera |
| `extension_continuation` | Extending or continuing an existing take |
| `no_video_shot` | Audio-only work, static graphics and deterministic renders: no shot exists |

In a static-by-design format, variety may come only from light, a product
insert or B-roll the format allows; ask before leaving the format.

Two further reasons are not exemptions. They justify one held shot inside a
plan: `performance_hold` (stillness is the beat; quote the beat or cue that needs
it) and `contrast_hold` (a deliberate hold right after a moving shot).

## Input and output contract

Input: the scene beats and intended viewer reaction, location and light facts
(draft until canon is approved, then revalidated), runtime and aspect ratio,
any confirmed `directorial_axes` or `locked` block recorded in `project.md`,
and any user locks.
For character-performance work, consume the caller's performance plan with
beat IDs, intentions, listening tasks, required registration/response time and
critical acceptance criteria. For staged fights, consume the exchange and
state ledger. Missing material input goes back to the caller; this leaf does
not invoke the other skills or invent character motivations.

Output: a shot plan record per [shot plan format](references/shot-plan-format.md)
and the per-shot facts the Seedance 2.5 prompt carries.
Carry relevant performance/exchange beat IDs and readable evidence in existing
shot notes; this does not add provider parameters. Reconcile required cues
with crop, camera side, occlusion, scale and duration. Reserve listener and
reaction time, preserve sustained holds, and return conflicts with camera or
timing locks instead of silently changing them.

## Procedure

1. **Read locks and axes.** A `user_confirmed` camera or light choice is an
   input, not a suggestion. A confirmed project axis must reach the shots, and
   the plan records where. Fill only the gaps.
2. **Choose the energy level** from the intended reaction and format, never
   from genre alone.

   | Level | Fits | Typical shot length | Camera | Light |
   | --- | --- | --- | --- | --- |
   | Restrained | Naturalistic, documentary, brand-safe realism, quiet drama | 3-10 s | Slow motivated push, drift or pan; holds as contrast | Motivated window or practical light; soft contrast between shots |
   | Standard | Moderate energy supported by the brief | 2-6 s | Motivated moves or sustained holds | Named source and key side; contrast when useful |
   | Kinetic | Action, sport, chase, music video, high-energy ad | 1-3 s | Tracking, whip, handheld, crash zoom, orbit or FPV per beat | Hard contrast, rim or backlight, flicker, colored practicals |

   These ranges are optional planning examples, not timing or variety quotas.
   Separate actor energy, camera energy and edit rhythm. Kinetic dialogue is
   valid when words, speaking assignments and critical performance remain
   readable at the planned framing and speed. Do not soften body action merely
   because speech is present; verify the actual take by playback and listening.
3. **Give every beat a job:** establish, reveal, emphasize, connect, escalate,
   hold or release. A shot with no job is cut or merged into its neighbor.
4. **Set the shot count and lengths** from the beats. Density estimates are
   provisional, not a shot-count ceiling or minimum shot duration. Preserve
   requested rhythm within verified request limits; inspect actual cuts and
   propose assembly when exact timing or demonstrated merging requires it.
   Reuse suitable footage; additional generated clips require authorization.
   Choose equal or unequal lengths from perception time,
   performance and editorial intent. One shot across a long clip needs a recorded one-take or
   `static_reason`. Size dialogue shots from measured delivery or a
   native-language-informed read with pauses. About 2.2 words/s is an English
   estimate, not a universal gate. Derive onset and tail from measured delivery,
   the required response and intended ending, without fixed margins.
   Without evidence, timing is provisional. Preserve language and locked text;
   propose retiming or splitting before authorized rewrites. Judge final action
   by readability, not a state-change quota.
5. **Declare the scene's light sources** with world positions, the event that
   switches each on, and any in-scene cue that switches it off, dims it or makes
   it flicker. Then give every shot a source, a key side relative to the
   lens, a quality and a contrast. Assign each shot a size, a framing (who is
   featured and how the subjects relate, per [framing](references/framing.md)),
   an angle, a move with start and end, a lens intent as a visible result, and
   where useful its depth layers. Dialogue coverage may repeat or vary framing;
   choose movement by intent and speech/performance readability, not a speed cap.
   Plan an attention shift inside one frame with staging or a move, not a
   prompted rack focus: Seedance drafts keep a face sharp, so a focus pull away
   from a face is added in post (see the lens preset skill).
6. **Run the coverage checks below.** Explain how choices serve the brief.
   Mark a turn only when the approved scene contains one and the label helps.
7. **Tell one light story per scene.** The sources stay fixed in the room. A cut
   changes which side of a source the camera sees, or a motivated event adds or
   removes a source (a door opens, a lamp is switched on, the room lights go
   out). A light cue may land inside a shot, even during a move, when the plan
   records its time and trigger; a timed cue tends to land close to its
   stated time. A shot never invents a source or a cue the
   scene did not declare. A silhouette is compatible with speech when required
   cues remain readable; preserve concealed faces and flag visibility conflicts.
8. **Write the plan** per [shot plan format](references/shot-plan-format.md).
   Choose recurring structures from
   [coverage patterns](references/coverage-patterns.md).

## Variety rules

| Rule | Check |
| --- | --- |
| V1 Neighbor intent | Repetition or contrast in size, angle, move and key side serves attention, action or relationship. No minimum number of changed dimensions. |
| V2 Viewpoint | Choose eye level or another angle for what must be seen or felt. An entire scene may remain eye level. |
| V3 Motivated motion or stillness | Derive motion from the confirmed script, medium and directing intent. Motion ratios are optional planning aids, not quotas. A whole clip or scene may remain held with a recorded rationale; repeated stillness is valid when intentional. Do not insert a move, cut or light change merely to satisfy a count. |
| V4 Light named | Every shot names a declared source and a key side. "Cinematic lighting" and "soft fill" without a source and a side are not light facts. |
| V5 Emphasis | Emphasize the approved event where useful through performance, sound, staging, light or edit. No turn, largest-contrast shot or duration difference is required. |
| V6 Coherent camera path | A primary move with a compatible secondary is a planning aid. Preserve requested compound paths with explicit order and endpoints; flag competing directions or unreadable cues, not the move count alone. |
| V7 Readable performance | A move never stands in for a cue that cannot be read at that size; match shot size to the cues the beat needs. |
| V8 Screen direction | Travel and confrontation state the axis and restate it after each cut; a deliberate axis crossing is named. |
| V9 Perception time | Equal or unequal shot lengths preserve the needed action, attention, speech and response. Carry fixed song-map times and timing locks unchanged. |
| V10 Framing intent | In multi-character scenes name framing and featured subjects. Singles, shared frames and unpaired point-of-view shots are available when the relationship and required evidence remain legible; no coverage pattern is mandatory. |

## Inputs and limits

Storyboard grids and boards are planning and review aids and are never bound
as Seedance references: panel numbers and the sketch look leak into the video.
Blockout images are not bound by default. The plan's facts live in the prompt
text, beside the bound character, location and prop references. A first-frame
image fixes the opening size and angle of its shot, so V1 counts from the next
shot. A single location plate may not show the planned reverse or contre-jour
view: check that the plate supports each planned side, plan only supported
views, or request an approved extra view before Stage 6.

## Evidence and limits

A recorded plan (or exemption) is a workspace requirement under the
`shot.plan_bound`, `shot.variety` and `shot.axis_carry` rules. V1-V10
are intent/readability checks, not numeric variety quotas. Optional techniques are drawn from
common failure shapes: equal-length wide, medium, two-shot, wide ladders with
no move and no light change, and project axes that never reach the shot lines. V10 and the framing vocabulary follow a
StudioBinder framing article, with the group shot and the over-the-hip height
condition as workspace heuristics. None of them is a measured video-quality
gain.
Cut timestamps are a time budget, not frame-accurate cut points, and the model
may merge or reorder cuts; a timed light cue lands far closer to its stated
time. Judge the take by watching it. A 480p Draft
(`draft=true`) is the cheap way to check shot structure and motion before a
final render.

## Checklist

Before returning a plan, confirm:

1. Every shot has a job, duration, size, angle, move (or `static_reason`), lens
   intent, source and key side, and a framing in multi-character scenes.
2. V1 through V10 support the intended perception without imposing variety.
3. Locks and confirmed axes are carried, not overwritten.
4. The shot count and lengths fit the duration, the energy level and any
   dialogue.
5. No shot stacks competing moves, and no shot invents a light source or an
   undeclared light cue.
6. Exact edit timing names the available source footage and assembly operation.
   Short cuts alone do not require separate generation or slower rhythm.
7. Clip boundaries follow the approved idea and verified limits, not a cadence
   or standout-image quota.
8. No shot relies on a prompted focus pull away from a face; that defocus is
   planned for post.
9. The plan names where it is stored and which prompt carries it.

Worked cases are hypothetical teaching repairs in
[worked repairs](references/worked-repairs.md).
