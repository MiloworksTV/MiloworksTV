"""FastAPI server that drives the same runner as the CLI.

This is the local studio app: episode dashboard, per-scene preview + reroll,
episode stitch. The repo on disk stays the source of truth — every endpoint
reads/writes the same files the CLI does.

Boot with `milo serve` and open http://127.0.0.1:8765.
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .config import (
    episode_paths,
    episodes_dir,
    get_api_key,
    get_fal_api_key,
    load_env,
    project_root,
)
from .manifest import load_episode
from .runner import run_episode, stitch_episode

# =================== JOBS ===================

JobStatus = Literal["queued", "running", "done", "error"]
JobKind = Literal["render_scene", "stitch"]


@dataclass
class Job:
    id: str
    kind: JobKind
    slug: str
    backend: str
    scene_id: str | None = None
    status: JobStatus = "queued"
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()
# Single worker on purpose: API renders cost real money and the CLI
# pipeline isn't designed for concurrent writes into the same scene dir.
_executor = ThreadPoolExecutor(max_workers=1)


def _job_update(job_id: str, **fields: object) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        for k, v in fields.items():
            setattr(job, k, v)


def _output_subdir(backend: str) -> str:
    return "output" if backend == "xai" else f"output-{backend}"


def _resolve_api_key(backend: str) -> str | None:
    if backend == "xai":
        return get_api_key()
    if backend == "fal":
        return get_fal_api_key()
    return None


def _run_render(job_id: str, slug: str, scene_id: str, backend: str) -> None:
    _job_update(job_id, status="running", started_at=time.time())
    try:
        run_episode(
            slug,
            api_key=_resolve_api_key(backend),
            only_scenes=[scene_id],
            force=True,
            backend=backend,
            output_subdir=_output_subdir(backend),
        )
        _job_update(job_id, status="done", finished_at=time.time())
    except Exception as e:  # noqa: BLE001 — we want to surface anything to the UI
        _job_update(job_id, status="error", error=str(e), finished_at=time.time())


def _run_stitch(job_id: str, slug: str, backend: str) -> None:
    _job_update(job_id, status="running", started_at=time.time())
    try:
        stitch_episode(slug, output_subdir=_output_subdir(backend))
        _job_update(job_id, status="done", finished_at=time.time())
    except Exception as e:  # noqa: BLE001
        _job_update(job_id, status="error", error=str(e), finished_at=time.time())


def _enqueue(job: Job, fn, *args) -> Job:
    _jobs[job.id] = job
    _executor.submit(fn, job.id, *args)
    return job


# =================== APP ===================

WEB_DIR = Path(__file__).parent / "web"
app = FastAPI(title="Milo Studio")


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return HTMLResponse((WEB_DIR / "index.html").read_text())


@app.get("/api/project")
def get_project() -> dict:
    """Tell the UI which project is loaded (so the header can show it)."""
    proot = project_root()
    return {"path": str(proot), "name": proot.name}


# ---- Episode list ----

@app.get("/api/episodes")
def list_episodes() -> list[dict]:
    out: list[dict] = []
    edir = episodes_dir()
    if not edir.exists():
        return out
    for child in sorted(edir.iterdir()):
        if not child.is_dir():
            continue
        # Skip hidden / scratch dirs (e.g. _smoke, .DS_Store).
        if child.name.startswith((".", "_")):
            continue
        manifest = child / "manifest.yaml"
        if not manifest.exists():
            continue
        try:
            data = yaml.safe_load(manifest.read_text()) or {}
        except Exception:
            continue
        out.append(
            {
                "slug": child.name,
                "title": data.get("title", child.name),
                "logline": data.get("logline", ""),
                "day": data.get("day"),
                "weekday": data.get("weekday"),
                "bucket": data.get("bucket"),
                "concept": data.get("concept"),
                "scene_count": len(data.get("scenes", []) or []),
            }
        )
    return out


# ---- Episode detail ----

def _resolve_seed_path(paths, episode, scene) -> Path | None:
    """Best-effort lookup of the seed image used to render a scene.

    Returns None for scenes that don't have a chained seed (mode=text,
    mode=reference, or extend modes). The UI just hides the seed
    preview in those cases.
    """
    if scene.image_from == "_prev_episode":
        if not episode.prev_episode:
            return None
        prev = episode_paths(
            episode.prev_episode, output_subdir=paths.output_subdir
        )
        if prev.final_last_frame.exists():
            return prev.final_last_frame
        # Fall back to the prev episode's handoff scene's last frame.
        try:
            prev_ep = load_episode(prev.manifest, prev.style_bible)
        except FileNotFoundError:
            return None
        handoff = prev_ep.handoff_scene or (
            prev_ep.scenes[-1].id if prev_ep.scenes else None
        )
        return prev.scene_last_frame(handoff) if handoff else None
    if scene.image_from:
        return paths.scene_last_frame(scene.image_from)
    if scene.seed_image:
        p = Path(scene.seed_image)
        if not p.is_absolute():
            p = paths.episode_dir / p
        return p
    return None


@app.get("/api/episodes/{slug}")
def get_episode(slug: str, backend: str = "xai") -> dict:
    paths = episode_paths(slug, output_subdir=_output_subdir(backend))
    if not paths.manifest.exists():
        raise HTTPException(404, f"Episode {slug!r} not found")
    episode = load_episode(paths.manifest, paths.style_bible)

    scenes_out: list[dict] = []
    max_scene_mtime = 0
    for s in episode.scenes:
        video = paths.scene_video(s.id)
        meta = paths.scene_meta(s.id)
        seed = _resolve_seed_path(paths, episode, s)
        rendered = video.exists() and meta.exists()
        v_mtime = int(video.stat().st_mtime) if video.exists() else None
        if v_mtime is not None:
            max_scene_mtime = max(max_scene_mtime, v_mtime)
        scenes_out.append(
            {
                "id": s.id,
                "mode": s.mode,
                "duration": s.duration,
                "image_from": s.image_from,
                "prompt": s.prompt,
                "audio": s.audio,
                "rendered": rendered,
                "video_mtime": v_mtime,
                "seed_exists": bool(seed and seed.exists()),
            }
        )

    final = paths.final_video
    final_mtime = int(final.stat().st_mtime) if final.exists() else None
    final_stale = bool(
        final_mtime is not None
        and max_scene_mtime
        and max_scene_mtime > final_mtime
    )

    return {
        "slug": episode.slug,
        "title": episode.title,
        "logline": episode.logline,
        "aspect_ratio": episode.aspect_ratio,
        "resolution": episode.resolution,
        "prev_episode": episode.prev_episode,
        "handoff_scene": episode.handoff_scene,
        "scenes": scenes_out,
        "final_rendered": final.exists(),
        "final_mtime": final_mtime,
        "final_stale": final_stale,
        "backend": backend,
    }


# ---- File serving ----

@app.get("/api/episodes/{slug}/scenes/{scene_id}/video")
def get_scene_video(slug: str, scene_id: str, backend: str = "xai") -> FileResponse:
    paths = episode_paths(slug, output_subdir=_output_subdir(backend))
    p = paths.scene_video(scene_id)
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4")


@app.get("/api/episodes/{slug}/scenes/{scene_id}/seed")
def get_scene_seed(slug: str, scene_id: str, backend: str = "xai") -> FileResponse:
    paths = episode_paths(slug, output_subdir=_output_subdir(backend))
    if not paths.manifest.exists():
        raise HTTPException(404)
    episode = load_episode(paths.manifest, paths.style_bible)
    scene = next((s for s in episode.scenes if s.id == scene_id), None)
    if scene is None:
        raise HTTPException(404, f"Scene {scene_id!r} not in manifest")
    p = _resolve_seed_path(paths, episode, scene)
    if not p or not p.exists():
        raise HTTPException(404, "Seed image not yet available")
    return FileResponse(p, media_type="image/png")


@app.get("/api/episodes/{slug}/final")
def get_episode_final(slug: str, backend: str = "xai") -> FileResponse:
    paths = episode_paths(slug, output_subdir=_output_subdir(backend))
    p = paths.final_video
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4")


# ---- Job control ----

class RenderRequest(BaseModel):
    backend: Literal["xai", "fal", "wan"] = "xai"


@app.post("/api/episodes/{slug}/scenes/{scene_id}/render")
def post_render_scene(slug: str, scene_id: str, req: RenderRequest) -> dict:
    load_env()
    paths = episode_paths(slug, output_subdir=_output_subdir(req.backend))
    if not paths.manifest.exists():
        raise HTTPException(404, f"Episode {slug!r} not found")
    episode = load_episode(paths.manifest, paths.style_bible)
    if not any(s.id == scene_id for s in episode.scenes):
        raise HTTPException(404, f"Scene {scene_id!r} not in manifest")
    job = Job(
        id=uuid.uuid4().hex,
        kind="render_scene",
        slug=slug,
        backend=req.backend,
        scene_id=scene_id,
    )
    _enqueue(job, _run_render, slug, scene_id, req.backend)
    return asdict(job)


@app.post("/api/episodes/{slug}/stitch")
def post_stitch(slug: str, req: RenderRequest) -> dict:
    load_env()
    paths = episode_paths(slug, output_subdir=_output_subdir(req.backend))
    if not paths.manifest.exists():
        raise HTTPException(404, f"Episode {slug!r} not found")
    job = Job(
        id=uuid.uuid4().hex,
        kind="stitch",
        slug=slug,
        backend=req.backend,
    )
    _enqueue(job, _run_stitch, slug, req.backend)
    return asdict(job)


@app.get("/api/jobs")
def list_jobs(limit: int = 50) -> list[dict]:
    with _jobs_lock:
        items = sorted(
            _jobs.values(), key=lambda j: j.created_at, reverse=True
        )[:limit]
        return [asdict(j) for j in items]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404)
        return asdict(job)


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Boot uvicorn synchronously. Used by `milo serve`."""
    import uvicorn

    load_env()
    uvicorn.run(app, host=host, port=port, log_level="info")
