# Dialogue and Audio Checklist

Multilingual and market-pack dialogue (stacked on the Seedance checklist) and
Seed Audio prompts. Apply the universal items in [the
index](review-checklists.md#universal--all-prompts) first.

## Seedance multilingual dialogue

Source skill: `seedance-prompt-25-dialogue`

Use as an additional checklist alongside Seedance 2.5 when the scene contains
spoken dialogue in a language other than English or in more than one language.

### Language and scope

1. **Language route recorded.** The dialogue language is checked against the
   native list; an unlisted language names its route (annotation, supported
   spoken language with subtitles, or explicitly requested audio-first).
2. **Exact words protected.** Locked dialogue, names and approved spelling are
   unchanged. A pronunciation or accent request alone does not authorize
   rewriting.
3. **Register grounded.** Formality, honorifics, regional variety and
   code-switching match the speakers and relationship; one voice is not forced
   on every character. Preserve the requested language and locked text. Ask
   when a missing register or code-switch preference materially affects a draft;
   an installed market pack does not select a mix. Dense passages in any
   language are not a defect by themselves.

### Delivery and evidence

4. **Notes separate from speech.** Spoken text sits inside braces; accent,
   pronunciation and acting notes sit outside unless a spoken-text edit is
   explicitly in scope. An accent-only request preserves the requested spoken
   language and never adds code-switching.
5. **Evidence distinguished.** A heard failure cites a recording or transcript
   diff; a predicted issue is labelled a hypothesis. Transcription checks the
   words; stress, intonation, accent and speaker identity need a listener
   (preferably native), rather than an audio model summary.
6. **No capability invented.** No guarantee of pronunciation, accent or lip-sync
   is claimed; the caller resolves tool and model support. A language or accuracy
   concern alone does not authorize a separate audio track.
7. **Subtitles in post.** Subtitle text follows the locked words and is not
   requested inside the generated video.

### Repairs

8. **Word-scoped.** A repair targets the wrong word (cue retake or splice); a
   whole-clip re-voice needs explicit user scope.
9. **Splice quality.** Set tolerances from the current voice and delivery, then
   verify identity, pronunciation, rhythm and continuity by listening. No
   fixed percentage from a previous production establishes acceptance.
10. **Audio binding evidenced.** An explicitly requested lip-sync track preserves
    approved words; the inspected audio path/hash, actual duration and original
    timestamps stay separate from proposed prompt timing. Confirm tool support
    for the exact ordered audio binding before submission.

---

## Seedance market-pack dialogue

Source skill: the explicitly selected market dialogue pack for the scene's language (for
example `references/review-checklist.md` inside the pack's own skill folder)

Use the pack's own checklist as an additional checklist alongside Seedance 2.5
when selected for a requested or confirmed market and a language it covers.
When no pack is selected, apply the Seedance 2.5 dialogue items and
`seedance-prompt-25-dialogue`.

---

## Seed Audio

Source skill: `seed-audio-prompt`

### Full-soundscape ingredients

1. **Environment.** Location, weather, context, acoustic space described.
2. **Background music and SFX.** Dramatic role, style, instruments, rhythm, mood,
   volume, opening intensity described.
3. **Character actions/appearance.** Included when they affect performance.
4. **Character voice profile.** Age, gender, accent, emotion, tone, speed, timbre for
   each character.
5. **Exact dialogue.** In double quotes, with delivery note before the quote.

### Arrangement order

6. **Input references** (only when reference audio included).
7. **Opening environment, ambience, music.**
8. **Dialogue, actions, SFX** in chronological order.
9. **Ending behavior.** Resolve, fade, sustain, or cut.
10. **Creative/quality constraints** (only when user supplies them).

### Input references

11. **Reference count.** ≤ 3 reference audio (TA2A) OR exactly 1 reference image
    (reference-image mode). Mutually exclusive.

12. **Per-clip limits.** ≤ 30s, ≤ 10 MB. Formats: WAV, MP3, PCM, OGG_OPUS.

13. **Single purpose per clip.** Each clip serves exactly one purpose: voice timbre
    cloning, emotion reference, or SFX reference.

14. **TA2A mapping.** `<<TGT_SPK1>>`, `<<TGT_SPK2>>`, `<<TGT_SPK3>>` mapped to ordered
    entries in `references[]`, labeled `@Audio1`, `@Audio2`, `@Audio3`.

15. **No references section.** When no references, the input references section is
    omitted entirely.

### Environment

16. **Acoustic quality specific.** "Hallway reverb," "stone corridor echo" — not just
    "echoey room."

17. **Layers described.** Foreground, midground, background.

18. **Evolution.** How environment evolves over time.

### Background music

19. **Dramatic role.** Underscore, tension bed, transition, reveal, celebration, outro.

20. **Style/genre/instruments.** Concrete musical language, not generic phrases.

21. **Dynamic arc.** How it begins, swells, thins, changes instrumentation, stops.

22. **Relationship to speech/effects.** When music ducks, effects dominate, ambience
    remains distant.

23. **Ending.** Clean stop, held unresolved note, crossfade, gradual fade.

### Ambience

24. **Persistent bed.** Separate from one-off effects.

25. **Distance/direction/room tone.** Echo, reverb, gradual evolution described.

26. **Subordinate to dialogue.** Unless scene requires otherwise.

### Sound effects

27. **Source/action/material/acoustic character.** Spatial position described.

28. **Positioned relative to actions/dialogue.**

29. **Evolution/decay.** Described when important.

30. **Onomatopoeia in quotes.** "ring-a-ling," "zzzip," "clack" — used to clarify
    texture, not as a substitute for describing the sound.

31. **Foreground/midground/background.** Identified when mix could be ambiguous.

### Character voice profiles

32. **T2A format.** `Name (age, gender, accent, voice timbre, emotional tone, delivery
    style) says: "dialogue text"`

33. **TA2A format.** `Name (voice description, voiced by <<TGT_SPKN>>) says [delivery
    note]: "dialogue text"`

34. **Voice contrast.** Each voice contrasts through pitch, timbre, accent, pacing,
    emotional baseline, or performance style.

### Dialogue

35. **Double quotes.** Spoken text in double quotes.

36. **Delivery note before quote.**

37. **Physical actions included.** When they affect delivery or generate sound.

38. **Multi-character chronological.** Alternates chronologically; actions/music/SFX
    between lines where listeners should hear them.

39. **Explicit attribution.** No unlabeled blocks of alternating quotes.

40. **Non-speech in brackets.** Ambient descriptions and non-speech sounds wrapped in
    square brackets.

41. **Prompt language = script language.** The prompt and the dialogue script are in
    the same language.

### Scene transitions

42. **Transition block format.** Audio state A → Transition trigger → Transition
    behavior → Audio state B → Forbidden carryover. All five fields present.

### Timestamp control

43. **Format.** `[start_time:end_time]` immediately before dialogue, in seconds with
    decimal precision.

44. **Used only when precision matters.** Omitted when event-relative cues suffice.

### Validation

45. **Character limit.** `text_prompt` ≤ 3000 characters.

46. **Duration limit.** Generated audio ≤ 120 seconds per call.

46a. **Short lines state their length.** A short line or sting states the
    clip length and the trailing silence; otherwise it can truncate (MINOR).

47. **No API concerns in prompt.** Does not insert "Max duration: 120 seconds" into the
    prompt — that is an API concern.

48. **Long requests split.** If requested generation > 120s, split before sending.

### Audio-video alignment (when used with Seedance)

49. **Same dialogue text in both prompts.** Exact lines match between Seed Audio
    `text_prompt` and Seedance `{curly braces}`.

50. **Audio duration ≤ video duration.**

51. **Shot timestamps align to audio.** Seedance shot time ranges match actual audio
    timing.

52. **Audio as reference_audio.** Passed to Seedance task as `reference_audio`.

### Brand-name pronunciation

53. **Respelling inside the dialogue line.** Any brand or domain name the
    voiceover must say correctly has its phonetic respelling written *inside*
    the dialogue line itself (not only in a note), using a real-word anchor
    rather than spaced or capitalized letters (e.g. `Echo-nos`, not `EH ko nos`).
