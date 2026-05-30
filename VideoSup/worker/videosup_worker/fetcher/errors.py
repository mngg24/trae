from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorStrategy(str, Enum):
    RETRY = "retry"
    ABORT = "abort"


class ErrorTaxonomy(str, Enum):
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    BAD_MEDIA = "BAD_MEDIA"
    FFMPEG_FAILED = "FFMPEG_FAILED"
    STORAGE_FAILED = "STORAGE_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"


@dataclass(frozen=True)
class ErrorDescriptor:
    code: ErrorTaxonomy
    message: str
    strategy: ErrorStrategy


class FetcherError(RuntimeError):
    def __init__(self, descriptor: ErrorDescriptor, *, details: Optional[str] = None):
        self.descriptor = descriptor
        self.details = details
        msg = (
            descriptor.message
            if details is None
            else f"{descriptor.message}: {details}"
        )
        super().__init__(msg)
