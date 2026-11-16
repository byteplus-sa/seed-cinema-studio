# Video Editing

Focused reference for `seedance-prompt`. Read [the entrypoint](../SKILL.md) for
mode selection and caller responsibilities.

- [Video editing](#video-editing)

## Video editing

When editing, first define the source video as the **sole editing master**, then
specify edit target, scope, target material, and content to preserve. Treat the
patterns below as 2.5-based authoring conventions, not a promise of exact output.
Verify operation, source roles, syntax and auto-locked parameters for the
selected exact model and destination.

Preserve the full measured source: fractional duration, frame count, fps,
timestamps, cuts, final word and audio tails. Missing or malformed measurements
remain unresolved; prompt-only writing may label these gaps but cannot invent
timing evidence. A provider tolerance does not relax the source lock. No
rounding, trim, pad, retime, automatic probe or derivative is authorized here.
Any required adaptation needs current provider evidence and explicit derivative
adaptation approval, recording source and derivative hashes, exact window,
timing delta and audio consequences. Denied or missing approval leaves the
original unchanged. Output mismatch is unresolved, never hidden with `-shortest`.

The caller applies the workspace
[video-to-video inputs contract](../../../contracts/video-to-video-inputs.md):
source rights, independent identity/voice authorization, an eligible source,
and the authorized muted-master/post-audio route outside explicit native audio
edits. Muting a submission derivative does not discard or shorten the approved
soundtrack. A raw-person rejection is not permission to disguise an input.
Narrower edit families retain `seedance-object-swap`, `seedance-motion-recast`
and `seedance-restyle`; the caller owns composition and execution.

### General editing pattern

```
[Edit Goal]
Edit @Video 1. Within <the entire video or a specific time range>,
<add, remove, replace, or adjust> <visual object, region, or audio category>.

[Source Video Role]
@Video 1 is the sole editing master. It defines <characters, scene, actions, composition,
camera movement, occlusion relationships, audio, and event order>.

[Target Material Role]
@Image 1 or @Audio 1 defines <specified attributes of the target object or sound>.

[Edit Scope]
Modify only <object, region, time range, or audio category>.

[Content to Preserve]
Keep <visual content, motion, audio, and timing relationships that must not change> from @Video 1.
```

### Subject replacement with Timeline Inheritance

The target object **inherits every appearance, motion, occlusion, and exit** of
the original object, including timing, duration, path, and speed changes.

```
[Edit Goal]
Edit @Video 1. Change only <original object> to <target object>.

[Source Video Role]
@Video 1 is the sole editing master. It defines the original scene, camera position, camera
movement, motion path, occlusion relationships, and event order.

[Target Reference Role]
@Image 1 defines <target object>'s <appearance, structure, or material>. Do not use <irrelevant
background, people, or composition>.

[Edit Scope]
Modify only <specific object and area>. The entire video contains <number> target object(s).
Do not modify <content to preserve>.

[Timeline Inheritance]
<Target object> inherits every appearance, motion, occlusion, and exit of <original object>,
including timing, duration, path, and speed changes.
Except for the object or area explicitly modified above, keep all other people, props, scene
content, camera movements, cuts, and event order from @Video 1 unchanged.
```

### Background replacement

Swap the background while preserving the subject's silhouette, identity, motion,
and occlusion relationships.

```
[Edit Goal]
Edit @Video 1. Replace only <original background area> with <target environment> from @Image 1.

[Source Video Role]
@Video 1 is the sole editing master. It defines the people, foreground objects, actions,
composition, camera movement, and event order.

[Target Reference Role]
@Image 1 defines only <target environment>'s spatial layout, materials, depth of field, ambient
color, and lighting direction. Do not use the people or foreground objects in the image.

[Edit Scope]
Modify only <background outside the subject's silhouette>. Do not modify <subject identity, facial
features, hairstyle, clothing, expression, position, size, or motion>.

[Timeline Inheritance]
Keep the character actions and occlusion relationships from @Video 1. Except for the modified
area, keep all other content from @Video 1 unchanged.
```

### Audio editing

When independently verified for the selected operation, request changes to
dialogue, language, voice, background music or sound effects separately from
visuals. Specify exact layer ownership and keep unselected layers unchanged.
The examples below assume the requested language change is authorized; language
or lip-sync support is not inferred from their wording.

```
Edit @Video 1. Remove only the original background music. Keep the character dialogue, lip sync,
ambience, and action sound effects; preserve the visuals, camera treatment, and editing rhythm
from @Video 1.

Edit @Video 1. Change <Presenter>'s spoken language to natural American English while preserving
the dialogue content and speaking times. Keep all other character voices, background music,
ambience, and visuals from @Video 1.
```

For the full language-swap pattern (English ⇄ Chinese/Japanese, re-lip-sync with
visuals locked), treat it as a video edit that keeps the picture and replaces the audio, and
follow the [video-to-video inputs contract](../../../contracts/video-to-video-inputs.md).
