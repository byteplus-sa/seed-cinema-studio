# Framing

Focused reference for `seedance-shot-design`. Read [the entrypoint](../SKILL.md)
for the procedure and the variety rules, and [shot plan
format](shot-plan-format.md) for the `framing` field.

- [Source and status](#source-and-status)
- [What framing decides](#what-framing-decides)
- [Framing types](#framing-types)
- [Choosing a framing](#choosing-a-framing)
- [Framing in the plan](#framing-in-the-plan)
- [Failure shapes](#failure-shapes)

## Source and status

The framing definitions follow the StudioBinder article "Camera Framing
Techniques" (SC Lannom, 2025-05-20, accessed 2026-10-17:
https://www.studiobinder.com/blog/types-of-camera-shot-frames-in-film/): single
and dirty single, two-shot, three-shot, over-the-shoulder, over-the-hip, point
of view and insert, with size, relationships and balance as the factors. The
group shot, the balance reading, the "Use when" column, the mapping to plan
fields, the variety rule and the wording notes are this workspace's own craft
heuristics. None is a verified Seedance control: the
model's official vocabulary names shot sizes, `low angle`, `overhead view` and
`first-person view`, and the other terms below are common film language that the
model may or may not honour. Check framing in a 480p draft before relying on it
in a final render.

## What framing decides

Framing is the placement and position of subjects in the frame, not merely where
the camera points. Three decisions carry it:

| Decision | Meaning | Plan field |
| --- | --- | --- |
| Size | What scale makes the intended action, relationship or environment readable | `size` |
| Relationship | Several featured subjects in one frame are read as related (romantic, contentious and so on) | `framing`, `featured` |
| Balance | A balanced frame holds elements on both the left and right sides; reading an unbalanced frame as tension or isolation is a workspace heuristic | `composition` |

A subject is *featured* when the shot is about it: in focus, in the plane the
viewer reads. A foreground shoulder that only gives perspective is not featured.

## Framing types

`featured` counts the subjects the shot is about. Size is chosen independently of
the framing type.

| Framing | Featured | Job | Use when | Wording notes |
| --- | --- | --- | --- | --- |
| Single | 1 | Isolate one subject's face, body or reaction | A performance beat needs one readable face; any size works | Say that only the subject is in frame |
| Dirty single (over-the-shoulder single) | 1 | Keep a relationship alive while showing one person | A dialogue or confrontation where the listener's presence must stay felt | Name the foreground character's side of frame and keep that character soft and unfeatured |
| Two-shot | 2 | Let a performance play out in one take; show two people as related | Comedy timing, intimacy, a pair reacting together, a release after singles | Name who is screen-left and screen-right |
| Three-shot | 3 | Show a trio without paying for three singles | Adventure, family, any small group | Name the left-to-right order |
| Group shot (workspace addition) | 4 or more | Place an ensemble in one space | Establishing a crowd, a family table, a team | Name the grouping and the front or center subject |
| Over-the-shoulder (OTS) | 1 featured, 1 foreground | Orient the scene and connect two characters emotionally; it echoes what one of them sees | Conversation scenes | The foreground shoulder and back of the head sit soft at one side of frame |
| Over-the-hip (OTH) | 1 featured, 1 foreground | Like OTS, but with a hip in the foreground; a supplied standing/seated difference may help show a relationship | Actual blocking places a hip in the relevant foreground | Describe the foreground hip and hand and the featured subject at their actual positions and heights; do not invent a height difference |
| Point of view (POV) | 0 or more | Show exactly what a character, or an object such as a bullet or a rolling ball, sees | A reveal that the viewer must read as the character's discovery | No part of the looker is visible except hands or limbs they would see |
| Insert | 0 | Direct attention to a detail, or show the viewer something the characters miss (dramatic irony) | A prop, a screen, a hand, a note, an environmental clue | The detail fills the frame; add a face only when the beat needs it |

Notes on the types:

- Name screen positions as frame-left and frame-right. The model reads "her
  left" as the character's own side, so a hand or a shoulder is named by both
  anatomy and frame side ("her right hand, frame-left").
- A single can be framed at any size. Only the count of featured subjects makes
  it a single.
- A dirty single technically has two people in the frame. It remains a single
  because only one is featured.
- A look, POV, reaction sequence is one way to establish viewpoint. Existing
  scene context may already make ownership clear without either adjacent shot.
- An insert is only as useful as how it presents the information. Choose the
  detail, its size and its move for what the viewer must learn, and keep it to
  props and details the canon approves (the prop threshold applies).

## Choosing a framing

Decide the framing from the beat, actual blocking and source locks, then confirm
the size. These options are not required coverage or authority to add clips.

| Beat | Framing | Why |
| --- | --- | --- |
| One character's private reaction | Single, close-up | Isolation and readable cues |
| Confrontation, one side dominates | Dirty single on the weaker side; over-the-hip instead when their heights differ | The pressure stays in frame |
| Two people playing a joke or an intimate moment | Two-shot, held | The timing needs both in the same take |
| A small group reacts together | Three-shot | Can preserve simultaneous responses in one frame |
| A character discovers something | Looker, POV, reaction | The viewer shares the discovery |
| A detail the characters cannot see | Insert | Dramatic irony |
| Orienting a new space with its people | Group shot or wide | Places everyone |

Size follows the evidence the audience needs. An important subject may stay
small in a purposeful wide that reveals isolation, geography or a relationship.
Do not enlarge it merely to signal importance or change actual blocking to
fit a framing label.

## Framing in the plan

- Every shot in a scene with two or more characters carries a `framing` value
  and its `featured` subjects. Other scenes may omit it.
- Framing type is checked by V10 for readable evidence, not a contrast count.
  A dirty single, over-the-shoulder and over-the-hip framing record
  `angle: over-the-shoulder` and a point-of-view framing records `angle:
  first-person`; these compatibility labels do not impose angle variety.
- Establish POV ownership through the available context; a looker/reaction
  sequence is optional. Do not add generated clips without authorization.
- Use an unbalanced frame on purpose and record it in `composition`.

## Failure shapes

| Shape | Why it reads as flat or confusing | Repair |
| --- | --- | --- |
| Clean singles lose a required relationship cue | The intended interaction is unclear | Repair the cue in existing coverage; a shared frame is optional |
| Framing label disagrees with actual featured subjects | Plan and prompt describe different evidence | Correct the label without forcing a face reveal or softening a relevant listener |
| POV ownership is unclear in context | The viewer cannot identify the viewpoint | Clarify ownership; propose extra coverage only within authorization |
| Separate singles hide a required simultaneous reaction | The timing cannot be read | Propose a shared frame or preserve the interaction in existing coverage |
| An OTH label does not match actual blocking | The label encourages invented staging | Describe the actual hip/subject relationship or choose another framing; preserve heights and positions |
| A wide hides a required detail | The critical evidence is unreadable, not unimportant | Adjust the cue or propose coverage while preserving purposeful wide framing and locks |
