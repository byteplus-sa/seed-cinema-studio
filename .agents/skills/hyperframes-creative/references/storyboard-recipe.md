# Storyboard recipe

Applies wherever a run plans on a storyboard (`storyboard: yes` in `brief-contract.md`). This file owns **how to make the storyboard**: what goes in it, and the HTML page the user reviews. `review-loop.md` owns when the user is asked; `storyboard-format.md` owns the `STORYBOARD.md` file the scripts parse. Nothing here is a Studio feature: the agent writes the storyboard, the user reads it in chat and in a browser.

Launch-style claims, beat lengths and motion defaults below apply only to
explicitly selected launch or promotional content. They are not requirements
for all narrated or narrative work. The approved script, narrative canvas,
aspect, timing and ending take precedence, including quiet held shots and
wordless scenes. Use `story-spine.md` for the selected launch structure, not
to recast a supplied narrative as marketing. Keep the review and lock gates.

## 1. Open with the decisions, before any beat

Message, audience, arc and format go in the `STORYBOARD.md` frontmatter (`storyboard-format.md`); the rest go in sections above the first `## Frame` heading. Frame packets take everything after a frame heading to the next one, so a section placed after the last frame leaks into that frame's packet. Repeat the first three in the chat proposal:

- **Message**: the approved narrative intention in one sentence. For explicit launch content, propose a claim, not a topic ("Close isn't final", not "About the inspector"); do not invent a product claim for other stories.
- **Audience and arc**: who watches, and the arc named in one line (pain → turn → proof → logo, or the workflow's own archetype).
- **Format**: aspect, target length, voiceover yes/no, music yes/no. Caption keep-out (content in the top ~83% when captions run).
- **The spine**: the one device that threads every beat, named now, not discovered while building (a persistent window, a silent button that finally has sound, one background that leads every transition).
- **Visual direction**: use the approved canvas and design tokens in `frame.md`. For real product launch content, derive brand tokens from a capture rather than memory; do not require a product site or three type roles for an unrelated narrative.
- **Bans**: a short per-video list derived from the brief. For launch content, consider repetitive fresh cards or unmotivated motion; do not classify an approved static endcard or quiet sequence as a defect.
- **Held frame**: preserve planned holds. For a launch treatment, consider a deliberate pause where a line lands; do not impose a new beat on an approved script.

## 2. The beat list

Follow the approved narrative beats; for a new launch proposal, use one idea
and focus per beat. Give each beat a short semantic name that will also be its
composition filename. Beat boundaries do not mandate editorial cuts.

| Field       | Rule                                                                                                                                    |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Heading     | `NN — Name (start–end, ~dur)`, absolute times. Sum the durations and state the total; check it against the target length by arithmetic. |
| Beat length | Use approved timing and actual reading or performance needs. For an explicit launch proposal only, 1.5–3.5 s is a starting estimate, not a cap or minimum. |
| On screen   | What is visible, in concrete terms (the object, its count, its position), with every on-screen word verbatim in quotes.                 |
| Voiceover   | Verbatim, or `onscreen` for silent films. Reveals land on the word or beat cue that names them.                                         |
| Hero prop   | The object that persists, and the beat where it returns (callback). A callback beat states which earlier beat it answers.               |
| Motion      | Named moves with easing and duration, or the intended hold. Motion within 0.2 s is a launch option only; approved narrative timing wins. |
| Seam out    | The approved cut, transition, direction or continued hold. For launch proposals, a consistent direction can help; leftward is not a universal default. |
| Audio cue   | Sound effect or music cue with its time, when the film has sound.                                                                       |
| Constraint  | At least one explicit "no …" per beat that could go generic.                                                                            |
| Why         | The beat's job in the approved story. Flag an unclear purpose for review, never remove a locked beat automatically for lacking a launch claim. |

Real product proof is real: a captured screen, the real command output, or a labelled placeholder beat that holds the slot. Never approximate the launched product's UI: use a capture or recording of it, rebuild only what the capture cannot move, or rebuild from its own design source (`/figma`). A third-party tool shown as context is rebuilt faithfully from a capture. Where the film depicts something real, add a truthfulness line saying what is real.

Craft devices that make a storyboard specific are taught with examples in `docs/prompting/storyboards.mdx` (breather, callback, two-color discipline) and `docs/prompting/motion.mdx` (hero prop, accumulation); use them by name.

## 3. `storyboard.html`: the page the user reviews

Write one self-contained HTML file in the project root, `storyboard.html`, from `STORYBOARD.md`. Tell the user the path and to open it in a browser. It is the review surface, and it must be beautiful enough to judge the film from.

- **Header**: title with a version (`v1`), one-line dek, and a tag with resolution, length and beat count.
- **Grid**: chronological cells matching the approved canvas aspect (`aspect-ratio` from that canvas, `container-type: inline-size`, sizes in `cqw` so the sheet matches the build), grouped under an act bar when there are acts. Three columns of 16:9 cells are an option only when the approved canvas is 16:9; never overwrite a portrait, square or custom narrative canvas.
- **Each cell** carries `id="frame-NN"` (the build reads its layout from there) and shows the beat's key moment drawn with the real words in the real fonts and brand colors, plain shapes for panels, charts and media, one accent on the focal. Then a label row (`NN · NAME` left, `id · start–end` right), a note that says what moves first and which way the seam goes (bold lead-in, one or two sentences), and a small chip naming the seam.
- **Two closing cells**: a seam map (every seam on one strip) and a tokens cell (palette, type roles, bans).
- **No motion, no scripts, no external assets.** Fonts are local `@font-face` or a system stack; images are inlined or relative. It must open from `file://`.

A sketch is a few dozen lines of HTML per cell; the whole sheet lands in minutes. Sketch fidelity is the point: a reviewer reacts to placement, hierarchy and copy, which is why the build later dresses the layout and never redraws it.

## 4. The review round

1. Present the chat proposal (`story-spine.md` § 3), then the sheet.
2. Record the user's notes verbatim under `## Changes from v1` and unresolved questions under `## Still open` (above the first frame), then bump the version and revise **only the beats named**.
3. Repeat until the user says the layout is locked, then list what is locked under `## Locked` (above the first frame, same reason as § 1). Build only after the lock.
4. When the build lands, compare actual timing from `index.html` (and the transcript when there is voiceover) with the locked plan. Report drift and reconcile it through review; a build does not silently supersede approved narrative timing. Update `STORYBOARD.md` and `storyboard.html` after the change is accepted and state the final length.

Do not render until asked.
