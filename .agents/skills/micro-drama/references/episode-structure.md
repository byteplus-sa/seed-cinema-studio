# Episode Structure

Read [the entrypoint](../SKILL.md). Use this reference when drafting or
checking an episode brief, or when no market writer skill supplies one.

## Format

Defaults apply only when the user states no preference; the market card
overrides aspect, runtime and scene split.

- 9:16 vertical, 45–60 s delivered, three scene clips of about 15 / 20 / 15 s.
- Cast of at most three recurring characters per episode; incidental extras are
  described in scene direction, not canonized.
- One or two locations. One location per scene keeps geography stable.
- Dialogue carries the plot. Aim for 3–5 short lines per clip; a clip with more
  than about 12 spoken seconds rushes delivery and invites word errors.
- Word budget: about 2.2 spoken words per second of the time the lines can
  occupy, remembering that speech starts 0.5–1.5 s after its cue. A 15 s clip
  carries roughly 20–25 words; the last line ends at least 0.4 s before the
  clip ends.
- The hook line uses plain, common words that speech-to-text transcribes
  cleanly, spoken at normal volume.

## Beat template

| Beat | Delivered time | Purpose | Must be visible |
| --- | --- | --- | --- |
| Cold open / hook | 0–3 s | Start mid-conflict: an accusation, a thrown object, a shocking line, a ringing phone, a locked door | The wronged character and the aggressor in one readable frame |
| Setup | 3–15 s | Who is wronged, what they want, what the status gap is | Status markers: wardrobe, posture, setting |
| Turn | 15–35 s | The confrontation or reveal: a document, a mark, a message, a stranger at the door | Physical proof in a clean insert or close-up |
| Reaction | 35–45 s | Power shifts; the audience's sympathy is confirmed | Held reaction close-ups |
| Cliffhanger | last 5–10 s | A new threat or reversal that reopens the question | A final held close-up of the character who has just learned it |

Physical conflict follows the market card's `content_limits`. When it states
none, stay non-injurious: a clean contact or a cut on contact, a head turn, and
a held silence, without blood, injury detail or weapons. Horror, thriller and
action may set other limits in the card.

## Cliffhanger patterns

- A whispered secret that reframes the reveal ("you don't know who your real
  mother is").
- A document or object that flips ownership (a title deed, a test result).
- The winner lies to the audience's face (tearing up a result and saying the
  opposite).
- The victim is revealed to have an agenda of their own.
- A supernatural tell seen only by the audience (a shadow, a reflection).

End on a held close-up of at least 1.5 s before the card. Do not resolve the
question inside the episode.

## Cards

- **Title card:** 1.5–2 s, deterministic HTML render, placed after the cold
  open line or dissolving in under it, never before the hook.
- **To-be-continued card:** 2 s, deterministic render, with the market's
  idiom from the market card's `card_idiom`, in the dialogue language, optional one-line teaser question.
- Cards carry the only on-screen text. Subtitles are a sidecar file.

## Episode brief fields

A market writer skill or the author supplies:

1. `slug`, title, market, language and register, formula.
2. Logline in one sentence.
3. Cast table: name, age, look, wardrobe, always-worn items, role.
4. Locations: layout, light, time of day, geography-critical landmarks.
5. Props that pass the threshold: story-critical or identity-critical only.
6. Three scenes, each with duration, action beats, exact locked dialogue in
   `{braces}` with speaker, the spoken word count, the turn or proof beat, and
   the final visible state.
7. Subtitle translations for any non-English words.
8. Content limits: fictional characters only, no real brands, plain unlettered
   surfaces instead of signage, non-injurious conflict.
