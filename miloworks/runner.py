"""Episode orchestrator: characters + scenes + stitch."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .config import EpisodePaths, episode_paths, music_track_path
from .ffmpeg_utils import (
    concat_videos,
    extract_last_frame,
    replace_audio_with_music,
    trim_head,
)
from .manifest import (
    Episode,
    Scene,
    compose_prompt,
    load_character_sheets,
    load_episode,
)
from .xai_client import VideoResult, XaiClient, XaiError
from .xai_client import download as _xai_download
from .wan_client import WanClient
from .wan_client import download as _wan_download
from .fal_backend import FalClient, FalError
from .fal_backend import download as _fal_download

console = Console()

# Sentinel value for image_from that means "seed scene 01 from the previous
# episode's handoff frame". Used by daily episodes to chain across days.
PREV_EPISODE_TOKEN = "_prev_episode"


# =================== CHARACTER SHEETS ===================

def generate_characters(episode_slug: str, *, api_key: str, force: bool = False) -> list[Path]:
    paths = episode_paths(episode_slug)
    if not paths.characters_yaml.exists():
        raise FileNotFoundError(
            f"No characters.yaml at {paths.characters_yaml}. Create one first."
        )
    sheets = load_character_sheets(paths.characters_yaml)
    style_bible = paths.style_bible.read_text().strip() if paths.style_bible.exists() else ""
    client = XaiClient(api_key=api_key)
    paths.characters_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[Path] = []
    console.print(Panel.fit(f"Generating {len(sheets.characters)} character sheets", title=episode_slug))
    for char in sheets.characters:
        out = paths.character_image(char.id)
        if out.exists() and not force:
            console.print(f"[green]✓[/green] {char.id} cached → {out.name}")
            outputs.append(out)
            continue
        console.rule(f"[bold cyan]{char.id}[/bold cyan]")
        full_prompt = compose_prompt(style_bible, char.prompt)
        result = client.generate_image(
            full_prompt,
            aspect_ratio=sheets.aspect_ratio,
            resolution=sheets.resolution,
        )
        if not result.url:
            raise RuntimeError(f"No URL in image result for {char.id}: {result.raw}")
        download(result.url, out)
        console.print(f"  → {out.relative_to(paths.episode_dir)}")
        outputs.append(out)
    return outputs


# =================== EPISODE SCENES ===================


def _scene_is_cached(paths: EpisodePaths, scene_id: str) -> bool:
    return paths.scene_video(scene_id).exists() and paths.scene_meta(scene_id).exists()


def _resolve_seed_image(
    paths: EpisodePaths, episode: Episode, scene: Scene
) -> Path:
    if scene.image_from == PREV_EPISODE_TOKEN:
        return _resolve_prev_episode_frame(paths, episode, scene)
    if scene.image_from:
        src = paths.scene_last_frame(scene.image_from)
        if not src.exists():
            raise FileNotFoundError(
                f"Scene {scene.id} expects last frame of {scene.image_from}, "
                f"but {src} is missing."
            )
        return src
    if scene.seed_image:
        p = Path(scene.seed_image)
        if not p.is_absolute():
            p = paths.episode_dir / p
        if not p.exists():
            raise FileNotFoundError(f"seed_image not found: {p}")
        return p
    raise ValueError(
        f"Scene {scene.id} mode=image needs image_from or seed_image"
    )


def _resolve_prev_episode_frame(
    paths: EpisodePaths, episode: Episode, scene: Scene
) -> Path:
    """Resolve image_from='_prev_episode' to the prev episode's handoff frame.

    Resolution order:
    1. <prev>/<output_subdir>/last_frame.png — the canonical handoff,
       copied at stitch time from the prev episode's handoff_scene.
    2. <prev>/<output_subdir>/scenes/<handoff_or_last>/last_frame.png —
       fallback when the prev episode hasn't been re-stitched since the
       last regeneration.
    """
    prev_slug = episode.prev_episode
    if not prev_slug:
        raise ValueError(
            f"Scene {scene.id} uses image_from={PREV_EPISODE_TOKEN!r} but the "
            f"manifest has no `prev_episode:` field"
        )
    prev_paths = episode_paths(prev_slug, output_subdir=paths.output_subdir)
    if prev_paths.final_last_frame.exists():
        return prev_paths.final_last_frame

    if not prev_paths.manifest.exists():
        raise FileNotFoundError(
            f"Scene {scene.id} expects prev episode {prev_slug!r}, but "
            f"{prev_paths.manifest} does not exist"
        )
    prev_episode = load_episode(prev_paths.manifest, prev_paths.style_bible)
    handoff_id = prev_episode.handoff_scene or (
        prev_episode.scenes[-1].id if prev_episode.scenes else None
    )
    if not handoff_id:
        raise ValueError(f"prev episode {prev_slug!r} has no scenes")
    fallback = prev_paths.scene_last_frame(handoff_id)
    if not fallback.exists():
        raise FileNotFoundError(
            f"Scene {scene.id} expects the handoff frame of prev episode "
            f"{prev_slug!r}, but neither {prev_paths.final_last_frame} nor "
            f"{fallback} exist. Run `milo run {prev_slug}` (and stitch) first."
        )
    return fallback


def _resolve_reference_paths(paths: EpisodePaths, scene: Scene) -> list[Path]:
    if not scene.reference_chars:
        raise ValueError(f"Scene {scene.id} mode=reference requires reference_chars")
    result = []
    for cid in scene.reference_chars:
        p = paths.character_image(cid)
        if not p.exists():
            raise FileNotFoundError(
                f"Scene {scene.id} references character '{cid}' but {p} "
                f"is missing. Run `milo characters {paths.episode_dir.name}` first."
            )
        result.append(p)
    return result


def _resolve_extend_source_url(paths: EpisodePaths, scene: Scene) -> str:
    if not scene.extend_from:
        raise ValueError(f"Scene {scene.id} mode=extend requires extend_from")
    meta_path = paths.scene_meta(scene.extend_from)
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")
    meta = json.loads(meta_path.read_text())
    url = meta.get("url")
    if not url:
        raise ValueError(f"No url in {meta_path}. xAI URLs expire — rerun source scene.")
    return url


def _generate_scene_xai(
    client: XaiClient,
    episode: Episode,
    paths: EpisodePaths,
    scene: Scene,
) -> VideoResult:
    full_prompt = compose_prompt(episode.style_bible, scene.prompt, scene.audio)
    paths.scene_dir(scene.id).mkdir(parents=True, exist_ok=True)
    paths.scene_prompt(scene.id).write_text(full_prompt)

    if scene.mode == "text":
        return client.generate_text_to_video(
            full_prompt,
            duration=scene.duration,
            aspect_ratio=episode.aspect_ratio,
            resolution=episode.resolution,
        )
    if scene.mode == "image":
        seed = _resolve_seed_image(paths, episode, scene)
        return client.generate_image_to_video(
            full_prompt,
            seed,
            duration=scene.duration,
            aspect_ratio=episode.aspect_ratio,
            resolution=episode.resolution,
        )
    if scene.mode == "reference":
        refs = _resolve_reference_paths(paths, scene)
        return client.generate_reference_to_video(
            full_prompt,
            refs,
            duration=scene.duration,
            aspect_ratio=episode.aspect_ratio,
            resolution=episode.resolution,
        )
    if scene.mode == "extend":
        source_url = _resolve_extend_source_url(paths, scene)
        return client.extend_video(
            full_prompt,
            source_url,
            duration=scene.duration,
        )
    raise ValueError(f"Unknown scene.mode={scene.mode!r} for {scene.id}")


FAL_PROMPT_MAX = 2500  # Kling 2.6 Pro hard cap


def _generate_scene_fal(
    client: FalClient,
    episode: Episode,
    paths: EpisodePaths,
    scene: Scene,
) -> VideoResult:
    """fal.ai / Kling 2.6 Pro backend.

    Kling natively generates audio, so we send a SHOT + AUDIO prompt.
    We deliberately drop the master style bible here: Kling caps prompts
    at 2500 chars, and for image-to-video the seed frame already carries
    style continuity. Title/outro cards self-describe their look. Extend
    / reference modes map to image-to-video using the first reference.
    """
    full_prompt = compose_prompt("", scene.prompt, scene.audio)
    if len(full_prompt) > FAL_PROMPT_MAX:
        full_prompt = full_prompt[: FAL_PROMPT_MAX - 1].rstrip() + "…"
    paths.scene_dir(scene.id).mkdir(parents=True, exist_ok=True)
    paths.scene_prompt(scene.id).write_text(full_prompt)

    if scene.mode == "text":
        return client.generate_text_to_video(
            full_prompt,
            duration=scene.duration,
            aspect_ratio=episode.aspect_ratio,
            resolution=episode.resolution,
        )
    if scene.mode == "image":
        seed = _resolve_seed_image(paths, episode, scene)
        return client.generate_image_to_video(
            full_prompt,
            seed,
            duration=scene.duration,
            aspect_ratio=episode.aspect_ratio,
            resolution=episode.resolution,
        )
    if scene.mode == "reference":
        refs = _resolve_reference_paths(paths, scene)
        # Kling i2v takes a single start image; fall back to first reference.
        return client.generate_image_to_video(
            full_prompt,
            refs[0],
            duration=scene.duration,
            aspect_ratio=episode.aspect_ratio,
            resolution=episode.resolution,
        )
    raise ValueError(
        f"Scene {scene.id} mode={scene.mode!r} is not supported by the fal backend"
    )


def _generate_scene_wan(
    client: WanClient,
    episode: Episode,
    paths: EpisodePaths,
    scene: Scene,
) -> VideoResult:
    """Wan 2.2 backend. Only supports image and flf2v modes for now.

    - mode=image with image_from → I2V (start frame from previous scene)
    - mode=image with end_frame set (via scene.end_frame_from) → FLF2V
    - mode=text is NOT supported here yet (we don't have T2V weights on box)
    """
    # Build prompt WITHOUT the audio block: Wan is silent.
    full_prompt = compose_prompt(episode.style_bible, scene.prompt)
    paths.scene_dir(scene.id).mkdir(parents=True, exist_ok=True)
    paths.scene_prompt(scene.id).write_text(full_prompt)

    if scene.mode == "text":
        raise ValueError(
            f"Scene {scene.id} mode=text is not supported by the Wan backend. "
            f"Give it a seed_image or switch backends."
        )

    if scene.mode == "image":
        start = _resolve_seed_image(paths, episode, scene)
        # Optional end-frame anchor for true FLF2V.
        end = _resolve_end_frame(paths, scene)
        if end is not None:
            return client.generate_flf2v(
                full_prompt,
                start,
                end,
                duration=scene.duration,
                aspect_ratio=episode.aspect_ratio,
                resolution=episode.resolution,
                filename_prefix=f"{episode.slug}_{scene.id}",
            )
        return client.generate_image_to_video(
            full_prompt,
            start,
            duration=scene.duration,
            aspect_ratio=episode.aspect_ratio,
            resolution=episode.resolution,
            filename_prefix=f"{episode.slug}_{scene.id}",
        )

    raise ValueError(
        f"Scene {scene.id} mode={scene.mode!r} is not supported by Wan backend"
    )


def _resolve_end_frame(paths: EpisodePaths, scene: Scene) -> Path | None:
    end_path = getattr(scene, "end_frame", None)
    if end_path:
        p = Path(end_path)
        if not p.is_absolute():
            p = paths.episode_dir / p
        if not p.exists():
            raise FileNotFoundError(f"end_frame not found: {p}")
        return p
    end_from = getattr(scene, "end_frame_from", None)
    if end_from:
        p = paths.scene_last_frame(end_from)
        if not p.exists():
            raise FileNotFoundError(
                f"end_frame_from={end_from} but {p} is missing"
            )
        return p
    return None


def run_episode(
    episode_slug: str,
    *,
    api_key: str | None = None,
    only_scenes: list[str] | None = None,
    force: bool = False,
    backend: str = "xai",
    wan_base_url: str = "http://127.0.0.1:8188",
    output_subdir: str = "output",
) -> Path | None:
    paths = episode_paths(episode_slug, output_subdir=output_subdir)
    episode = load_episode(paths.manifest, paths.style_bible)

    if backend == "xai":
        if not api_key:
            raise ValueError("XAI backend requires api_key")
        client: XaiClient | WanClient | FalClient = XaiClient(api_key=api_key)
        download_fn = _xai_download
    elif backend == "wan":
        client = WanClient(base_url=wan_base_url)
        download_fn = _wan_download
    elif backend == "fal":
        if not api_key:
            raise ValueError("fal backend requires api_key")
        client = FalClient(api_key=api_key)
        download_fn = _fal_download
    else:
        raise ValueError(f"Unknown backend: {backend!r}")

    console.print(
        Panel.fit(
            f"[bold]{episode.title}[/bold]\n{episode.logline}\n\n"
            f"[dim]{len(episode.scenes)} scenes • {episode.aspect_ratio} • "
            f"{episode.resolution} • backend={backend}[/dim]",
            title=f"Episode: {episode.slug}",
        )
    )

    for scene in episode.scenes:
        if only_scenes and scene.id not in only_scenes:
            continue
        if _scene_is_cached(paths, scene.id) and not force:
            console.print(f"[green]✓[/green] scene {scene.id} cached, skipping")
            continue

        # Wan can't do text-only scenes yet (no T2V weights on the box). Skip
        # and leave any existing xAI-generated video in place.
        if backend == "wan" and scene.mode == "text":
            if paths.scene_video(scene.id).exists():
                console.print(
                    f"[yellow]↷[/yellow] scene {scene.id} mode=text — "
                    f"keeping existing video (Wan has no T2V)"
                )
                continue
            console.print(
                f"[yellow]↷[/yellow] scene {scene.id} mode=text skipped "
                f"(Wan backend has no T2V weights)"
            )
            continue

        tag = scene.mode + (
            f"←{','.join(scene.reference_chars)}" if scene.mode == "reference" else ""
        ) + (
            f"←{scene.image_from}" if scene.mode == "image" and scene.image_from else ""
        )
        console.rule(f"[bold cyan]Scene {scene.id}[/bold cyan] ({tag}, {scene.duration}s)")
        console.print(f"[dim]{scene.prompt[:160]}{'…' if len(scene.prompt) > 160 else ''}[/dim]")

        # Content-moderation false positives are random; retry a few times
        # before giving up on a scene.
        result = None
        last_err: Exception | None = None
        for attempt in range(1, 4):
            try:
                if backend == "xai":
                    result = _generate_scene_xai(client, episode, paths, scene)  # type: ignore[arg-type]
                elif backend == "fal":
                    result = _generate_scene_fal(client, episode, paths, scene)  # type: ignore[arg-type]
                else:
                    result = _generate_scene_wan(client, episode, paths, scene)  # type: ignore[arg-type]
                break
            except (XaiError, FalError) as e:
                last_err = e
                msg = str(e)
                transient = (
                    "content moderation" in msg.lower()
                    or "moderation" in msg.lower()
                    or "rate" in msg.lower()
                )
                if not transient or attempt == 3:
                    raise
                wait = 5 * attempt
                console.print(
                    f"  [yellow]⚠ attempt {attempt} rejected "
                    f"({msg[:80]}…); retrying in {wait}s[/yellow]"
                )
                time.sleep(wait)
        assert result is not None

        video_path = paths.scene_video(scene.id)
        download_fn(result.url, video_path)
        console.print(f"  downloaded → {video_path.relative_to(paths.episode_dir)}")

        # Extend mode returns input+extension concatenated. Strip the source part.
        if scene.mode == "extend" and scene.extend_from:
            src_meta = json.loads(paths.scene_meta(scene.extend_from).read_text())
            src_duration = float(src_meta.get("duration_s") or 0)
            if src_duration > 0:
                raw_path = paths.scene_dir(scene.id) / "raw_accumulated.mp4"
                video_path.rename(raw_path)
                trim_head(raw_path, src_duration, video_path)
                console.print(
                    f"  trimmed first {src_duration:.1f}s "
                    f"(kept extension only) → {video_path.name}"
                )

        last_frame = paths.scene_last_frame(scene.id)
        extract_last_frame(video_path, last_frame)
        console.print(f"  last frame → {last_frame.relative_to(paths.episode_dir)}")

        paths.scene_meta(scene.id).write_text(
            json.dumps(
                {
                    "scene_id": scene.id,
                    "mode": scene.mode,
                    "backend": backend,
                    "duration_s": result.duration_s,
                    "request_id": result.request_id,
                    "url": result.url,
                    "prompt": scene.prompt,
                    "reference_chars": scene.reference_chars,
                    "image_from": scene.image_from,
                    "audio": scene.audio,
                    "raw": result.raw,
                },
                indent=2,
            )
        )

    if only_scenes:
        console.print("[yellow]Skipping stitch — partial run[/yellow]")
        return None
    return stitch_episode(episode_slug, output_subdir=output_subdir)


def stitch_episode(episode_slug: str, *, output_subdir: str = "output") -> Path:
    paths = episode_paths(episode_slug, output_subdir=output_subdir)
    episode = load_episode(paths.manifest, paths.style_bible)
    videos = [paths.scene_video(s.id) for s in episode.scenes]
    missing = [p for p in videos if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Cannot stitch — missing {len(missing)} scene videos: "
            f"{[p.name for p in missing[:3]]}"
        )
    console.rule("[bold magenta]Stitching final episode[/bold magenta]")
    if episode.music is not None:
        # Concat into a temp file, then mix music over it as the final.
        # Keeps `final.mp4` always at the canonical path with the score baked in.
        raw_concat = paths.output_dir / "concat_raw.mp4"
        concat_videos(videos, raw_concat)
        try:
            track = music_track_path(episode.music.track)
        except FileNotFoundError as e:
            console.print(f"[red]✗ music track unresolved: {e}[/red]")
            raw_concat.replace(paths.final_video)
            final = paths.final_video
        else:
            console.print(f"  scoring with [cyan]{track.name}[/cyan]")
            final = replace_audio_with_music(
                raw_concat,
                track,
                paths.final_video,
                fade_in_s=episode.music.fade_in_s,
                fade_out_s=episode.music.fade_out_s,
                volume_db=episode.music.volume_db,
                start_offset_s=episode.music.start_offset_s,
            )
            raw_concat.unlink(missing_ok=True)
    else:
        final = concat_videos(videos, paths.final_video)
    console.print(f"[bold green]✓ final video:[/bold green] {final}")

    # Copy the handoff scene's last_frame.png up to output/last_frame.png so
    # the next episode can chain via image_from="_prev_episode". Defaults to
    # the last scene; ep00 (which ends on a text outro card) sets handoff_scene
    # explicitly to its last narrative shot.
    handoff_id = episode.handoff_scene or (
        episode.scenes[-1].id if episode.scenes else None
    )
    if handoff_id:
        handoff_src = paths.scene_last_frame(handoff_id)
        if handoff_src.exists():
            paths.final_last_frame.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(handoff_src, paths.final_last_frame)
            console.print(
                f"  handoff frame ← scene {handoff_id} → "
                f"{paths.final_last_frame.relative_to(paths.episode_dir)}"
            )
        else:
            console.print(
                f"[yellow]⚠ handoff scene {handoff_id} has no last_frame.png; "
                f"chain to next episode unavailable[/yellow]"
            )
    return final
