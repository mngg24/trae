from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from .models import JobStateOut, OutputsOut


@dataclass
class JobEntry:
    job_id: str
    project_id: str
    created_at: datetime
    state: JobStateOut
    outputs: OutputsOut | None = None


class JobStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: dict[str, JobEntry] = {}

    def create(self, entry: JobEntry) -> None:
        with self._lock:
            self._jobs[entry.job_id] = entry

    def get(self, job_id: str) -> JobEntry | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_state(self, job_id: str, state: JobStateOut) -> None:
        with self._lock:
            e = self._jobs.get(job_id)
            if e is None:
                return
            e.state = state

    def update_outputs(self, job_id: str, outputs: OutputsOut | None) -> None:
        with self._lock:
            e = self._jobs.get(job_id)
            if e is None:
                return
            e.outputs = outputs

