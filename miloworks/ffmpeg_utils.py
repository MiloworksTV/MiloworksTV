"""Thin wrappers around the ffmpeg CLI for frame extraction and concat."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def _run(args: list[str]) -> None:
    if not shutil.which("ffmpeg"):
        raise FFmpegError("ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`).")
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(
            f"ffmpeg failed ({' '.join(args)}):\n{result.stderr[-2000:]}"
        )


def trim_head(video_path: Path, seconds_to_drop: float, out_path: Path) -> Path:
    """Re-encode a video after dropping the first N seconds.

    Used to strip the accumulated source video from an `extend` result,
    keeping only the newly generated extension.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Re-encode (not -c copy) to ensure a clean keyframe at t=0.
    _run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{seconds_to_drop:.3f}",
            "-i",
            str(video_path),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(out_path),
        ]
    )
    return out_path


def extract_last_frame(video_path: Path, out_png: Path) -> Path:
    """Extract the last frame of a video as a PNG."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-sseof",
            "-0.5",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_png),
        ]
    )
    return out_png


def probe_duration(video_path: Path) -> float:
    """Return the duration of a media file in seconds."""
    if not shutil.which("ffprobe"):
        raise FFmpegError("ffprobe not found on PATH (comes with ffmpeg).")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FFmpegError(f"ffprobe failed:\n{result.stderr[-2000:]}")
    return float(result.stdout.strip())


def replace_audio_with_music(
    video_path: Path,
    music_path: Path,
    out_path: Path,
    *,
    fade_in_s: float = 1.5,
    fade_out_s: float = 2.5,
    volume_db: float = -2.0,
    start_offset_s: float = 0.0,
) -> Path:
    """Re-mux a video, replacing its audio track entirely with `music_path`.

    The music is trimmed to the video's exact duration, faded in/out, and
    gain-shifted by `volume_db`. The video stream is copied (no re-encode).
    Used by the silent-pipeline stitch step to drop the model's bad-lip-sync
    audio and lay down a clean classical score on top.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dur = probe_duration(video_path)
    fade_out_start = max(0.0, dur - fade_out_s)

    afilter = (
        f"atrim=duration={dur:.3f},"
        f"asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={fade_in_s:.3f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade_out_s:.3f},"
        f"volume={volume_db:.2f}dB"
    )

    args = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-ss",
        f"{start_offset_s:.3f}",
        "-i",
        str(music_path),
        "-filter_complex",
        f"[1:a]{afilter}[mus]",
        "-map",
        "0:v",
        "-map",
        "[mus]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(out_path),
    ]
    _run(args)
    return out_path


def concat_videos(video_paths: list[Path], out_path: Path) -> Path:
    """Concatenate N mp4s losslessly via the concat demuxer, falling back to
    re-encode when the streams don't line up."""
    if not video_paths:
        raise FFmpegError("No videos to concatenate")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_file = out_path.parent / "concat_list.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in video_paths) + "\n"
    )

    try:
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(out_path),
            ]
        )
    except FFmpegError:
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(out_path),
            ]
        )
    return out_path
