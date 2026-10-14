# Routes

Read [the entrypoint](../SKILL.md). Choose the lowest-cost route that meets the
user's goal and record it, with the reason, in the localization note.

## Choosing

| Situation | Route |
| --- | --- |
| The audience accepts reading subtitles over the source audio | A |
| The audience needs spoken audio in their language and the picture must stay | B |
| Lip sync in the new language matters and the user accepts new clips and cost | C |
| Target language is not on the native list and spoken audio is required | B with a verified audio tool, or C with annotation as an experiment, or an explicitly requested audio-first track |
| Budget is tight or the language is unverified | A first; upgrade later |

## A. Subtitles only

1. Translate and get the text accepted.
2. Run the subtitle script for each language from the delivered timing.
3. Place the sidecars beside the master; no new render is needed. Note the
   master hash the timing was measured against.
4. If the master is later re-rendered or retimed, regenerate the sidecars.

## B. Line-scoped re-voice, source soundtrack kept

Keep the delivered video and its soundtrack (music, effects, room tone) and
replace only the spoken lines.

1. List the lines to change and their windows. A line cannot outlast its
   window; shorten the translation instead of stretching speech.
2. Send the original video with its audio and the new text, and ask the model
   to change the words; take the full audio back. Do not send dialogue alone
   and rebuild the soundtrack by hand. Use whichever tool binding the current
   capability evidence lists for text plus video to audio (registry operation
   `text_video_to_audio`); if none is listed, say the route is unverified and
   offer reference-audio generation with authorized voices, or route A.
3. Splice the new audio onto the video in Studio as a clip or overlay and
   render a new master version. Muted-source and post-audio rules follow
   [video-to-video inputs](../../../contracts/video-to-video-inputs.md).
4. Fix wrong words one at a time with a word-scoped patch, never a second full
   re-voice. Reject a splice that needs more than about 10 percent pitch or
   tempo change.
5. Loudness-match to the delivery target in the
   [audio-video alignment](../../../contracts/audio-video-alignment.md)
   contract.

Mouths still move for the source language. Say so in the lip-sync verdict; it
is a known limit of route B, not a defect to hide.

## C. Full regenerate

New Seedance clips with dialogue in the target language.

1. Pass the language check; write the dialogue layer with
   `seedance-prompt-25-dialogue`; keep every canon binding, shot plan and
   reference from the source clips.
2. Prepare, review, register and submit as 480p drafts; select under the
   approval mode; then request final resolution as a new paid request.
3. Picture can change even with identical inputs. Treat the result as a new
   cut: re-run picture QA, continuity across clips, and the cold open window.
4. Same dialogue QA gate as the source episode: word-by-word speech-to-text
   diff against the locked target text before a take passes.

## Mixed language

When some words stay in the source language (names, forms of address, short
phrases), keep those words few and mid-sentence and subtitle the rest.
Plot-critical words should not sit at a whispered or line-initial position.
