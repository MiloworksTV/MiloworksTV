# MiloWorks

> Make AI shorts from chained-prompt manifests. A small, opinionated studio
> for prompt-driven cartoon and short-film series — daily episodes,
> scene-by-scene, frame chained to frame.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Site: miloworks.tv](https://img.shields.io/badge/site-miloworks.tv-7eecaa.svg)](https://miloworks.tv)

MiloWorks turns a YAML *manifest* into a finished short film. You write
the script as a list of scenes — each one a prompt, a duration, and a
seed image — and the engine renders them through a video model
(xAI Grok Imagine, Kling via fal.ai, or Wan 2.2 locally), stitches them
with ffmpeg, and optionally scores the result with a music track. The
**last frame of every shot is the seed of the next**, so a season can
be authored as one unbroken plano-secuencia across hundreds of episodes.

There are two ways to use it:

- **CLI** — `miloworks run my-episode` from a project directory, like a
  build tool. Good for batch jobs and CI.
- **Studio** — `miloworks serve` opens a local web UI at
  `http://127.0.0.1:8765`: episode dashboard, per-scene preview, reroll
  any shot with one click, stitch with one click. Files on disk stay
  the source of truth.

The repository ships with one full reference show — **Milo** — under
[`examples/milo/`](examples/milo/). Read its `series_arc.md`,
`style_bible.md`, and daily manifests to see how a long-running
chained-frame show is structured in practice. Follow Milo at
[**miloworks.tv**](https://miloworks.tv).

---

## Quick start

You'll need **Python 3.11+**, **ffmpeg**, and an **API key** for at
least one of the supported video backends.

```sh
# 1. Install
git clone https://github.com/MiloworksTV/MiloworksTV miloworks
cd miloworks
uv sync                      # or: pip install -e .

# 2. Configure
cp .env.example .env         # add your XAI_API_KEY
# get a key at https://x.ai/api

# 3. Run the bundled Milo example
miloworks --project examples/milo serve
# open http://127.0.0.1:8765 in your browser
```

To start your own show:

```sh
miloworks init my-show
cd my-show
cp .env.example .env         # add your XAI_API_KEY
miloworks serve
```

The studio web UI lists your episodes, lets you reroll individual
scenes, and stitches the final cut. Every operation reads/writes the
same files the CLI does — you can drop down to `miloworks run` at any
time.

---

## How it works

A **project** is a directory:

```
my-show/
├── style_bible.md           # show-wide style + tone, prepended to every prompt
├── characters.yaml          # reference sheets for named characters
├── episodes/
│   └── ep00-pilot/
│       ├── manifest.yaml    # the script: ordered list of scenes
│       └── output/          # rendered scenes + final.mp4 (gitignored)
├── music/                   # optional post-mix tracks
└── .env                     # API keys (gitignored)
```

A **manifest** is a YAML file with a list of scenes. Each scene names
its mode (`text` / `image` / `reference` / `extend`), its prompt, its
duration, and how it gets its seed:

```yaml
slug: ep00-pilot
title: "My Show — Pilot"
aspect_ratio: "16:9"
resolution: "720p"
handoff_scene: "03"

scenes:
  - id: "01"
    mode: reference
    reference_chars: [hero]
    duration: 8
    prompt: >-
      Establishing shot. Hero stands in a wide open field at golden hour.
    audio: >-
      Light wind, distant birds.

  - id: "02"
    mode: image
    image_from: "01"        # seed = last frame of scene 01
    duration: 8
    prompt: >-
      Same field. Hero turns to camera, raises one hand.
    audio: >-
      Continued wind. A soft fabric rustle.

  - id: "03"
    mode: image
    image_from: "02"
    duration: 8
    prompt: >-
      Hand-off frame. Camera locked, hero in default pose, world stable.
    audio: >-
      Ambient only.
```

The runner turns this into three scene videos chained frame-to-frame,
concatenates them with ffmpeg, and writes `output/final.mp4`. Daily
episodes can chain *across* episodes too via
`image_from: "_prev_episode"`, so a 365-episode season is one
continuous plano-secuencia.

See [`docs/manifest_schema.md`](docs/manifest_schema.md) for the full
reference and [`docs/creating_a_show.md`](docs/creating_a_show.md) for
the philosophy behind chained-prompt shows.

---

## Backends

| Backend | Setup | Strengths |
|---|---|---|
| `xai` (default) | `XAI_API_KEY` | Grok Imagine. Good prompt adherence, generates audio, supports text/image/reference/extend modes. |
| `fal` | `FALAI_API_KEY` | Kling 2.6 Pro via fal.ai. Strong i2v continuity. Image and reference modes only. |
| `wan` | local ComfyUI at `--wan-url` | Wan 2.2 self-hosted. Free, silent, image and FLF2V (first-and-last-frame) modes only. |

Each backend writes to its own output folder (`output/`,
`output-fal/`, `output-wan/`) so you can render the same manifest with
multiple providers and pick the best one per scene.

---

## CLI reference

```sh
miloworks init <path>                    # scaffold a new project
miloworks --project <path> <command>     # run against a specific project
                                         # (or just cd into it)

miloworks characters <slug>              # generate character reference sheets
miloworks run <slug> [--scene 03] [--force] [--backend xai|fal|wan]
miloworks stitch <slug>                  # rebuild final.mp4 from cached scenes
miloworks serve [--port 8765]            # open the studio web UI
miloworks smoke                          # 5s test render to verify your API key
```

---

## Docs

- [`docs/quickstart.md`](docs/quickstart.md) — install + first render in 5 minutes
- [`docs/manifest_schema.md`](docs/manifest_schema.md) — every field, every mode
- [`docs/creating_a_show.md`](docs/creating_a_show.md) — how to design a chained-frame show
- [`docs/api_keys.md`](docs/api_keys.md) — where to get xAI / fal / Wan running

---

## The Milo example

[`examples/milo/`](examples/milo/) contains the production show this
engine was built to make: **Milo**, a daily silent 60-second cartoon
about a shapeshifting alien blob. One episode every day for a year, all
chained as one unbroken plano-secuencia.

It's a complete reference for everything the engine can do — series
arc, weekday curriculum, form drift, sky events, daily writer prompt,
music score, cross-episode handoff. Read `examples/milo/README.md` for
the show, `examples/milo/series_arc.md` for the year-long roadmap, and
the daily manifests for working examples of every scene mode.

The show itself lives at [**miloworks.tv**](https://miloworks.tv). The
engine made the videos there. You can fork the repo and use the same
engine to make yours.

---

## Contributing

Issues and PRs welcome. The engine is small (~1500 lines of Python);
bias toward fewer abstractions and surgical changes. See `LICENSE`
(MIT).
