# Repairs

Read [the entrypoint](../SKILL.md). These rules come from the first
production series; they apply to every language.

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
- Reject a splice whose tempo or pitch differs from the original by more than
  about 10 percent; four such splices were heard as voice changes.
- Check pitch (f0) continuity at the splice points and listen at normal speed.
- Never replace a whole line or clip with a re-voiced version unless the user
  asked for it.

## Speech-timing traps

- A line that ends in the last second of a clip is often clipped. Leave a tail
  of silence or ambience after the last word.
- Keep the source soundtrack when re-voicing: send the original video with its
  audio and ask the model to fix the words; take the full audio back.

## Record the result

After each take, record the approved text, what was heard, the cue tried and
the outcome. Repeated failures for a language belong in that language's market
pack as observed failures.
