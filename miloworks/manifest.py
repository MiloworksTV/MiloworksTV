"""Episode manifest + character sheet models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

SceneMode = Literal["text", "image", "reference", "extend"]


@dataclass
class Scene:
    id: str
    mode: SceneMode
    prompt: str
    duration: int = 8
    # mode=image
    image_from: str | None = None
    seed_image: str | None = None
    # mode=reference: list of character ids whose PNGs to pass as reference_images
    reference_chars: list[str] = field(default_factory=list)
    # mode=extend
    extend_from: str | None = None
    # Optional: for Wan FLF2V, pin the END frame of this scene.
    # `end_frame_from` references another scene's last_frame.png;
    # `end_frame` points at any image file (absolute or relative to episode).
    end_frame_from: str | None = None
    end_frame: str | None = None
    notes: str = ""
    # Free-form sound-design description for a later audio pass
    # (xAI video generation is silent). Not sent to the video model.
    audio: str = ""


@dataclass
class Music:
    """Post-render music score. The grok-imagine-video model bakes its own
    audio (voices, ambient, SFX) into every clip, but it lip-syncs poorly
    and the autonomous pipeline can't trust voiced dialogue. So the stitch
    step REPLACES the concatenated video's audio entirely with the track
    declared here. Set `track` to a filename (with or without extension)
    inside the repo's top-level `music/` directory.
    """

    track: str  # e.g. "satie-gymnopedie-1" or "satie-gymnopedie-1.mp3"
    volume_db: float = -2.0
    fade_in_s: float = 1.5
    fade_out_s: float = 2.5
    start_offset_s: float = 0.0
    # Future knob: mix the model's audio under the music at this gain (dB).
    # When None the model audio is dropped completely. Not yet implemented.
    duck_model_db: float | None = None


@dataclass
class Episode:
    slug: str
    title: str
    logline: str
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    style_bible: str = ""
    scenes: list[Scene] = field(default_factory=list)
    # Cross-episode chain. When a scene uses image_from="_prev_episode"
    # the runner pulls the seed image from the previous episode's
    # output/last_frame.png (which is itself a copy of the handoff scene's
    # last frame — see `handoff_scene` below).
    prev_episode: str | None = None
    # Which scene's last_frame.png becomes this episode's chain handoff
    # for the *next* episode. Defaults to the last scene in the manifest,
    # which is wrong when the episode ends on a text outro card. Set it
    # explicitly to the last narrative scene id in that case.
    handoff_scene: str | None = None
    # Optional post-render musical score. When set, the stitch step mixes
    # the named music track over the concatenated video and drops the
    # model-generated audio. See `Music` above.
    music: Music | None = None


@dataclass
class Character:
    id: str
    prompt: str


@dataclass
class CharacterSheets:
    aspect_ratio: str = "1:1"
    resolution: str = "1k"
    characters: list[Character] = field(default_factory=list)


def load_episode(manifest_path: Path, style_bible_path: Path | None = None) -> Episode:
    data = yaml.safe_load(manifest_path.read_text())

    style_bible = ""
    if style_bible_path and style_bible_path.exists():
        style_bible = style_bible_path.read_text().strip()

    scenes = [
        Scene(
            id=str(s["id"]),
            mode=s.get("mode", "text"),
            prompt=s["prompt"].strip(),
            duration=int(s.get("duration", 8)),
            image_from=s.get("image_from"),
            seed_image=s.get("seed_image"),
            reference_chars=list(s.get("reference_chars") or []),
            extend_from=s.get("extend_from"),
            end_frame_from=s.get("end_frame_from"),
            end_frame=s.get("end_frame"),
            notes=s.get("notes", ""),
            audio=(s.get("audio") or "").strip(),
        )
        for s in data["scenes"]
    ]

    music_data = data.get("music")
    music: Music | None = None
    if isinstance(music_data, dict) and music_data.get("track"):
        music = Music(
            track=str(music_data["track"]),
            volume_db=float(music_data.get("volume_db", -2.0)),
            fade_in_s=float(music_data.get("fade_in_s", 1.5)),
            fade_out_s=float(music_data.get("fade_out_s", 2.5)),
            start_offset_s=float(music_data.get("start_offset_s", 0.0)),
            duck_model_db=(
                float(music_data["duck_model_db"])
                if music_data.get("duck_model_db") is not None
                else None
            ),
        )

    return Episode(
        slug=data["slug"],
        title=data["title"],
        logline=data.get("logline", ""),
        aspect_ratio=data.get("aspect_ratio", "16:9"),
        resolution=data.get("resolution", "720p"),
        style_bible=style_bible,
        scenes=scenes,
        prev_episode=data.get("prev_episode"),
        handoff_scene=(
            str(data["handoff_scene"]) if data.get("handoff_scene") is not None else None
        ),
        music=music,
    )


def load_character_sheets(yaml_path: Path) -> CharacterSheets:
    data = yaml.safe_load(yaml_path.read_text())
    chars = [Character(id=c["id"], prompt=c["prompt"].strip()) for c in data["characters"]]
    return CharacterSheets(
        aspect_ratio=data.get("aspect_ratio", "1:1"),
        resolution=data.get("resolution", "1k"),
        characters=chars,
    )


# grok-imagine-video's /videos/generations endpoint rejects prompts
# longer than 4096 *bytes* (not characters) with HTTP 400. UTF-8
# multi-byte characters like em-dashes (—) cost 3 bytes each, so the
# byte count can exceed the char count. Enforce the byte limit
# locally so callers see which scene overflows instead of a cryptic
# API error.
MAX_PROMPT_BYTES = 4096


def compose_prompt(
    style_bible: str, scene_prompt: str, audio: str | None = None
) -> str:
    """Build the full prompt sent to grok-imagine-video.

    grok-imagine-video generates AUDIO along with the video (AAC track).
    Anything described in the prompt is translated into ambient sound,
    SFX, and voice. We append a clearly-labeled AUDIO section so the
    model hears the intended sound design.
    """
    parts: list[str] = []
    if style_bible:
        parts.append(style_bible.strip())
    parts.append(f"SHOT:\n{scene_prompt.strip()}")
    if audio:
        parts.append(f"AUDIO:\n{audio.strip()}")
    composed = "\n\n---\n\n".join(parts)
    n_bytes = len(composed.encode("utf-8"))
    if n_bytes > MAX_PROMPT_BYTES:
        raise ValueError(
            f"Composed prompt is {n_bytes} bytes "
            f"({len(composed)} chars), {n_bytes - MAX_PROMPT_BYTES} over "
            f"the {MAX_PROMPT_BYTES}-byte API limit. Trim style_bible.md "
            f"or this scene's prompt/audio. Note multi-byte UTF-8 chars "
            f"like em-dashes (—) cost 3 bytes each — replace with '--' "
            f"to save space."
        )
    return composed
