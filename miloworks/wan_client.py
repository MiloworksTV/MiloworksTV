"""ComfyUI-backed Wan 2.2 video client.

Talks to a ComfyUI server (running on a vast.ai GPU box) via its built-in
REST API. Uses the workflow templates in `milo/workflows/` as skeletons
and fills in per-scene parameters (prompt, start/end images, dimensions,
length, seed, output prefix).

Presents the same `generate_*` surface as `XaiClient` so the runner can
pick a backend without caring about the underlying provider.

Audio: Wan 2.2 (base) does NOT generate audio. Videos come out silent.
A later step can mux TTS + SFX + score.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

POLL_INTERVAL_S = 3
POLL_TIMEOUT_S = 30 * 60


# Generic negative prompt baked in. Users override via style bible if needed.
DEFAULT_NEGATIVE_PROMPT = (
    "low quality, blurry, jpeg artifacts, watermark, text, logo, "
    "extra limbs, deformed, malformed, 3D render, photorealistic, "
    "live action, cgi, ugly, static, frozen"
)

# Wan 2.2 native 16 fps. length must be 4n+1.
FPS = 16.0


class WanError(RuntimeError):
    pass


@dataclass
class VideoResult:
    url: str            # file path on the ComfyUI server (absolute)
    duration_s: float
    request_id: str     # ComfyUI prompt_id
    raw: dict[str, Any]


def _frames_for_duration(seconds: float) -> int:
    """Wan 2.2 length must be 4n+1. Clamp to [5, 241] (≈15s)."""
    n = max(1, round(seconds * FPS))
    n = ((n - 1) // 4) * 4 + 1  # nearest 4n+1, rounding down
    return max(5, min(241, n))


class WanClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8188",
        workflows_dir: Path | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = uuid.uuid4().hex
        self._session = requests.Session()
        self.workflows_dir = (
            workflows_dir or Path(__file__).parent / "workflows"
        )

    # =================== PUBLIC API ===================

    def generate_image_to_video(
        self,
        prompt: str,
        start_frame: Path,
        *,
        duration: float,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        seed: int = 42,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        filename_prefix: str = "wan_scene",
    ) -> VideoResult:
        w, h = _resolution_to_wh(aspect_ratio, resolution)
        length = _frames_for_duration(duration)
        start_name = self._upload_image(start_frame)
        wf = self._load_workflow("wan22_i2v.json")
        _fill_common(wf, prompt, negative_prompt, seed, length, w, h, filename_prefix)
        wf["start_image"]["inputs"]["image"] = start_name
        wf["resize_start"]["inputs"]["width"] = w
        wf["resize_start"]["inputs"]["height"] = h
        return self._run_workflow(wf, expected_duration=length / FPS)

    def generate_flf2v(
        self,
        prompt: str,
        start_frame: Path,
        end_frame: Path,
        *,
        duration: float,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        seed: int = 42,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        filename_prefix: str = "wan_scene",
    ) -> VideoResult:
        w, h = _resolution_to_wh(aspect_ratio, resolution)
        length = _frames_for_duration(duration)
        start_name = self._upload_image(start_frame)
        end_name = self._upload_image(end_frame)
        wf = self._load_workflow("wan22_flf2v.json")
        _fill_common(wf, prompt, negative_prompt, seed, length, w, h, filename_prefix)
        wf["start_image"]["inputs"]["image"] = start_name
        wf["end_image"]["inputs"]["image"] = end_name
        for k in ("resize_start", "resize_end"):
            wf[k]["inputs"]["width"] = w
            wf[k]["inputs"]["height"] = h
        return self._run_workflow(wf, expected_duration=length / FPS)

    # =================== INTERNAL ===================

    def _load_workflow(self, name: str) -> dict[str, Any]:
        raw = (self.workflows_dir / name).read_text()
        wf = json.loads(raw)
        # Drop metadata keys (leading underscore).
        return {k: v for k, v in wf.items() if not k.startswith("_")}

    def _upload_image(self, path: Path) -> str:
        """Upload image to ComfyUI input folder; returns server-side filename."""
        path = Path(path)
        if not path.exists():
            raise WanError(f"image not found: {path}")
        # Use unique name so repeat scenes don't collide.
        server_name = f"{uuid.uuid4().hex[:12]}_{path.name}"
        with path.open("rb") as f:
            r = self._session.post(
                f"{self.base_url}/upload/image",
                files={"image": (server_name, f, "image/png")},
                data={"overwrite": "true", "type": "input"},
                timeout=120,
            )
        if r.status_code >= 400:
            raise WanError(f"upload failed ({r.status_code}): {r.text[:500]}")
        return r.json().get("name", server_name)

    def _run_workflow(
        self, workflow: dict[str, Any], *, expected_duration: float
    ) -> VideoResult:
        body = {"prompt": workflow, "client_id": self.client_id}
        r = self._session.post(f"{self.base_url}/prompt", json=body, timeout=60)
        if r.status_code >= 400:
            raise WanError(f"submit failed ({r.status_code}): {r.text[:1500]}")
        prompt_id = r.json().get("prompt_id")
        if not prompt_id:
            raise WanError(f"no prompt_id in response: {r.text[:500]}")

        deadline = time.monotonic() + POLL_TIMEOUT_S
        while True:
            try:
                h = self._session.get(
                    f"{self.base_url}/history/{prompt_id}", timeout=90
                )
            except requests.exceptions.RequestException:
                time.sleep(POLL_INTERVAL_S)
                continue
            if h.status_code >= 400:
                time.sleep(POLL_INTERVAL_S)
                continue
            hist = h.json().get(prompt_id)
            if hist:
                status = hist.get("status", {})
                if status.get("status_str") == "error":
                    raise WanError(
                        f"generation error: {json.dumps(status)[:2000]}"
                    )
                if status.get("completed"):
                    return self._extract_video(
                        hist, prompt_id, expected_duration
                    )
            if time.monotonic() > deadline:
                raise WanError(f"timed out (prompt_id={prompt_id})")
            time.sleep(POLL_INTERVAL_S)

    def _extract_video(
        self, history: dict[str, Any], prompt_id: str, expected_duration: float
    ) -> VideoResult:
        outputs = history.get("outputs", {})
        for node_id, node_out in outputs.items():
            for key in ("videos", "gifs", "images"):
                items = node_out.get(key) or []
                for item in items:
                    if item.get("type") == "output":
                        fname = item.get("filename", "")
                        if fname.lower().endswith((".mp4", ".webm", ".mov")):
                            return VideoResult(
                                url=self._view_url(item),
                                duration_s=expected_duration,
                                request_id=prompt_id,
                                raw=history,
                            )
        raise WanError(
            f"no video output in history for {prompt_id}: "
            f"{json.dumps(outputs)[:1000]}"
        )

    def _view_url(self, item: dict[str, Any]) -> str:
        from urllib.parse import urlencode

        params = {
            "filename": item.get("filename", ""),
            "subfolder": item.get("subfolder", ""),
            "type": item.get("type", "output"),
        }
        return f"{self.base_url}/view?{urlencode(params)}"


def _resolution_to_wh(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    """Map (aspect, resolution) → (width, height).

    Wan 2.2 14B sweet spots are 1280x720 (720p 16:9) and 832x480 (480p 16:9).
    Dimensions must be multiples of 16.
    """
    if aspect_ratio != "16:9":
        # Fallback: treat as 720p 16:9 until we add other ratios.
        pass
    if resolution.lower() in ("720p", "hd"):
        return 1280, 720
    if resolution.lower() in ("480p", "sd"):
        return 832, 480
    return 1280, 720


def _fill_common(
    wf: dict[str, Any],
    positive: str,
    negative: str,
    seed: int,
    length: int,
    width: int,
    height: int,
    filename_prefix: str,
) -> None:
    wf["positive_prompt"]["inputs"]["text"] = positive
    wf["negative_prompt"]["inputs"]["text"] = negative
    wf["flf"]["inputs"]["width"] = width
    wf["flf"]["inputs"]["height"] = height
    wf["flf"]["inputs"]["length"] = length
    wf["sampler_high"]["inputs"]["noise_seed"] = seed
    wf["sampler_low"]["inputs"]["noise_seed"] = seed
    wf["save_video"]["inputs"]["filename_prefix"] = filename_prefix


def download(url: str, dest: Path) -> Path:
    """Download a /view URL to local disk."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    return dest
