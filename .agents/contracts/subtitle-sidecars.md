# Shared Subtitle Sidecars

This Phase 4 compatibility contract from `PLAN_SEED_CINEMA_STUDIO.md` applies
to `subtitle-sidecars` and the retained `microdrama-subtitles` leaf.
Neither leaf loads or invokes its sibling.

## One Engine, Two Commands

Both commands run the single implementation at
`.agents/skills/microdrama-subtitles/scripts/make_subtitles.py`:

```bash
uv run python .agents/skills/subtitle-sidecars/scripts/make_subtitles.py --help
uv run python .agents/skills/microdrama-subtitles/scripts/make_subtitles.py --help
```

The generic entry is a thin import adapter. Keep the old engine file and its
public functions (`load_lines`, `resolve_settings`, `build_cues`, renderers,
`main`) available. Do not copy the engine into another skill. Valid legacy
input produces the same SRT/WebVTT bytes and report shape through either path.
The engine remains stdlib-only.

## Inputs and Timing

```json
{
  "schema_version": 1,
  "offset_s": 7200,
  "lines": [
    {
      "id": "ep002-s100-line-010",
      "speaker": "Speaker",
      "start_s": 1.25,
      "end_s": 4.75,
      "text": {"en": "The source line stays exactly as locked."}
    }
  ]
}
```

Final time = measured local line time + file `offset_s` + CLI `--offset-s`.
Times must be finite numbers with end after start; the final start cannot be
negative. The master duration bounds output. There is no minute or hour cap;
timestamps retain hours on long timelines.

For independent units, call the command separately with unit-local placements.
For an explicitly requested combined master, add the measured unit start and
clip start into each file's offset once. Never sum planned shot lengths:
trims, gaps and overlaps change actual placement. Use stable, unit-qualified
line IDs across files so diagnostics and overlap handling are unambiguous.
The script does not resolve unit membership or select a Studio context.

Text comes from locked dialogue and accepted translations, not heard mistakes.
Speech timing must come from the delivered take/master and be checked by
listening. A JSON file does not prove timing was measured. No-speech work
does not fabricate a dialogue file or a dialogue gate.

## Limits

Compatibility defaults remain 32 Latin characters per line, two lines, 17
characters/second, cue durations 1-7 seconds and a 40 ms minimum gap.
Chinese defaults: 16 characters, 9 per second. Japanese: 13 and 7.
Korean: 16 and 12. These are disclosed working defaults, not platform
certification. Explicit horizontal delivery can use `--max-chars 42
--max-cps 20`; confirm the platform and language requirements instead of
inferring limits from format or aspect.

Flags remain `--input` (repeatable), `--master-stem`, `--language`,
`--out-dir`, `--format srt|vtt|both`, `--offset-s`, `--master-duration-s`,
`--max-chars`, `--max-lines`, `--min-duration-s`, `--max-duration-s`,
`--max-cps`, `--min-gap-s`, `--max-chars-for LANG=N`, `--max-cps-for LANG=N`,
`--overlap trim|error`, `--rtl-marks auto|on|off`, and `--overwrite`.

Wrap at words, supplied U+200B and CJK boundaries, preserving grapheme clusters.
Unspaced scripts without supplied word boundaries can split and warn; this is
not dictionary-based segmentation. RTL auto mode marks lines for relevant
language/script tags, but target-player mixed-direction rendering still needs
visual inspection.

## Outputs and Preservation

Write `<master-stem>.<lowercase-language-code>.srt` and optional `.vtt`. JSON
stdout has `files` with path/language/format/cue-count/SHA-256 and `warnings`.
Exit 2 reports invalid input or output conflicts.

All requested languages and targets are preflighted before writing. A missing
later language cannot leave an earlier language's partial delivery. Existing
targets require explicit `--overwrite`; symlink/hardlink targets and dialogue
input aliases are refused even with that flag. File-open guards protect the
leaf target. This is not a multi-file filesystem transaction: disk failures
during writing can still leave some new files. Inspect and reconcile them;
never regenerate media as a response.

The script never opens a master for writing, transcribes, translates, burns
captions or claims playback approval. Keep the source master hash and timing
provenance in delivery/localization notes. Review every warning and inspect
the sidecars against that exact master in the target player. Unavailable
player or listening checks stay `unverified`.
