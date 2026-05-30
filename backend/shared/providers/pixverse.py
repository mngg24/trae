import os
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

import httpx

from shared.providers.interfaces import ImageToVideoProvider
from shared.providers.types import GeneratedAsset


@dataclass(frozen=True)
class PixVerseConfig:
    api_key: str
    base_url: str = "https://app-api.pixverse.ai"
    model: str = "v6"
    aspect_ratio: str = "9:16"
    duration: int = 5
    quality: str = "720p"
    poll_interval_sec: float = 5.0
    max_poll_sec: float = 300.0


class PixVerseVideoProvider(ImageToVideoProvider):
    def __init__(self, config: PixVerseConfig):
        self._cfg = config

    @property
    def provider_name(self) -> str:
        return "pixverse"

    def generate_video(self, image_uri: str, motion_prompt: str, *, seed: int) -> GeneratedAsset:
        prompt = self._prompt_from_image_uri(image_uri)
        fused_prompt = f"{prompt}. Motion: {motion_prompt}".strip()

        trace_id = str(uuid.uuid4())
        submit_url = f"{self._cfg.base_url}/openapi/v2/video/text/generate"

        payload = {
            "prompt": fused_prompt,
            "model": self._cfg.model,
            "aspect_ratio": self._cfg.aspect_ratio,
            "duration": self._cfg.duration,
            "quality": self._cfg.quality,
            "motion_mode": "normal",
            "seed": int(seed) % 2147483647,
            "water_mark": False,
        }
        headers = {
            "API-KEY": self._cfg.api_key,
            "Ai-Trace-Id": trace_id,
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=60.0) as client:
            res = client.post(submit_url, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()
            video_id = data.get("video_id") or data.get("id") or data.get("data", {}).get("video_id")
            if not video_id:
                raise ValueError("PixVerse submission did not return video_id")

            result_url = f"{self._cfg.base_url}/openapi/v2/video/result/{video_id}"
            deadline = time.monotonic() + self._cfg.max_poll_sec

            last_payload: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                r = client.get(result_url, headers=headers)
                r.raise_for_status()
                last_payload = r.json()
                status = last_payload.get("status")
                if status == 1:
                    url = last_payload.get("url") or last_payload.get("data", {}).get("url")
                    if not url:
                        raise ValueError("PixVerse job succeeded but no url returned")
                    return GeneratedAsset(
                        provider=self.provider_name,
                        uri=str(url),
                        metadata={
                            "video_id": video_id,
                            "trace_id": trace_id,
                            "status": status,
                            "prompt": fused_prompt,
                        },
                    )
                if status in (5, "5"):
                    time.sleep(self._cfg.poll_interval_sec)
                    continue
                if status in (7, "7"):
                    raise ValueError("PixVerse moderation failure")
                if status in (8, "8"):
                    raise ValueError("PixVerse generation failed")
                time.sleep(self._cfg.poll_interval_sec)

        raise TimeoutError("PixVerse job polling timed out")

    @staticmethod
    def _prompt_from_image_uri(image_uri: str) -> str:
        if image_uri.startswith("prompt://"):
            return unquote(image_uri.removeprefix("prompt://"))
        return image_uri


def pixverse_config_from_env() -> PixVerseConfig:
    api_key = os.getenv("PIXVERSE_API_KEY")
    if not api_key:
        raise ValueError("PIXVERSE_API_KEY is required for PixVerse provider")

    duration = int(os.getenv("PIXVERSE_DURATION_SEC", "5"))
    poll_interval_sec = float(os.getenv("PIXVERSE_POLL_INTERVAL_SEC", "5"))
    max_poll_sec = float(os.getenv("PIXVERSE_MAX_POLL_SEC", "300"))
    return PixVerseConfig(
        api_key=api_key,
        base_url=os.getenv("PIXVERSE_BASE_URL", "https://app-api.pixverse.ai"),
        model=os.getenv("PIXVERSE_MODEL", "v6"),
        aspect_ratio=os.getenv("PIXVERSE_ASPECT_RATIO", "9:16"),
        duration=duration,
        quality=os.getenv("PIXVERSE_QUALITY", "720p"),
        poll_interval_sec=poll_interval_sec,
        max_poll_sec=max_poll_sec,
    )

