---
name: story-development
description: Prepare premises, treatments, outlines and script-led scene lists. Use for narrative development or adapting supplied material. Do not use for generation or production orchestration.
---

# Story Development

Act as an independent leaf. Write development artifacts only; never invoke
sibling skills, generate media, initialize Studio, or approve production.
Follow the [development contract](../../contracts/production-development.md).

## Inputs

Require the scoped brief and any supplied screenplay, treatment, outline,
rights restrictions and creative locks. Record the intended unit or legacy
project scope. Ask only for missing choices that would materially alter the
story. Genre, medium, language, audience, runtime and delivery aspect are
independent; a vertical canvas does not imply micro-drama.

## Procedure

1. Inventory the sources by project-relative path and SHA-256. Read them in
   full. Distinguish source facts, explicit locks, proposed additions and open
   questions. Never rewrite or replace the supplied files.
2. Choose the smallest requested development output. For a supplied screenplay,
   make a faithful scene list and adaptation notes first; do not substitute a
   new premise or restructure it without authorization. For a new story, write
   a premise, treatment and ordered outline before a screenplay draft.
3. Preserve the brief's dramatic and stylistic intent, ending, quiet held
   moments and wordless passages. Do not impose Hook/Turn/Cliffhanger, a fixed
   scene count, a grade, a to-be-continued card or a duration from another format.
4. Write an ordered scene list with stable scene IDs, source page/section,
   setting and time, participating characters, visible action, narrative
   purpose, incoming/outgoing state, exact supplied dialogue references and
   duration estimate if useful. Estimates are planning, never measured timing.
5. Separate suggested revisions from the faithful extraction. Identify which
   locks, source lines and downstream scene IDs each proposal would affect.
   Carry existing IDs forward rather than renumbering approved scenes.
6. Return the output paths, source hashes, assumptions, unresolved questions
   and a precise change summary. Label new prose `draft`; only quote actual
   authorization when reporting a confirmed choice.

## Outputs

Use `development/<unit>/` for versioned `sources.json`, `treatment-vNN.md`,
`outline-vNN.md`, `script-vNN.md` and `scene-list-vNN.md` as requested. A
legacy scope can use a documented stable label such as `main`; this does not
activate a production manifest or unit Studio. Omit redundant outputs when a
locked source already supplies them.

The calling orchestrator may compose scene-craft specialists for a separate
dramatic pass. This leaf returns material and questions, not instructions to
load another skill. Source fidelity is not proof of creative quality.
