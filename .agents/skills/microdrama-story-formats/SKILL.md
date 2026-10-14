---
name: microdrama-story-formats
description: >-
  Develop micro-drama stories for any market, language or genre: pick a proven
  format (billionaire or CEO romance, hidden heir or identity reveal, revenge
  and rebirth, in-law or family conflict, mafia or alpha, switched at birth,
  campus, thriller, horror, comedy, historical or fantasy, true-to-life
  sacrifice), then write a locked episode brief with a three-beat hook, turn
  and cliffhanger, a light cast, culturally grounded settings, props and
  wardrobe, dialogue in the target language, and subtitle translations. Use for
  micro-drama concepts, loglines, episode briefs, series bibles or dialogue
  passes in any language, including concept-only or prompt-only work, and as
  the fallback story writer when no market pack exists. This leaf writes story
  material only; it does not generate media. Pair it with micro-drama for
  production and seedance-prompt-25-dialogue for spoken-delivery direction.
---

# Micro-Drama Story Formats

Write micro-drama story material for any market that performs on vertical
platforms and reads as authentic to its audience. The output is a locked
episode brief, or a set of briefs for a series or batch. Any production
orchestrator can consume it. A market pack, such as `filipino-micro-drama`,
adds deeper local craft; this skill is the market-neutral writer.

## Inputs and outputs

Input: market or audience (country, region, diaspora, age band), dialogue
language and register, number of episodes or concepts, an optional format,
tone (melodrama, kilig or romance, thriller, comedy, horror), and any locked
names, lines or limits.

Output per episode: the brief fields in
[the episode brief template](references/episode-brief.md), with dialogue in
`{braces}` and a subtitle translation for every line not in the subtitle
language. For batches, choose a different format for each episode unless the
user asks otherwise.

## Procedure

1. **Use the market if given.** The user decides it and may give none; never
   default to a market or infer one. When details are given, record the optional
   market card (country or region, dialogue language and register, audience,
   platform, cast appearance, content limits) as defined in the `micro-drama`
   market card. Follow
   [market adaptation](references/market-adaptation.md) to ground names,
   settings, honorifics, wardrobe, taboos and the proof object. Ask a focused
   question when the market is unstated and the choice changes the story.
2. **Plan a series first.** For 6-10 connected episodes, write the bible with
   [the series bible template](references/series-bible.md) before any episode
   brief.
3. **Choose the format.** Use [formats](references/formats.md). Match it to the
   audience and to what can be staged with at most three recurring characters
   and one or two locations.
4. **Build the beats.** Hook in the first 3 s, then the setup, a turn or reveal
   with physical proof, and a cliffhanger held on a close-up. Keep each scene
   to 3-5 short lines.
5. **Write the dialogue in the target language.** Keep every story-critical
   line short and speakable, with the plot-critical word mid-sentence at
   normal volume rather than shouted or whispered. When dialogue language is
   not natively supported by the video model, flag it for the dialogue partner
   skill rather than writing around it.
6. **Dress the world.** Everything is fictional: no real brands, no legible
   signage, no celebrity likeness. Use local signifiers from the market
   adaptation notes.
7. **Lock the brief.** State the format, the logline and the cliffhanger
   question in one line each.

## Boundaries

- Story and dialogue only. Delivery, pronunciation direction and prompt
  syntax for Seedance belong to `seedance-prompt-25-dialogue` (or a market
  partner) and `seedance-prompt-25`. Production belongs to an orchestrator such
  as `micro-drama`.
- Conflict follows the market card's content limits; with none stated, stay
  non-injurious (a sharp contact or a cut on contact, never blood or injury
  detail). No minors in peril, no sexual content.
- Formats are genre conventions. Do not copy a named show's characters, plots
  or lines.
- Market claims about what performs go stale. Recheck current platform
  performance before presenting them as fact.
- New wording is a draft until the user accepts it. Once locked, preserve
  exact words downstream.
