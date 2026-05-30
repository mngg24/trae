from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GeneratedAsset:
    provider: str
    uri: str
    metadata: dict[str, Any]
