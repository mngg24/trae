import os
from dataclasses import dataclass

from shared.providers.interfaces import ImageToVideoProvider, LLMProvider, TextToImageProvider, TTSProvider
from shared.providers.mock import MockImageToVideoProvider, MockLLMProvider, MockTextToImageProvider, MockTTSProvider


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    text_to_image: TextToImageProvider
    image_to_video: ImageToVideoProvider
    tts: TTSProvider


def get_providers() -> Providers:
    mode = os.getenv("PROVIDERS_MODE", "mock").strip().lower()
    if mode != "mock":
        raise ValueError(f"Unsupported PROVIDERS_MODE={mode!r}")

    return Providers(
        llm=MockLLMProvider(),
        text_to_image=MockTextToImageProvider(),
        image_to_video=MockImageToVideoProvider(),
        tts=MockTTSProvider(),
    )
