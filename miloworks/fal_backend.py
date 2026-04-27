"""fal.ai backend for Kling 2.6 Pro (image-to-video + text-to-video).

Presents the same `generate_*` surface as `XaiClient` / `WanClient` so the
runner can pick a backend without caring about the underlying provider.

Kling 2.6 Pro specifics:
- Image-to-video endpoint: fal-ai/kling-video/v2.6/pro/image-to-video
  Inputs: prompt, start_image_url, duration ("5" or "10"), generate_audio
  (aspect ratio is inferred from the input image).
- Text-to-video endpoint: fal-ai/kling-video/v2.6/pro/text-to-video
  Inputs: prompt, duration ("5" or "10"), aspect_ratio ("16:9" | "9:16" | "1:1"),
  cfg_scale, generate_audio.

Audio: v2.6 Pro generates native audio (dialogue + SFX) when
`generate_audio=True`; this mirrors grok-imagine-video, so we set it True
by default and send the same SHOT + AUDIO composed prompt the xAI path uses.

Duration: Kling only accepts exactly "5" or "10" seconds — per-scene
durations are clamped to the nearest allowed value (see `_clamp_duration`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fal_client as _fal
import requests

DEFAULT_I2V_MODEL = "fal-ai/kling-video/v2.6/pro/image-to-video"
DEFAULT_T2V_MODEL = "fal-ai/kling-video/v2.6/pro/text-to-video"


class FalError(RuntimeError):
    pass


@dataclass
class VideoResult:
    url: str
    duration_s: float
    request_id: str
    raw: dict[str, Any]


def _clamp_duration(seconds: float) -> str:
    """Kling 2.6 Pro only accepts '5' or '10'. Pick the closer one."""
    if abs(seconds - 5) <= abs(seconds - 10):
        return "5"
    return "10"


class FalClient:
    def __init__(
        self,
        api_key: str,
        *,
        i2v_model: str = DEFAULT_I2V_MODEL,
        t2v_model: str = DEFAULT_T2V_MODEL,
        generate_audio: bool = True,
    ):
        # fal-client reads FAL_KEY from the environment on each call.
        os.environ["FAL_KEY"] = api_key
        self.api_key = api_key
        self.i2v_model = i2v_model
        self.t2v_model = t2v_model
        self.generate_audio = generate_audio

    # =================== VIDEO ===================

    def generate_text_to_video(
        self,
        prompt: str,
        *,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",  # unused: Kling 2.6 Pro fixes its own
    ) -> VideoResult:
        arguments: dict[str, Any] = {
            "prompt": prompt,
            "duration": _clamp_duration(duration),
            "aspect_ratio": aspect_ratio,
            "generate_audio": self.generate_audio,
        }
        return self._subscribe(self.t2v_model, arguments)

    def generate_image_to_video(
        self,
        prompt: str,
        image_path: Path,
        *,
        duration: int = 5,
        aspect_ratio: str = "16:9",  # unused: Kling 2.6 Pro i2v uses image ratio
        resolution: str = "720p",     # unused
    ) -> VideoResult:
        image_url = self._upload(image_path)
        arguments: dict[str, Any] = {
            "prompt": prompt,
            "start_image_url": image_url,
            "duration": _clamp_duration(duration),
            "generate_audio": self.generate_audio,
        }
        return self._subscribe(self.i2v_model, arguments)

    # =================== INTERNAL ===================

    def _upload(self, path: Path) -> str:
        p = Path(path)
        if not p.exists():
            raise FalError(f"image not found: {p}")
        try:
            return _fal.upload_file(str(p))
        except Exception as e:  # noqa: BLE001
            raise FalError(f"fal upload failed for {p}: {e}") from e

    def _subscribe(self, model_id: str, arguments: dict[str, Any]) -> VideoResult:
        try:
            handle = _fal.submit(model_id, arguments=arguments)
            request_id = handle.request_id
            data = handle.get()
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            raise FalError(f"fal generation failed ({model_id}): {msg}") from e

        video = (data or {}).get("video") or {}
        url = video.get("url")
        if not url:
            raise FalError(f"no video url in fal response: {data}")
        duration_str = str(arguments.get("duration", "5"))
        return VideoResult(
            url=url,
            duration_s=float(duration_str),
            request_id=str(request_id),
            raw=data,
        )


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    return dest
