# Quickstart

Render a 24-second three-shot pilot from scratch in about 5 minutes.

## 0. Requirements

- Python 3.11 or newer
- [`ffmpeg`](https://ffmpeg.org/download.html) on `$PATH`
- An xAI API key — get one at <https://x.ai/api>. Pricing is per-second
  of generated video; the pilot below costs about $0.50.
- Optional: [`uv`](https://docs.astral.sh/uv/) for faster installs

## 1. Install

```sh
git clone https://github.com/MiloworksTV/MiloworksTV miloworks
cd miloworks
uv sync               # or: python -m venv .venv && source .venv/bin/activate && pip install -e .
```

## 2. Add your API key

```sh
cp .env.example .env
# Edit .env, paste your XAI_API_KEY=
```

## 3. Try the bundled example

```sh
miloworks --project examples/milo serve
```

Open <http://127.0.0.1:8765>. You'll see the Milo show's three episodes
already rendered (cached from disk). Click any one to land in the day
editor: a 3×2 grid of the rendered shots, the seed image used for each,
and a "re-render" button per scene.

This is the day-to-day Milo workflow: a daily manifest is authored,
each shot is rendered, anything that comes out wrong gets rerolled
inline, then `stitch episode` fuses the six shots into `final.mp4`
with the music track mixed on top.

## 4. Make your own show

```sh
miloworks init my-show
cd my-show
cp .env.example .env       # add the same XAI_API_KEY
miloworks characters ep00-pilot
miloworks run ep00-pilot
miloworks serve
```

`miloworks init` scaffolds a starter project: a stub `style_bible.md`,
a `characters.yaml` with one example character, a three-shot pilot
manifest, and an empty `episodes/`/`music/`. Edit any of those files
and re-run.

## What just happened

```
my-show/
├── style_bible.md
├── characters.yaml
├── episodes/
│   └── ep00-pilot/
│       ├── manifest.yaml          # the script
│       ├── characters/            # generated reference PNGs
│       └── output/
│           ├── scenes/01/{video.mp4, last_frame.png, prompt.txt, meta.json}
│           ├── scenes/02/...
│           ├── scenes/03/...
│           ├── final.mp4          # ffmpeg-stitched, music-mixed
│           └── last_frame.png     # handoff to next episode
└── music/
```

The `output/` folder is fully derived from the inputs: delete it and
re-run, you get the same result (modulo the AI's randomness). It's
gitignored by default.

## Next

- [`manifest_schema.md`](manifest_schema.md) — every field of the manifest
- [`creating_a_show.md`](creating_a_show.md) — how chain-frame shows are designed
- [`api_keys.md`](api_keys.md) — switching to fal.ai (Kling) or Wan 2.2
