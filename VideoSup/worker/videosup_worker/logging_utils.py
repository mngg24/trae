from __future__ import annotations

import json
import logging
from typing import Any, Optional


def log_event(
    logger: logging.Logger,
    *,
    level: int = logging.INFO,
    job_id: str,
    step: str,
    duration_ms: Optional[int] = None,
    message: str,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "job_id": job_id,
        "step": step,
        "message": message,
    }
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    if fields:
        payload.update(fields)
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))
