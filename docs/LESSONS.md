# Lessons from the first series

Source: "Dalawang Anak ng Don", 11 episodes, about 15 minutes, produced October 2026 as Seedance 2.5
480p drafts reviewed in HyperFrames Studio. These are the problems that cost the most rework.

## Audio

- Whole-clip re-voicing changed every voice; word-scoped fixes kept the performance. Fix only the wrong word.
- A replacement word from a different generated voice can differ by about 13 percent in pitch. Reject
  any splice outside roughly 0.9 to 1.1 on tempo and pitch; four such splices were heard as "voice changes".
- Check the speaker's pitch before generating samples. If no sample fits, retake the clip with a pronunciation
  cue in the Seedance prompt (for example "saying Attorney as uh-TUR-nee") instead of splicing.
- Speech-to-text hears spelling, not accent. A native listener is the authority; record which words are unverified.
- A retake discards earlier patches on that clip. Re-apply after every retake and keep a list of patches per take.
- A trimmed or word-fixed file is a derived take: record its parent, review and decision.

## Continuity and blocking

- Check where each character is across episodes before adding a bridge clip; a new beat can create a new gap
  (a character expelled in one episode and back in the kitchen in the next).
- Carry state changes forward: soaked clothing, wet hair, a broken lock.
- A location plate containing a door makes Seedance reuse that door. Give a second door its own prop plate,
  keep the plate bound as a prop, and use tight shots; text alone failed. When a clip must not show a door,
  also drop the door reference.
- Crowd scenes drift between clips. Bind a staging map to every clip of the scene and repeat identical
  atmosphere text.
- Video extension and first-frame are unavailable for generated people.
- An object that falls or appears in the last second of a clip is easy to miss; scan the last two seconds.
- When the owner cites a timestamp, recompute from the Studio start times; every new or cut clip shifts all later times.

## Tooling

- `studio_project.py sync` appends new frames at the end of the timeline. To insert a clip in story order,
  delete `index.html`, `STORYBOARD.md`, `compositions/*.html` and `assets/s*_t01_*.mp4`, then
  `sync --take SHOT=FILE`. `place` only swaps takes within 0.25 s of the frame length.
- A Studio tab left open during a rebuild breaks with a React render-loop error; hard-refresh after rebuilds.
- Presigned reference URLs expire (four hours in this setup); refresh them before long sessions.
- The browser file-upload tool accepts under 10 MB per call. Large episode files cannot be uploaded to a
  web form by the agent; the owner selects the file and the agent fills captions and saves the draft.

## Delivery checklist

1. Studio status and check clean, every shot placed with a recorded selection.
2. Export one file per episode (1080x1920, H.264, AAC) from the placed takes.
3. Captions per episode, a cover timestamp per episode (clear face close-ups work best) and a post order.
4. Turn on the platform's AI-generated content label when posting.
5. Post three episodes on day one, then two a day; one playlist; pin a link to the next part.
