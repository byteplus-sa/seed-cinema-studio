# Repairs

Read [the entrypoint](../SKILL.md). Derive repair decisions from the actual
voice, approved delivery and listening evidence for this take. A prior
production's outcomes are not universal acceptance criteria.

## Order of response

1. **Verify.** Compare a speech-to-text transcript against the approved words,
   then listen. A transcript cannot certify stress, tone or accent.
2. **Classify.** Wrong word, mispronounced word, delivery, pacing, speaker or
   alignment.
3. **Choose the smallest repair.**

| Problem | Repair |
| --- | --- |
| One word wrong or mispronounced in an otherwise good take | Retake the clip with one pronunciation cue outside the braces; if the retake changes the performance, splice only the word instead |
| Delivery or intent weak | Revise the delivery direction, not the words |
| Several words wrong across a clip | Retake the clip with the same words; do not re-voice the whole series |
| Line cannot be pronounced after a retake | Offer an alternative wording as a draft for the user to accept |

## Word-scoped splice limits

- Replace only the wrong word. Keep the original voice for everything else.
- Compare local pitch (f0), timbre, prosody, tempo and loudness around the
  replacement against the actual speaker, not a universal numeric threshold.
  Numeric differences help locate a possible mismatch but neither certify nor
  reject a splice on their own.
- Listen at normal speed both across the splice and in the full line; check
  intelligibility, speaker identity and room-tone continuity. Record the
  measurements, heard result and limits. Unavailable listening remains
  unresolved, not passed.
- Never replace a whole line or clip with a re-voiced version unless the user
  asked for it.

## Speech-timing traps

- Measure the last word's actual end and the intended pause or ambience tail.
  Check playback for truncation; do not impose a fixed tail duration on every
  language or performance.
- Keep the source soundtrack when re-voicing: send the original video with its
  audio and ask the model to fix the words; take the full audio back.

## Record the result

After each take, record the approved text, what was heard, the cue tried and
the outcome. Repeated failures for a language belong in that language's market
pack as observed failures.
