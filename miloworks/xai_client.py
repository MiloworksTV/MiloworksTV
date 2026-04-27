"""Minimal xAI Grok Imagine client (video + image).

REST-only so the pipeline is transparent. Covers:
- Text-to-video         POST /v1/videos/generations
- Image-to-video        POST /v1/videos/generations  (+ image)
- Reference-to-video    POST /v1/videos/generations  (+ reference_images)
- Extend-video          POST /v1/videos/extensions   (not currently used —
                        the returned video accumulates prior content)
- Image generation      POST /v1/images/generations

Docs:
- https://docs.x.ai/developers/model-capabilities/video/generation
- https://docs.x.ai/developers/model-capabilities/images/generation
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

BASE_URL = "https://api.x.ai/v1"
DEFAULT_VIDEO_MODEL = "grok-imagine-video"
DEFAULT_IMAGE_MODEL = "grok-imagine-image"
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 15 * 60  # 15 minutes per scene


class XaiError(RuntimeError):
    pass


@dataclass
class VideoResult:
    url: str
    duration_s: float
    request_id: str
    raw: dict[str, Any]


@dataclass
class ImageResult:
    url: str | None
    b64: str | None
    raw: dict[str, Any]


class XaiClient:
    def __init__(
        self,
        api_key: str,
        video_model: str = DEFAULT_VIDEO_MODEL,
        image_model: str = DEFAULT_IMAGE_MODEL,
    ):
        self.api_key = api_key
        self.video_model = video_model
        self.image_model = image_model
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    # =================== IMAGE ===================

    def generate_image(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "1:1",
        resolution: str = "1k",
    ) -> ImageResult:
        body = {
            "model": self.image_model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        resp = self._session.post(f"{BASE_URL}/images/generations", json=body, timeout=300)
        if resp.status_code >= 400:
            raise XaiError(
                f"Image generation failed ({resp.status_code}): {resp.text[:1000]}"
            )
        data = resp.json()
        first = (data.get("data") or [{}])[0]
        return ImageResult(
            url=first.get("url"),
            b64=first.get("b64_json"),
            raw=data,
        )

    # =================== VIDEO ===================

    def generate_text_to_video(
        self,
        prompt: str,
        *,
        duration: int = 8,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
    ) -> VideoResult:
        body = {
            "model": self.video_model,
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        return self._submit_and_poll("/videos/generations", body)

    def generate_image_to_video(
        self,
        prompt: str,
        image_path: Path,
        *,
        duration: int = 8,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
    ) -> VideoResult:
        image_data_uri = _encode_image_as_data_uri(image_path)
        body = {
            "model": self.video_model,
            "prompt": prompt,
            "image": {"url": image_data_uri},
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        return self._submit_and_poll("/videos/generations", body)

    def generate_reference_to_video(
        self,
        prompt: str,
        reference_image_paths: list[Path],
        *,
        duration: int = 8,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
    ) -> VideoResult:
        if not reference_image_paths:
            raise XaiError("reference_to_video requires at least one image")
        refs = [{"url": _encode_image_as_data_uri(p)} for p in reference_image_paths]
        body = {
            "model": self.video_model,
            "prompt": prompt,
            "reference_images": refs,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        return self._submit_and_poll("/videos/generations", body)

    def extend_video(
        self,
        prompt: str,
        source_video_url: str,
        *,
        duration: int = 8,
    ) -> VideoResult:
        """Extend an existing video from its last frame.

        NOTE: the returned video contains the full accumulated content
        (input + extension), not only the new portion. Chains hit the
        15s input cap fast. Prefer image-to-video with extracted
        last_frame.png for long pipelines.
        """
        body = {
            "model": self.video_model,
            "prompt": prompt,
            "video": {"url": source_video_url},
            "duration": duration,
        }
        return self._submit_and_poll("/videos/extensions", body)

    # =================== INTERNAL ===================

    def _submit_and_poll(self, path: str, body: dict[str, Any]) -> VideoResult:
        start = self._session.post(f"{BASE_URL}{path}", json=body, timeout=60)
        if start.status_code >= 400:
            raise XaiError(f"Submit failed ({start.status_code}): {start.text[:1000]}")
        request_id = start.json().get("request_id")
        if not request_id:
            raise XaiError(f"No request_id in response: {start.text[:500]}")

        deadline = time.monotonic() + POLL_TIMEOUT_S
        transient_fails = 0
        while True:
            try:
                poll = self._session.get(
                    f"{BASE_URL}/videos/{request_id}", timeout=90
                )
            except (
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
            ) as e:
                transient_fails += 1
                if transient_fails >= 6:
                    raise XaiError(
                        f"Too many transient poll errors (last={e!r}, "
                        f"request_id={request_id})"
                    ) from e
                time.sleep(POLL_INTERVAL_S)
                continue
            if poll.status_code in (429, 500, 502, 503, 504):
                transient_fails += 1
                if transient_fails >= 6:
                    raise XaiError(
                        f"Poll failed ({poll.status_code}) repeatedly: "
                        f"{poll.text[:500]}"
                    )
                time.sleep(POLL_INTERVAL_S * 2)
                continue
            if poll.status_code >= 400:
                raise XaiError(f"Poll failed ({poll.status_code}): {poll.text[:1000]}")
            transient_fails = 0
            data = poll.json()
            status = data.get("status")

            if status == "done":
                video = data.get("video") or {}
                url = video.get("url")
                if not url:
                    raise XaiError(f"Done status but no url: {data}")
                return VideoResult(
                    url=url,
                    duration_s=float(video.get("duration", 0)),
                    request_id=request_id,
                    raw=data,
                )
            if status in ("expired", "failed"):
                raise XaiError(f"Generation {status}: {data}")
            if time.monotonic() > deadline:
                raise XaiError(
                    f"Timed out after {POLL_TIMEOUT_S}s (request_id={request_id})"
                )
            time.sleep(POLL_INTERVAL_S)


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    return dest


def _encode_image_as_data_uri(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "image/png")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"
