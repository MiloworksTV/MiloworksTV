# Manifest schema

A *manifest* is a YAML file describing one episode. It lives at
`episodes/<slug>/manifest.yaml` and is the only thing the runner needs
to produce a finished `final.mp4`.

```yaml
slug: ep00-pilot                      # must match the folder name
title: "My Show — Pilot"
logline: >-
  One sentence describing what happens.
aspect_ratio: "16:9"                  # default 16:9
resolution: "720p"                    # default 720p; backends accept 480/720/1080

# Optional: chain from a previous episode's handoff frame.
prev_episode: "ep00-pilot"            # slug of the previous episode
handoff_scene: "06"                   # which scene's last frame is this episode's handoff

# Optional: post-mix music. Track name resolves under the project's music/ folder.
music:
  track: my-theme                     # finds my-theme.mp3 / .ogg / .wav / .m4a / .flac
  volume_db: -2
  fade_in_s: 1.5
  fade_out_s: 3.0
  start_offset_s: 0.0

scenes:
  - id: "01"
    mode: image | reference | text | extend
    duration: 8                       # seconds; 5–14 typical
    prompt: >-
      The shot description. Concrete, visual, specific.
    audio: >-
      Optional sound-design block. Backends that generate audio (xAI)
      use this; backends that don't (Wan) ignore it.
    # mode-specific fields below
```

## Scene modes

### `mode: image`

Image-to-video. The seed is the last frame of another scene (or another
episode's handoff frame).

```yaml
- id: "02"
  mode: image
  image_from: "01"            # seed = last_frame of scene 01
  duration: 8
  prompt: >-
    Same field as before. Hero turns to camera.
```

Special values:

- `image_from: "_prev_episode"` — seed from the previous episode's
  `output/last_frame.png`. Requires `prev_episode:` at the top level.
- `seed_image: "path/to/file.png"` — seed from an arbitrary image
  on disk (relative to the episode dir or absolute).

Optional end-frame anchor (Wan FLF2V only):

```yaml
  end_frame_from: "03"        # interpolate toward last_frame of scene 03
  # or
  end_frame: "path/to/end.png"
```

### `mode: reference`

The seed is one or more character reference PNGs from the project's
`characters.yaml`. Use this for scenes introducing a new character or
to lock character likeness.

```yaml
- id: "01"
  mode: reference
  reference_chars: [hero, sidekick]
  duration: 8
  prompt: >-
    Hero and sidekick walk into frame from the left.
```

### `mode: text`

Text-to-video. No seed. Used for opening title cards, abstract
transitions, or anything that doesn't need to chain. Not supported by
the Wan backend.

```yaml
- id: "00-title"
  mode: text
  duration: 5
  prompt: >-
    A solid black title card. Chunky white serif text reads "MY SHOW".
```

### `mode: extend`

Append-to-video. The seed is another scene's full mp4 (xAI only).
Useful for pushing past the per-call duration cap on a single sustained
take.

```yaml
- id: "04b"
  mode: extend
  extend_from: "04"
  duration: 8
```

The runner trims the source-duration off the head of the result so you
end up with just the extension on disk.

## Top-level fields

| Field | Type | Notes |
|---|---|---|
| `slug` | string, required | Must match the folder name. |
| `title` | string, required | Human-readable. |
| `logline` | string | One-sentence summary, used by the studio UI. |
| `aspect_ratio` | string, default `"16:9"` | Backend-specific support. |
| `resolution` | string, default `"720p"` | `"480p" \| "720p" \| "1080p"`. |
| `prev_episode` | string | Slug of the previous episode for cross-episode chaining. |
| `handoff_scene` | string | Which scene's last frame becomes this episode's handoff PNG (default: last scene). Set explicitly when the episode ends on a non-narrative shot like an outro card. |
| `music` | mapping | Optional post-mix score, see below. |
| `scenes` | list, required | Ordered list of scene mappings. |

Anything else at the top level is ignored by the runner — handy for
operational metadata your team uses (e.g. `day:`, `weekday:`,
`bucket:`, `concept:`, `form_drift_state:` in the Milo example).

## Music block

```yaml
music:
  track: my-theme              # filename in music/, with or without extension
  volume_db: -2.0              # default -2
  fade_in_s: 1.5
  fade_out_s: 2.5
  start_offset_s: 0.0          # offset into the track
```

When `music:` is present, the stitch step **replaces** the model-generated
audio entirely with the named track. xAI bakes audio into every clip but
its lip-sync is unreliable; this gives you a consistent score across
every episode without depending on the model's audio.

## Prompt assembly

Each scene's prompt is composed at render time as:

```
<style_bible.md, full text>

---

SHOT:
<scene.prompt>

---

AUDIO:
<scene.audio>          # only if non-empty
```

The composed prompt must fit under **4096 bytes** (the xAI API limit).
The runner enforces this and tells you which scene overflows. Note
that multi-byte UTF-8 characters like em-dashes (—) cost 3 bytes each.

The Wan backend skips the AUDIO block (Wan is silent). The fal/Kling
backend drops the style bible at i2v time (it caps prompts at 2500
chars and the seed frame already carries style continuity).

## Caching

- Scene videos are cached at `output/scenes/<id>/video.mp4`. Re-running
  `miloworks run` skips any scene whose video and `meta.json` already
  exist. Pass `--force` (or click "re-render" in the studio UI) to
  regenerate.
- The studio UI flags `final.mp4` as **stale** when any scene's mtime
  is newer than the final's mtime, so you never accidentally publish
  a stitched reel that's missing your latest reroll.
