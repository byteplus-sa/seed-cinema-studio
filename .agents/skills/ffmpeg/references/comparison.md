# Video comparison

Build a separate review copy; preserve the source takes and their audio masters.
These recipes adapt the upstream FFmpeg comparison workflow without requiring
another skill. They compare simultaneous playback, rather than joining scenes.

## Before and after

Put before on the left and after on the right, preserving their aspect ratios
inside equal 640×360 cells. Both inputs start at zero and run at 30 fps.
`shortest=1` ends the comparison when the shorter video finishes. Only the
**after** soundtrack is heard; padding its audio avoids an early cutoff if that
stream is shorter than its video. `-n` refuses to overwrite an existing output.

```bash
ffmpeg -n -i before.mp4 -i after.mp4 -filter_complex "[0:v]setpts=PTS-STARTPTS,fps=30,scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v0];[1:v]setpts=PTS-STARTPTS,fps=30,scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v1];[v0][v1]hstack=inputs=2:shortest=1[v];[1:a:0]asetpts=PTS-STARTPTS,apad[a]" -map "[v]" -map "[a]" -shortest -c:v libx264 -crf 23 -preset fast -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart compare.mp4
```

Probe audio streams before running. If after has no audio, or the comparison
should be muted, remove its audio filter and `-map "[a]"`, then use `-an`.
To hear before instead, select `[0:a:0]`. Never mix both tracks implicitly.
For a vertical arrangement, replace `hstack` with `vstack`; the result is
640×720 rather than 1280×360.

## Four-take grid

This muted 1280×720 grid uses the same cell normalization and shortest-video
policy. Input order is top-left, top-right, bottom-left, bottom-right.

```bash
ffmpeg -n -i a.mp4 -i b.mp4 -i c.mp4 -i d.mp4 -filter_complex "[0:v]setpts=PTS-STARTPTS,fps=30,scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v0];[1:v]setpts=PTS-STARTPTS,fps=30,scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v1];[2:v]setpts=PTS-STARTPTS,fps=30,scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v2];[3:v]setpts=PTS-STARTPTS,fps=30,scale=640:360:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1[v3];[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0:shortest=1[v]" -map "[v]" -an -c:v libx264 -crf 23 -preset fast -pix_fmt yuv420p -movflags +faststart grid.mp4
```

## Duration policy and verification

Choose shortest playback above, or explicitly freeze shorter inputs to a shared
end time. For a freeze policy, measure each video-stream duration, choose a
shared duration `T`, and append `tpad=stop_mode=clone:stop_duration=T,trim=duration=T`
to **every** normalized video branch before stacking, replacing `T` with the
measured numeric seconds. This pads enough frames and then trims every cell to
exactly the same endpoint; it does not slow down the action. Keep the chosen
audio track padded and bound the output with `-t T`, or mute it. Record that the
comparison contains frozen tails so reviewers do not mistake them for defects.

Probe each input and the output, then decode the complete comparison:

```bash
ffprobe -v error -show_entries stream=codec_type,width,height,sample_aspect_ratio,r_frame_rate,duration -of json compare.mp4
ffmpeg -v error -i compare.mp4 -f null -
```

Check dimensions, square pixels, 30 fps, duration against the chosen policy,
and exactly one audio stream or none. Watch the review copy to confirm bars,
cell order and the selected soundtrack. A grid supplements individual-take
review and cannot establish lip sync or approval by itself.
