import hashlib
import json
import random

from shared.providers.interfaces import ImageToVideoProvider, LLMProvider, TextToImageProvider, TTSProvider
from shared.providers.types import GeneratedAsset


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _seed_int(*parts: object) -> int:
    return int(_stable_hash(parts)[:16], 16)


def _mock_uri(kind: str, fingerprint: object) -> str:
    return f"mock://{kind}/{_stable_hash(fingerprint)}"


class MockLLMProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "mock-llm"

    def generate_blueprint(self, topic: str, target_duration_seconds: int, *, seed: int) -> dict:
        base_scene_count = max(1, min(12, round(target_duration_seconds / 12)))
        rng = random.Random(_seed_int(self.provider_name, topic, target_duration_seconds, seed))
        estimated_scene_count = max(1, min(12, base_scene_count + rng.choice([-1, 0, 0, 1])))

        intros = [
            "Discover",
            "Explore",
            "Uncover",
            "Learn about",
            "Dive into",
        ]
        camera_moves = [
            "Slow cinematic pan",
            "Gentle push-in",
            "Subtle handheld drift",
            "Slow tilt down",
            "Smooth dolly forward",
        ]
        styles = [
            "Cinematic, photorealistic, 8k, dramatic lighting, vertical 9:16",
            "Documentary style, natural light, high detail, vertical 9:16",
            "Moody cinematic lighting, shallow depth of field, vertical 9:16",
        ]

        durations = [target_duration_seconds // estimated_scene_count] * estimated_scene_count
        for i in range(target_duration_seconds % estimated_scene_count):
            durations[i] += 1

        scenes: list[dict] = []
        for idx in range(1, estimated_scene_count + 1):
            scene_rng = random.Random(_seed_int(self.provider_name, topic, target_duration_seconds, seed, idx))
            intro = scene_rng.choice(intros)
            style = scene_rng.choice(styles)
            camera = scene_rng.choice(camera_moves)

            narration = f"{intro} {topic}. Scene {idx} highlights a key moment with a clear takeaway."
            image_prompt = f"{style}. Subject: {topic}. Scene {idx}. High realism, clean composition."
            camera_suggestion = f"{camera}, maintain subject focus."

            scenes.append(
                {
                    "scene_number": idx,
                    "narration_script": narration,
                    "image_generation_prompt": image_prompt,
                    "camera_movement_suggestion": camera_suggestion,
                    "estimated_duration_seconds": durations[idx - 1],
                }
            )

        return {
            "project_meta": {
                "topic": topic,
                "target_duration_seconds": target_duration_seconds,
                "estimated_scene_count": estimated_scene_count,
            },
            "scenes": scenes,
        }


class MockTextToImageProvider(TextToImageProvider):
    @property
    def provider_name(self) -> str:
        return "mock-text-to-image"

    def generate_image(self, prompt: str, *, seed: int) -> GeneratedAsset:
        uri = _mock_uri("image", {"provider": self.provider_name, "prompt": prompt, "seed": seed})
        return GeneratedAsset(
            provider=self.provider_name,
            uri=uri,
            metadata={"prompt": prompt, "seed": seed, "fingerprint": _stable_hash((prompt, seed))},
        )


class MockImageToVideoProvider(ImageToVideoProvider):
    @property
    def provider_name(self) -> str:
        return "mock-image-to-video"

    def generate_video(self, image_uri: str, motion_prompt: str, *, seed: int) -> GeneratedAsset:
        uri = _mock_uri(
            "video",
            {
                "provider": self.provider_name,
                "image_uri": image_uri,
                "motion_prompt": motion_prompt,
                "seed": seed,
            },
        )
        return GeneratedAsset(
            provider=self.provider_name,
            uri=uri,
            metadata={
                "image_uri": image_uri,
                "motion_prompt": motion_prompt,
                "seed": seed,
                "fingerprint": _stable_hash((image_uri, motion_prompt, seed)),
            },
        )


class MockTTSProvider(TTSProvider):
    @property
    def provider_name(self) -> str:
        return "mock-tts"

    def synthesize(self, text: str, *, voice: str, seed: int) -> GeneratedAsset:
        uri = _mock_uri(
            "audio",
            {
                "provider": self.provider_name,
                "text": text,
                "voice": voice,
                "seed": seed,
            },
        )
        return GeneratedAsset(
            provider=self.provider_name,
            uri=uri,
            metadata={
                "text": text,
                "voice": voice,
                "seed": seed,
                "fingerprint": _stable_hash((text, voice, seed)),
            },
        )
