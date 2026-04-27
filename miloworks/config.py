"""Shared config + paths.

A *project* is a directory that contains a show: a `style_bible.md`,
a `characters.yaml`, an `episodes/` folder, and optionally a `music/`
folder and a `.env` with API keys. The MiloWorks engine itself ships
with one such project at `examples/milo/`, but anything pip-installing
this package will create a project of their own and run from inside
it.

All paths in this module are resolved against the *current project*,
not the engine's install location. Resolve order:

1. Explicit `set_project(path)` (the CLI does this when given `--project`).
2. The `MILOWORKS_PROJECT` env var.
3. Auto-detect from cwd: walk up from `Path.cwd()` looking for a
   directory that contains either an `episodes/` folder or a
   `style_bible.md`. This means you can `cd examples/milo &&
   miloworks serve` and it just works.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# The engine's own install root. Used for shipping templates and the web
# UI bundled inside the package — never for episode/music lookup.
ENGINE_ROOT = Path(__file__).resolve().parent.parent

PROJECT_ENV_VAR = "MILOWORKS_PROJECT"
_PROJECT: Path | None = None


def set_project(path: Path | str) -> None:
    """Pin the active project root for the rest of the process.

    Called by the CLI when the user passes `--project`. After this,
    `project_root()` always returns the pinned path.
    """
    global _PROJECT
    _PROJECT = Path(path).resolve()


def _looks_like_project(p: Path) -> bool:
    return (p / "episodes").is_dir() or (p / "style_bible.md").is_file()


def project_root() -> Path:
    """Resolve the active project root.

    Order: explicit set_project → $MILOWORKS_PROJECT → walk-up from cwd.
    Raises if nothing matches.
    """
    if _PROJECT is not None:
        return _PROJECT
    env = os.getenv(PROJECT_ENV_VAR)
    if env:
        p = Path(env).resolve()
        if not _looks_like_project(p):
            raise RuntimeError(
                f"${PROJECT_ENV_VAR}={env!r} but it doesn't look like a "
                f"MiloWorks project (no episodes/ or style_bible.md)."
            )
        return p
    # Walk up from cwd until we find a project directory.
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if _looks_like_project(candidate):
            return candidate
    raise RuntimeError(
        "No MiloWorks project found. Either:\n"
        "  • cd into a project directory (one containing episodes/ or "
        "style_bible.md), or\n"
        "  • pass --project /path/to/show, or\n"
        f"  • set ${PROJECT_ENV_VAR}=/path/to/show.\n"
        "Run `miloworks init <name>` to scaffold a new project."
    )


def episodes_dir() -> Path:
    return project_root() / "episodes"


def music_dir() -> Path:
    return project_root() / "music"


def music_track_path(track_name: str) -> Path:
    """Resolve a music track name to an on-disk path under the project's
    `music/` directory.

    Accepts names with or without an extension. Tries .mp3, .ogg, .wav,
    .m4a, .flac in order. Raises FileNotFoundError if none exist.
    """
    name = track_name.strip()
    mdir = music_dir()
    direct = mdir / name
    if direct.exists():
        return direct
    for ext in (".mp3", ".ogg", ".wav", ".m4a", ".flac"):
        p = mdir / f"{name}{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Music track {track_name!r} not found in {mdir}. "
        f"Tried direct path and extensions .mp3 .ogg .wav .m4a .flac."
    )


def load_env() -> None:
    """Load the project's .env, falling back to the engine root for
    backwards compatibility with the original Milo repo layout."""
    try:
        proot = project_root()
    except RuntimeError:
        proot = ENGINE_ROOT
    load_dotenv(proot / ".env")
    # Also try the engine root as a fallback (useful in dev where one
    # .env at the repo root powers all bundled examples).
    if proot != ENGINE_ROOT:
        load_dotenv(ENGINE_ROOT / ".env", override=False)


@dataclass(frozen=True)
class EpisodePaths:
    """All on-disk paths for a single episode.

    `output_subdir` lets different backends (xai, fal, wan) keep their
    rendered scenes + final.mp4 side-by-side under the same episode:
    e.g. ``output/`` for xAI vs ``output-kling/`` for fal's Kling.
    """

    episode_dir: Path
    output_subdir: str = "output"

    @property
    def manifest(self) -> Path:
        return self.episode_dir / "manifest.yaml"

    @property
    def style_bible(self) -> Path:
        return self.episode_dir / "style_bible.md"

    @property
    def characters_yaml(self) -> Path:
        return self.episode_dir / "characters.yaml"

    @property
    def characters_dir(self) -> Path:
        return self.episode_dir / "characters"

    def character_image(self, char_id: str) -> Path:
        return self.characters_dir / f"{char_id}.png"

    @property
    def output_dir(self) -> Path:
        return self.episode_dir / self.output_subdir

    @property
    def scenes_dir(self) -> Path:
        return self.output_dir / "scenes"

    @property
    def final_video(self) -> Path:
        return self.output_dir / "final.mp4"

    @property
    def final_last_frame(self) -> Path:
        """Episode-level chain handoff frame.

        At stitch time the runner copies the `handoff_scene`'s
        last_frame.png to this path so the next episode can seed scene
        01 from it via `image_from: "_prev_episode"`.
        """
        return self.output_dir / "last_frame.png"

    def scene_dir(self, scene_id: str) -> Path:
        return self.scenes_dir / scene_id

    def scene_video(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "video.mp4"

    def scene_last_frame(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "last_frame.png"

    def scene_meta(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "meta.json"

    def scene_prompt(self, scene_id: str) -> Path:
        return self.scene_dir(scene_id) / "prompt.txt"


def episode_paths(episode_slug: str, *, output_subdir: str = "output") -> EpisodePaths:
    return EpisodePaths(
        episode_dir=episodes_dir() / episode_slug,
        output_subdir=output_subdir,
    )


def get_api_key() -> str:
    key = os.getenv("XAI_API_KEY")
    if not key:
        raise RuntimeError(
            "XAI_API_KEY is not set. Put it in .env at your project root."
        )
    return key


def get_fal_api_key() -> str:
    key = os.getenv("FALAI_API_KEY") or os.getenv("FAL_KEY")
    if not key:
        raise RuntimeError(
            "FALAI_API_KEY (or FAL_KEY) is not set. Put it in .env at "
            "your project root."
        )
    return key
