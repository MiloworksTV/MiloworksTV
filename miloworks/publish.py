"""`miloworks publish` — populate site/ with rendered episodes.

Reads every episode in the active project that has a `final.mp4`,
copies that mp4 + a poster frame into `<site>/videos/`, and writes
`<site>/episodes.json` listing them. The static `index.html` reads
that JSON to render the public episode grid.

Designed to be cheap and idempotent: copies rather than moves, only
re-extracts a poster if it's missing or older than the source mp4.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .config import episode_paths, episodes_dir


def _extract_poster(video: Path, poster: Path, *, at_seconds: float = 1.5) -> None:
    """Snap a JPEG poster from the middle-ish of a video.

    No-op if the poster is already newer than the source video — that
    way `miloworks publish` is cheap to re-run after only some episodes
    have changed.
    """
    if poster.exists() and poster.stat().st_mtime >= video.stat().st_mtime:
        return
    poster.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel", "error",
            "-ss", f"{at_seconds:.2f}",
            "-i", str(video),
            "-frames:v", "1",
            "-q:v", "3",
            str(poster),
        ],
        check=True,
    )


def _episode_record(slug: str, *, output_subdir: str) -> dict[str, Any] | None:
    """Build one episode entry, or None if it isn't published-ready
    (no final.mp4 yet)."""
    paths = episode_paths(slug, output_subdir=output_subdir)
    if not paths.final_video.exists() or not paths.manifest.exists():
        return None
    with paths.manifest.open() as f:
        m = yaml.safe_load(f) or {}
    return {
        "slug": slug,
        "title": m.get("title", slug),
        "logline": (m.get("logline") or "").strip(),
        "day": m.get("day"),
        "weekday": m.get("weekday"),
        "video": f"videos/{slug}.mp4",
        "poster": f"videos/{slug}.jpg",
        # Lets the site sort by recency without needing the mp4 mtime.
        "mtime": int(paths.final_video.stat().st_mtime),
    }


def publish_site(
    site_dir: Path,
    *,
    show_name: str,
    show_tagline: str,
    show_description: str,
    output_subdir: str = "output",
) -> dict[str, Any]:
    """Materialize the public site from the active project's renders.

    Returns the manifest written to `<site>/episodes.json` so the
    caller can summarize what was published.
    """
    edir = episodes_dir()
    if not edir.exists():
        raise FileNotFoundError(f"No episodes/ found at {edir}")

    videos_out = site_dir / "videos"
    videos_out.mkdir(parents=True, exist_ok=True)

    episodes: list[dict[str, Any]] = []
    for ep_dir in sorted(edir.iterdir()):
        if not ep_dir.is_dir() or ep_dir.name.startswith((".", "_")):
            continue
        rec = _episode_record(ep_dir.name, output_subdir=output_subdir)
        if rec is None:
            continue
        src_mp4 = ep_dir / output_subdir / "final.mp4"
        dst_mp4 = videos_out / f"{ep_dir.name}.mp4"
        # Only copy if source is newer — keeps publish cheap on incremental runs.
        if (
            not dst_mp4.exists()
            or src_mp4.stat().st_mtime > dst_mp4.stat().st_mtime
        ):
            shutil.copy2(src_mp4, dst_mp4)
        _extract_poster(dst_mp4, videos_out / f"{ep_dir.name}.jpg")
        episodes.append(rec)

    # Newest episode first so the site's "Latest" is trivial.
    episodes.sort(key=lambda r: r["mtime"], reverse=True)

    manifest = {
        "show": {
            "name": show_name,
            "tagline": show_tagline,
            "description": show_description,
        },
        "episodes": episodes,
    }

    (site_dir / "episodes.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    return manifest
