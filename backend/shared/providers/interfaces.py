from abc import ABC, abstractmethod

from shared.providers.types import GeneratedAsset


class LLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def generate_blueprint(self, topic: str, target_duration_seconds: int, *, seed: int) -> dict: ...


class TextToImageProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def generate_image(self, prompt: str, *, seed: int) -> GeneratedAsset: ...


class ImageToVideoProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def generate_video(self, image_uri: str, motion_prompt: str, *, seed: int) -> GeneratedAsset: ...


class TTSProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def synthesize(self, text: str, *, voice: str, seed: int) -> GeneratedAsset: ...
