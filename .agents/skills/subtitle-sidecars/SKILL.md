---
name: subtitle-sidecars
description: Write multilingual SRT and WebVTT from locked text and measured timing. Use for film, short or episode sidecars. Do not use for translation, transcription or burned-in captions.
---

# Subtitle Sidecars

Act as an independent leaf. Write subtitle sidecars only; never invoke sibling
skills, translate, transcribe, generate media, alter a master or approve
delivery. Read the [shared subtitle contract](../../contracts/subtitle-sidecars.md).

## Inputs

Require a master stem, requested language codes, explicit delivery limits and
one or more schema-version-1 dialogue JSON files. Each file supplies `offset_s`
and nonempty `lines` containing speaker, stable ID, measured `start_s`/`end_s`
and locked text keyed by language code. Keep source JSON and source masters
intact. The script checks input shape, not whether timing was really measured.

## Procedure

1. Confirm which exact master hash the timings describe and that the supplied
   text is locked or an approved translation. A heard wrong word is a take
   defect; never silently substitute it into subtitles.
2. Use measured placement offsets, not summed planned scene lengths. For
   unit-local delivery, use that unit's clock. For an explicitly requested
   combined timeline, add each unit's measured start to its clip offsets once.
3. Select limits from the brief/platform. Compatibility defaults are 32 Latin
   characters per line, two lines, 17 characters/second, 1-7 second cues and
   40 ms gaps; CJK defaults are language-specific. Horizontal delivery may
   explicitly choose 42 characters and 20 characters/second, but aspect alone
   neither selects a format nor establishes a platform specification.
4. Run the script. It uses the same engine as the retained
   `microdrama-subtitles` command, not a second implementation.
5. Inspect every warning. Overlap trimming, short/fast cues and broken
   unspaced runs are defects to resolve or explicitly document. For strict
   timing, use `--overlap error`. Thai without spaces needs supplied U+200B
   word boundaries; the engine is not a dictionary segmenter.
6. Inspect the output against the exact master in the target player, including
   every non-Latin or mixed-direction language. Record real evidence or mark
   player review `unverified`. Script success is not listening or creative QA.

```bash
uv run python .agents/skills/subtitle-sidecars/scripts/make_subtitles.py \
  --input projects/<slug>/subtitles/scene-100.json \
  --master-stem short_master_v01 --language en --format both \
  --max-chars 42 --max-cps 20 --master-duration-s 7200 \
  --out-dir projects/<slug>/subtitles/out
```

## Outputs

Return `<master-stem>.<language-code>.srt` and optional `.vtt`, and the JSON
stdout report with hashes, cue counts and warnings. Never overwrite a sidecar
unless explicitly requested; use a new version stem normally. The writer
rejects source aliases and symlink/hardlink targets even with `--overwrite`.
Unavailable timing or missing language text blocks the relevant delivery;
never invent it. No-speech work has no dialogue sidecar unless another caption
requirement is supplied.
