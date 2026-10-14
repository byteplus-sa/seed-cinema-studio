# Input Format

Read [the entrypoint](../SKILL.md).

## Dialogue JSON

The workspace has no structured per-line timing record: shot manifests hold the
locked dialogue, and takes and Studio hold durations and start times. Keep one
small JSON per clip, or one per episode, under `projects/<slug>/subtitles/`.

```json
{
  "schema_version": 1,
  "offset_s": 14.2,
  "lines": [
    {
      "id": "s02-l01",
      "speaker": "Ana",
      "start_s": 1.1,
      "end_s": 3.4,
      "text": {
        "en": "You knew all along.",
        "es": "Lo sabias todo el tiempo."
      }
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `schema_version` | Must be `1` |
| `offset_s` | Optional. Where this file's time zero sits on the master timeline |
| `lines[].id` | Optional stable id, used in warnings. Defaults to `line-NNN` |
| `lines[].speaker` | Required, nonempty. Not printed in the sidecar |
| `lines[].start_s`, `end_s` | Numbers, seconds, relative to the file's zero; `end_s` after `start_s` |
| `lines[].text` | Object keyed by language code: the locked text per language |

Final time = `start_s` + `offset_s` + the command-line `--offset-s`. Use the
file's `offset_s` for a clip's position and the flag for a uniform shift such
as a title card inserted ahead of everything.

## Where each value comes from

| Value | Source |
| --- | --- |
| `text` | The shot manifest's locked dialogue (the words inside the braces) and the approved translations from the brief or localization pass |
| `start_s`, `end_s` | Speech-to-text segment or word times on the placed take, in the take's own clock; confirm by listening |
| `offset_s` | The clip's `data-start` on the main timeline in `studio/index.html`, or the position recorded in the render. Never the sum of planned durations: dissolves overlap clips |

When a clip is split on the timeline (for example a cold open lifted ahead of
the title card), write one file per piece with its own `offset_s`.

## Output behavior

- Cues are sorted by start time. Overlaps are trimmed to the later cue's start
  minus the gap (`--overlap error` stops instead).
- Short cues are extended toward the minimum duration and reading-speed need,
  never past the next cue or the master duration.
- A cue longer than the maximum duration, or with more text than fits the line
  limits, is split at clause punctuation or token boundaries with time shared
  by text length.
