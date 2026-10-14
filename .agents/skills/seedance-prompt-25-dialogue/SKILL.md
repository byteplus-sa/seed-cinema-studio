---
name: seedance-prompt-25-dialogue
description: >-
  Write or revise spoken-dialogue direction for Seedance in any language:
  check whether the language is natively supported, preserve approved exact
  words, speaker identity and register, direct accent, code-switching and
  delivery, and handle unsupported languages through annotation, a supported
  spoken language with subtitles, or an explicitly requested audio-first
  track. Diagnose a specific heard pronunciation or delivery problem before
  proposing a word-scoped retake or splice. Use for micro-drama and other
  video prompts with non-English or multilingual dialogue; this independent
  prompt-only leaf returns a dialogue layer and does not submit generation
  tasks. Market packs such as seedance-prompt-25-filipino add language-specific
  depth.
---

# Seedance Prompt 2.5 — Dialogue Partner (Any Language)

Write dialogue and delivery direction for any spoken language while preserving
the user's intended voice. The caller composes this dialogue layer with a full
video prompt; this skill does not load sibling skills.

## Input and output contract

Input: exact dialogue or a request to draft it; locked words; speaker and
addressee; scene purpose; language, regional variety and register; accent
target if any; observed speech defect or a reference recording; native audio or
an explicitly requested separate lip-sync track.

Output: approved spoken text, a concise delivery layer, any proposed change
shown separately, a language-support verdict, and the evidence or hypothesis
behind any pronunciation guidance. If critical context is missing, ask a
focused question while keeping existing words and completing the unaffected
direction.

## Core decisions

1. **Check language support first.** See
   [language support](references/language-support.md). A natively supported
   language needs only delivery direction. An unlisted language needs a
   recorded route before anything is submitted.
2. **Preserve locks.** Record exact wording, names, politeness, code-switching
   and character intent that must survive. A pronunciation request does not
   authorize rewriting dialogue.
3. **Use native audio by default.** The language alone does not request a
   separate Seed Audio track. Use separate lip-sync audio only with explicit
   scope.
4. **Identify the actual problem.** Distinguish stiff wording, unclear motive,
   register mismatch, wrong spoken word, pronunciation, accent, pacing and
   audio/video alignment. Without a recording, a predicted issue is a
   hypothesis, not an observed failure.
5. **Make the smallest repair.** Prefer delivery direction for delivery
   problems and a targeted note for a verified pronunciation issue. After a take
   exists, fix only the wrong word: retake with a cue or splice that word,
   never re-voice the whole clip. See [repairs](references/repairs.md).
6. **Keep spoken words separate from guidance.** Copy dialogue inside
   `{curly braces}`. Put accent, pronunciation and acting notes outside braces
   unless the user asks to change the spoken text.
7. **Review what was produced.** Directions are requests, not guarantees.
   Compare a transcript against the approved words and listen for pronunciation,
   speaker and register. Unavailable evidence stays unresolved.

## Reference loading

| Need | Same-skill reference |
| --- | --- |
| Supported-language check and unsupported routes | [Language support](references/language-support.md) |
| Register, accent, code-switching and subtitles | [Register and accent](references/register-and-accent.md) |
| Word-scoped retakes, splices and verification | [Repairs](references/repairs.md) |
| Creating a language or market pack | [Market pack template](references/market-pack-template.md) |

## Minimal native-audio form

```text
Dialogue language: <language, regional variety, register>.
<Speaker> addresses <addressee> to <immediate intent>, using <observable delivery>.
<Speaker> says: {<exact approved dialogue>}
Pronunciation note, only if needed: <specific evidence-backed target or clearly
identified hypothesis; this note is not spoken dialogue>.
```

Use enough direction to make the line playable. Do not pad every line with a
pronunciation dictionary or invented syllables. Timing stays event-relative
unless the user or a synchronization point calls for timestamps.

## Model and review boundaries

Tool and model capability evidence decides language availability, reference
support, resolution and parameter values. This skill does not switch models
because of a language or a pronunciation concern. Return an unsupported or
unverified requirement to the caller instead of inventing support.

The caller owns production authorization, approved references, the exact
request hash and complete prompt review. New text is a draft until the user
accepts it. Unknown submission outcomes are reconciled, not duplicated.
