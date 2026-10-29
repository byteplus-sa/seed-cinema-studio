# Episode Structure

Read [the entrypoint](../SKILL.md). Use this reference when drafting or
checking an episode brief, or when no market writer skill supplies one.

## Format

The format and beat tables are optional template proposals, not automatic
requirements when preference is missing. Select their use against the premise
under the existing approval mode. The confirmed script,
custom format or market card overrides aspect, runtime, scene split, casting,
dialogue, ending and cards throughout this reference. Adapt the brief fields
to those choices; do not invent a cliffhanger or dialogue for a wordless script.

- 9:16 vertical, 45–60 s delivered, three scene clips of about 15 / 20 / 15 s.
- Cast of at most three recurring characters per episode; incidental extras are
  described in scene direction, not canonized.
- One or two locations. One location per scene keeps geography stable.
- Let dialogue serve the approved story without a fixed line or word quota.
  Budget measured delivery or a native-language-informed read, pauses and the
  required response. About 2.2 words per second is a provisional English
  estimate, not a rejection gate. Derive onset and tail from performance and
  the intended ending, without fixed margins or final-state quotas.
  Preserve locked words; propose retiming or splitting before authorized
  rewrites, and obtain authorization for additional generated clips.
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

For the selected cliffhanger template, a held close-up before a card is one
option. Choose its duration by readable response; no close-up or 1.5 s quota.
A resolved or deliberately ambiguous ending may instead serve the approved brief.

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
6. The selected scenes, each with duration, action beats, exact locked dialogue when present in
   `{braces}` with speaker, the spoken word count, any supplied turn or proof beat, and
   the final visible state.
7. Subtitle translations for any non-English words.
8. Content limits: fictional characters only, no real brands, plain unlettered
   surfaces instead of signage, non-injurious conflict.
