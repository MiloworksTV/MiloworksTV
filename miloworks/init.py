"""Project scaffolding for `miloworks init <name>`.

Creates a minimal but real MiloWorks project: a style bible stub, a
characters.yaml with one example character, an empty episodes/ directory
with a starter pilot manifest, an empty music/ directory, an .env.example,
and a project README.
"""

from __future__ import annotations

from pathlib import Path

# ---- Templates kept inline so the package is a single wheel install. ----

_STYLE_BIBLE = """\
SHOW: "{name}" — short description of the show.

VISUAL: Describe the look. Camera, palette, line, animation style.

WHO APPEARS: Characters appear ONLY when the SHOT below names them.

CHARACTER 1 — describe default form, mouth state, eye, posture.

WORLD: where it takes place, lighting, props.

AUDIO RULE: ambient + non-verbal SFX only, OR allow dialogue —
your call. If silent, end every audio block with the literal
'NO VOICES. NO DIALOGUE.' so the model behaves.

FORMAT: 16:9 widescreen, 2D cartoon. TONE: ...
"""

_CHARACTERS_YAML = """\
aspect_ratio: "1:1"
resolution: "1k"
characters:
  - id: hero
    prompt: |
      A standalone reference sheet of HERO, the main character of {name}.
      Solid white background, full body, neutral pose, looking at camera.
      Describe colors, outline, eye, mouth state, distinctive features.
      Keep this prompt under 4000 chars.
"""

_PILOT_MANIFEST = """\
slug: ep00-pilot
title: "{name} — Ep 0: Pilot"
logline: >-
  One sentence describing what happens in this episode.
aspect_ratio: "16:9"
resolution: "720p"

handoff_scene: "03"

# Optional: post-mix a music track from the project's music/ folder.
# music:
#   track: my-theme
#   volume_db: -2
#   fade_in_s: 1.5
#   fade_out_s: 3.0

scenes:
  - id: "01"
    mode: reference
    reference_chars: [hero]
    duration: 8
    prompt: >-
      Establishing shot. Describe the world, the character entering,
      one clear stable beat. Keep it concrete and visual.
    audio: >-
      Ambient world sounds. Specific SFX with durations.

  - id: "02"
    mode: image
    image_from: "01"
    duration: 8
    prompt: >-
      Continue from scene 01's last frame. Describe ONE small change
      (a gesture, a morph, a turn). World stays solid.
    audio: >-
      Continued ambience plus one fresh SFX.

  - id: "03"
    mode: image
    image_from: "02"
    duration: 8
    prompt: >-
      Hand-off shot. Camera locked, world stable, character in default
      pose. This frame becomes the seed for the next episode.
    audio: >-
      Ambient only.
"""

_README = """\
# {name}

A MiloWorks project. Each episode is a `manifest.yaml` describing a
short chained-prompt video. Run `miloworks serve` from this directory
to open the studio web UI, or `miloworks run <slug>` from the CLI.

## Files

- `style_bible.md` — show-wide style + tone, prepended to every prompt.
- `characters.yaml` — reference sheets for each named character.
- `episodes/<slug>/manifest.yaml` — one file per episode (the script).
- `music/` — optional post-mix tracks.
- `.env` — API keys (copy from `.env.example`, never commit).

## First render

```sh
cp .env.example .env       # add your XAI_API_KEY (or FAL_KEY)
miloworks characters ep00-pilot
miloworks run ep00-pilot
miloworks serve            # open http://127.0.0.1:8765 to preview
```
"""

_ENV_EXAMPLE = """\
# xAI / Grok Imagine — https://x.ai/api
XAI_API_KEY=

# fal.ai — https://fal.ai/dashboard/keys (optional, for Kling backend)
# FALAI_API_KEY=
"""

_GITIGNORE = """\
.env
__pycache__/
*.pyc
.DS_Store

# Generated outputs are heavy and reproducible from the manifest.
episodes/*/output/
episodes/*/output-*/
episodes/*/_archive/
"""

_MUSIC_README = """\
# Music

Drop optional post-render score tracks here. Reference them by name
(with or without extension) in an episode's `music:` block:

```yaml
music:
  track: my-theme         # finds my-theme.mp3 / .ogg / .wav / .m4a / .flac
  volume_db: -2
  fade_in_s: 1.5
  fade_out_s: 3.0
```
"""


def scaffold_project(target: Path, *, name: str) -> None:
    """Create a fresh project at `target` with starter files.

    Refuses to overwrite an existing non-empty directory.
    """
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(
            f"{target} already exists and is not empty. "
            f"Pick a fresh path or remove it first."
        )
    target.mkdir(parents=True, exist_ok=True)
    (target / "episodes" / "ep00-pilot").mkdir(parents=True)
    (target / "music").mkdir()

    (target / "style_bible.md").write_text(_STYLE_BIBLE.format(name=name))
    (target / "characters.yaml").write_text(_CHARACTERS_YAML.format(name=name))
    (target / "README.md").write_text(_README.format(name=name))
    (target / ".env.example").write_text(_ENV_EXAMPLE)
    (target / ".gitignore").write_text(_GITIGNORE)
    (target / "music" / "README.md").write_text(_MUSIC_README)

    pilot = target / "episodes" / "ep00-pilot"
    (pilot / "manifest.yaml").write_text(_PILOT_MANIFEST.format(name=name))
    # Per-episode style + characters as relative symlinks back to the
    # project-level masters, so every episode stays self-consistent
    # but can be overridden by replacing the symlink with a real file.
    (pilot / "style_bible.md").symlink_to("../../style_bible.md")
    (pilot / "characters.yaml").symlink_to("../../characters.yaml")
