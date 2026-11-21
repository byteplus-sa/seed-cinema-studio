---
name: media-review
description: >
  Emergency CLI fallback for opening generated images or videos in macOS when
  Studio preview or the pre-Studio canvas is unavailable, or when the user
  explicitly requests an OS-native player. Never use it as production-stage
  review evidence: project workflows require the Studio stage-exit checks (or,
  for a pre-Studio canvas project with showcase.json, the showcase-html freshness check).
---

# Media Review

> **Fallback only.** Project workflows review shot takes in HyperFrames Studio
> and everything else from its manifests at every stage (pre-Studio canvas projects with `showcase.json` keep the `showcase-html` canvas);
> see the [production policy](../../contracts/production-policy.md). Use this
> skill only when the Studio preview or pre-Studio canvas is unavailable or the user
> explicitly requests the OS default player. Record the unavailable-surface
> evidence and restore it before the stage exits; this fallback never satisfies
> the stage checkpoint.

Help the user visually review generated media assets on macOS. Since the agent
runs in a CLI with no graphical display, the practical way to let the user
compare assets is to open them via the operating system's default apps.

## Core principle

- **Images** → build contact sheets (montages) so many variants can be compared
  in a single view, and/or open them directly.
- **Videos** → open them directly in the default player. **Do NOT extract
  keyframes** to build contact sheets — just open the video files so the user
  can play them.

## Opening files

Use the macOS `open` command to launch the default apps:

```bash
open path/to/file.mp4
```

Open multiple assets at once (each opens in its own window):

```bash
open variant_a.mp4 variant_b.mp4 variant_c.mp4
```

To force a specific app (optional):

```bash
open -a "QuickTime Player" file.mp4
open -a Preview file.png
```

## Contact sheets for images

To compare many image variations at once, build a montage/contact sheet with
Python (PIL). This puts all variants in a single image with labels.

### Contact sheet helper

```python
from PIL import Image, ImageDraw

def contact_sheet(images, labels, out, cols=3, cell_pad=10, header_h=60, bg=(255,255,255)):
    if not images or len(images) != len(labels) or cols < 1:
        raise ValueError("Supply an image and label per cell and at least one column")
    width = max(image.width for image in images)
    height = max(image.height for image in images)
    rows = (len(images) + cols - 1) // cols
    row_height = header_h + height + cell_pad
    sheet = Image.new("RGB", (cols * (width + cell_pad) + cell_pad, rows * row_height + cell_pad), bg)
    draw = ImageDraw.Draw(sheet)
    for index, (image, label) in enumerate(zip(images, labels)):
        row, column = divmod(index, cols)
        x = cell_pad + column * (width + cell_pad)
        y = cell_pad + row * row_height
        draw.text((x, y), label, fill="black")
        sheet.paste(image, (x, y + header_h))
    return sheet

def sheet_from_paths(paths, labels, out):
    imgs = [Image.open(p) for p in paths]
    contact_sheet(imgs, labels, out).save(out)
```

### Typical usage

```bash
# Build and open a contact sheet comparing 3 map variants
python3 - <<'EOF'
from PIL import Image
# (use the helper above, or inline)
EOF
open _review_sheet.png
```

## Workflow

1. **Confirm what to review** — which assets and whether image or video.
2. **Images**: build a labeled contact sheet (all variants in one view) and open
   it. Optionally also open the individual files.
3. **Videos**: open the files directly with `open`. Do not extract keyframes.
4. Tell the user the file paths and ask which variant they prefer.
5. If this is project work, return the result to the orchestrator so it can add
   the files and decision to the manifests, run `studio_project.py sync` and the
   stage-exit checks (pre-Studio canvas projects: regenerate the canvas and pass its
   freshness check).

## Notes

- Works on macOS (uses `open`, `sips`, and Python PIL).
- Contact sheets preserve the original images unchanged — they only composite
  copies into a labeled grid for viewing.
- Clean up any throwaway `_review_*.png` sheets after the user has decided
  (CLAYGO), unless the user wants to keep them.
- For video before/after comparison clips, compose with `ffmpeg`.
