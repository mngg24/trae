import os
from dataclasses import dataclass

from shared.providers.interfaces import ImageToVideoProvider, LLMProvider, TextToImageProvider, TTSProvider
from shared.providers.mock import MockImageToVideoProvider, MockLLMProvider, MockTextToImageProvider, MockTTSProvider
from shared.providers.pixverse import PixVerseVideoProvider, pixverse_config_from_env


@dataclass(frozen=True)
class Providers:
    llm: LLMProvider
    text_to_image: TextToImageProvider
    image_to_video: ImageToVideoProvider
    tts: TTSProvider


def get_providers() -> Providers:
    mode = os.getenv("PROVIDERS_MODE", "mock").strip().lower()
    if mode not in {"mock", "hybrid"}:
        raise ValueError(f"Unsupported PROVIDERS_MODE={mode!r}")

    llm: LLMProvider = MockLLMProvider()
    text_to_image: TextToImageProvider = MockTextToImageProvider()
    tts: TTSProvider = MockTTSProvider()

    if mode == "hybrid":
        image_to_video: ImageToVideoProvider = PixVerseVideoProvider(pixverse_config_from_env())
    else:
        image_to_video = MockImageToVideoProvider()

    return Providers(llm=llm, text_to_image=text_to_image, image_to_video=image_to_video, tts=tts)
