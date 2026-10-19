---
name: microdrama-subtitles
description: Write multilingual SRT and WebVTT for micro-drama from locked text and measured timing. Use for episode subtitle sidecars. Do not use for translation, generation or burned-in captions.
---

# Microdrama Subtitles

Turn locked dialogue plus measured timing into one subtitle sidecar per
language. The skill owns the file format, wrapping and timing rules; it does not
translate, listen, or render video.

This independent leaf is the retained micro-drama compatibility entry. Follow
the [shared subtitle contract](../../contracts/subtitle-sidecars.md). The
generic `subtitle-sidecars` script calls this same engine; neither leaf loads
or invokes its sibling. Existing flags, input schema and valid output bytes
remain supported, including explicit horizontal limits and long offsets.
The writer preflights all requested languages and targets before writing and
rejects source-input aliases and symlink/hardlink targets even with `--overwrite`.

## Input and output contract

Input: a dialogue JSON per clip (or one for the episode) that lists each spoken
line with speaker, `start_s`, `end_s` and the locked text for every requested
language; the master stem; the languages from the market card's
`subtitle_languages`; the clip's start on the master timeline when the file is
clip-relative. The format and the places timing comes from are in
[input format](references/input-format.md).

Output: `<master-stem>.<language-code>.srt` per language (and `.vtt` when
requested) next to the master, plus a JSON report with cue counts, SHA-256 per
file and every timing warning.

## Rules

1. **Locked words, not heard words.** Take text from the locked dialogue or its
   approved translation. A speech-to-text transcript supplies timing only. If
   the take said a different word, fix the take or record a defect; do not edit
   the subtitle to match it.
2. **Never burned in.** Generated footage stays text-free. The sidecar is the
   delivered subtitle; an on-screen caption is a separate Studio overlay the
   user asks for.
3. **Timing is measured, not planned.** Use the heard start and end of each
   line on the final timeline (see the reference), not the prompt's planned
   seconds. Apply the clip's Studio start as the offset.
4. **One file per language, one naming scheme.** Language codes are lowercase
   BCP 47 tags (`en`, `pt-br`, `zh-hans`). The stem is the delivered master's
   stem. Existing sidecars are not overwritten; write a new version stem or
   pass `--overwrite` on purpose.
5. **Never split a word or a grapheme cluster.** Breaks fall at spaces,
   U+200B, and between CJK characters (not before closing punctuation or after
   opening punctuation). Scripts written without spaces and without a
   dictionary, such as Thai, need U+200B at word boundaries in the locked
   text; otherwise the script splits an overlong run and warns.
6. **Right-to-left text.** Each line gets a leading U+200F mark for
   right-to-left languages so punctuation sits on the correct side in basic
   players. Arabic and Hebrew WebVTT output, including mixed digits and
   punctuation, was inspected in Chromium's native track rendering on
   2026-10-14 and displayed correctly. Other players and mobile apps are not
   verified; inspect the result in the target player.
7. **Limits are conservative defaults, not platform requirements.** Defaults:
   32 characters per line (16 for `zh` and `ko`, 13 for `ja`), two lines,
   17 characters per second (9 for `zh`, 7 for `ja`, 12 for `ko`), cue length
   1 to 7 s, 40 ms between cues. For comparison, the published Netflix timed
   text style guides (read 2026-10-14) allow 42 characters per line and 20
   characters per second for English adult programs, 16 characters per line and
   9 per second for Simplified Chinese, 16 and 12 for Korean, 13 and up to 7 for
   Japanese, two lines, 5/6 s minimum and 7 s maximum per cue. The narrower
   Latin line here suits 9:16 video. Replace the defaults with the platform's or
   market card's numbers via the flags.
8. **Warnings are defects to look at.** Reading speed above the limit, a cue
   shorter than the minimum, a trimmed overlap and a split unbroken run are
   reported. Fix the source timing or text rather than silencing the limit.

## Workflow

1. Confirm dialogue QA has passed for the takes in the episode.
2. Write or update the dialogue JSON with timing from the final timeline.
3. Run the script (from the repository root):

```bash
uv run python .agents/skills/microdrama-subtitles/scripts/make_subtitles.py \
  --input projects/<slug>/subtitles/scene-01.json \
  --input projects/<slug>/subtitles/scene-02.json \
  --master-stem <master-stem> --language en es --format both \
  --out-dir projects/<slug>/subtitles/out --master-duration-s <duration>
```

4. Read the report and warnings. Open the sidecar against the master in a real
   player for at least one line per language, including every right-to-left or
   non-Latin language.
5. Place the sidecar beside the master as a deliverable. Record the report
   hashes in the delivery notes. Studio renders the final master; the sidecar
   is not part of that render.

## Script reference

`scripts/make_subtitles.py` is stdlib-only. Flags: `--input` (repeatable),
`--master-stem`, `--language` (one or more), `--out-dir`, `--format`
(`srt`, `vtt`, `both`), `--offset-s`, `--master-duration-s`, `--max-chars`,
`--max-lines`, `--min-duration-s`, `--max-duration-s`, `--max-cps`,
`--min-gap-s`, `--max-chars-for LANG=N`, `--max-cps-for LANG=N`,
`--overlap trim|error`, `--rtl-marks auto|on|off`, `--overwrite`. It exits 2
with a one-line error for invalid input, a missing or blank language text, a
cue past the master duration, or an existing target.

## Boundaries

This skill does not translate (the caller supplies locked text per language),
does not time speech (use speech-to-text on the take), does not burn captions
into video, and does not decide which languages ship. Compose with
`micro-drama` for the episode flow and with `microdrama-localize` when a
delivered episode gains a new language.
