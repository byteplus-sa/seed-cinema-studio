# Market Card

Read [the entrypoint](../SKILL.md). The user decides the target market. There is
no built-in list and no default market: any country, region, diaspora, language,
dialect, audience, genre and platform is valid, including ones this repository has
never seen. The card is **optional**. When the user gives market details, record
them in `projects/<slug>/project.md` and treat the card as the single source for
every downstream skill. When they give none, proceed from the brief alone.

## Rules

- **Never assume a market.** If the user has not stated one, do not invent one
  and do not infer it from the user's name, location, language of the request or
  the examples in this repository. Take names, settings and language from the
  brief; ask a focused question only when a missing detail would materially change
  the result.
- **Partial cards are fine.** Fill only the fields the user cares about. When
  present, the block is checked for shape by the `brief-development` stage gate;
  an absent card is never an error.
- **Every field is free text** in the user's own words. A market pack is optional
  and is never required to proceed.
- **Mark guesses.** Anything not confirmed by the user or a native speaker goes in
  `unverified` and is surfaced for review.
- **Examples in this repository illustrate the format only.** Do not copy names,
  skin tones, settings, honorifics or idioms from an example into another market.

## Fields

```yaml
market:
  country_region: <where the story is set and who it is for>
  dialogue_languages:
    - language: <language>
      variety: <dialect or regional variety>
      register: <formal, casual, slang, period>
      accent_per_role: <optional, by character>
  subtitle_languages: [<languages for the sidecar files>]
  audience: <age band and segment>
  platform: <where it will be posted and its norms>
  genre_tone: <genre, tone, intended emotion>
  cast_appearance:
    cultural_identity: <as the user describes it>
    complexion_range: <natural range for this cast, or "per character">
    wardrobe_norms: <everyday and formal dress>
  setting: <architecture, climate, era, signage language>
  address_and_class: <honorifics, family terms, class markers>
  cultural_constraints: [<taboos, sensitivities, depictions to avoid>]
  content_limits: [<platform and user limits on violence, romance, themes>]
  card_idiom: <how the to-be-continued card reads in the dialogue language>
  unverified: [<items needing a native speaker>]
  pack: <optional market-pack skill name>
episode:
  count: <number>
  duration_s: <target length>
  aspect: <for example 9:16>
  scenes: [{role: hook, duration_s: <n>}, ...]
  max_recurring_cast: <number>
```

Every field may be omitted. `episode` defaults to the format in [episode structure](episode-structure.md) only
when the user states no preference; any value the user gives overrides it.

## Who reads the card

| Skill | Reads |
| --- | --- |
| `brief-intake` | Asks for and records the card |
| `microdrama-story-formats` or a market pack | Names, address, settings, proof objects, content limits |
| `seedance-prompt-25-dialogue` | `dialogue_languages`, `unverified` |
| `seedream-character-sheet`, `seedream-character-outfit` | `cast_appearance` |
| `seedream-location-asset` | `setting` |
| `micro-drama` | `episode`, `subtitle_languages`, `card_idiom`, `platform` |
| `prompt-review` | Dialogue language and descriptors match the card |
