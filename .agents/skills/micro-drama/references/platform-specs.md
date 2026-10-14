# Platform Specs

Read [the entrypoint](../SKILL.md) and the [market card](market-card.md). The
optional market card's `platform` field names where the series will be posted.
This reference turns that name into a verified delivery checklist. It carries no
platform numbers on purpose: platform requirements change, differ by region and
account type, and are not sourced from files in this repository.

## Rules

- **Never assume a platform.** When the card has no `platform` value, ask which
  platform and account type will receive the master before the delivery stage.
  A series with no stated platform keeps the defaults the repository already
  guarantees (see below) and records that no platform was confirmed.
- **Verify at posting time.** The user names the platform; the agent reads the
  platform's current official documentation (creator help centre, upload
  specification or ad specification page) and records each value with its source
  URL and the date it was read. Do not rely on memory, earlier projects, other
  episodes or third-party summaries.
- **Recheck before every new delivery batch.** Specs change. A value confirmed for
  episode 1 is stale by a later release unless it is rechecked and the date
  updated.
- **Unconfirmed means unknown.** If the documentation cannot be read, is gated
  behind a login, or does not state an attribute, record `not confirmed` and ask
  the user. Do not fill the gap with a plausible figure.
- **Platform limits are inputs, not overrides.** A confirmed limit may change the
  episode length, aspect or loudness target. Record the change in `project.md`
  and revalidate the Studio render; it never relaxes a hard gate such as the
  text-free generated footage rule.

## Attributes to confirm per platform

| Attribute | What to confirm |
| --- | --- |
| Aspect ratio | Supported ratios and the one the platform prefers for vertical video |
| Resolution | Minimum, recommended and maximum frame size |
| Length limits | Minimum and maximum duration per video, and any series or episode duration guidance |
| File size | Maximum upload size per file and per account type |
| Container and codec | Accepted containers, video codec, audio codec, frame rate and bitrate guidance |
| Loudness | Any stated loudness or true-peak target, or none |
| Captions and subtitles | Whether sidecar files are accepted, accepted formats, whether hard-coded captions are expected, and language handling |
| Safe zones | Regions where the platform's own interface covers the picture (caption text, buttons, progress bar, profile name), expressed as the platform documents them |
| Cover or thumbnail | Whether a custom cover is accepted, its size and ratio, and where in the video a frame can be chosen |
| AI-generated-content label | Whether disclosure is required, the mechanism (upload toggle, metadata field, on-screen text), and the wording the platform requires |
| Posting cadence | Any documented limits on uploads per period or release scheduling for series |
| Content limits | Platform rules that touch violence, romance, minors or themes in the market card's `content_limits` |
| Rights and monetization | Rules for synthetic voices, likeness and music that affect the distribution of generated media |

Add any attribute the platform's own documentation lists that this table omits.

## What the repository already guarantees

These are production defaults, not platform facts. Confirm each against the
platform before treating it as accepted.

| Area | Guarantee | Source |
| --- | --- | --- |
| Master format | 1080x1920 H.264/AAC unless the market card sets another aspect | [micro-drama entrypoint](../SKILL.md) |
| Codec compatibility | H.264 masters, because some platforms play HEVC poorly | [production recipe](production-recipe.md) |
| Loudness | Every delivered episode normalized to one loudness target, for example -16 LUFS integrated and -1.5 dBFS peak; the example is a project choice, not a platform number | [production recipe](production-recipe.md) |
| Captions | Generated footage stays text-free; titles, cards and subtitles are added in post, with a sidecar per language named `<master-stem>.<language-code>.srt` | [micro-drama entrypoint](../SKILL.md), [production recipe](production-recipe.md) |
| Safe margins | Everything visible stays inside the action-safe box (90% of the frame, 5% inset per edge); captions and key content stay inside the title-safe box (80%, 10% inset per edge) | [hyperframes-studio](../../hyperframes-studio/SKILL.md) section 4 |
| Final files | Only `studio_project.py render` produces the delivered master; post work made elsewhere is placed in Studio and rendered | [production policy](../../../contracts/production-policy.md) |

The Studio safe boxes are generic broadcast-style margins. They are not the
platform's interface overlay regions. When the platform documents its overlay
regions and they are larger than the title-safe box, move captions and key
content out of those regions in the Studio composition and re-render.

## Procedure

1. Read `market.platform` in `projects/<slug>/project.md`. If it is absent or
   vague, ask the user which platform and account type will receive the master.
2. Open the platform's current official documentation for each attribute in the
   table above. Prefer the creator or advertiser specification page over a
   forum post or third-party article.
3. Record every confirmed value, its source URL and the date read in the table
   template below, inside the project's `handoff.md`. Use `not confirmed` for
   anything the documentation does not state.
4. Compare the confirmed values with the repository guarantees. List each
   mismatch and decide with the user whether to change the render settings, the
   episode length or the loudness target.
5. Apply any change in the Studio project, render again with
   `studio_project.py render`, and run the delivery `check` before
   `stage complete delivery`.
6. Before delivery of a later batch, repeat steps 2 to 5 for the changed or
   expired rows only, and update the read dates.

## Handoff table template

Copy into `handoff.md` and fill from the platform's documentation.

```markdown
## Platform delivery specs

Platform: <name from market.platform>
Account type or region: <as stated by the user>
Last verified: <date>

| Attribute | Confirmed value | Source URL | Date read | Repository default | Action |
| --- | --- | --- | --- | --- | --- |
| Aspect ratio | | | | 9:16 unless the card sets another | |
| Resolution | | | | 1080x1920 | |
| Length limits | | | | per episode structure | |
| File size | | | | none set | |
| Container and codec | | | | H.264/AAC | |
| Loudness | | | | one project target | |
| Captions and subtitles | | | | sidecar SRT per language | |
| Safe zones | | | | title-safe 80%, action-safe 90% | |
| Cover or thumbnail | | | | none set | |
| AI-generated-content label | | | | none set | |
| Posting cadence | | | | none set | |
| Content limits | | | | market card content_limits | |
```

Set Action to `none`, `re-render`, `retime`, `renormalize` or `ask user`.
