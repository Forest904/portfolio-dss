"""Job boundary exposed to the HTTP adapter."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.application.guided import GuidedReport
from app.domain.guided import PreferenceResult


@dataclass(frozen=True, slots=True)
class JobFailure:
    code: str
    message: str
    retryable: bool = True


@dataclass(frozen=True, slots=True)
class GuidedJob:
    id: str
    status: str
    stage: str
    report: GuidedReport | None = None
    error: JobFailure | None = None


class GuidedJobs(Protocol):
    def submit(self, preference: PreferenceResult, capital: Decimal) -> str: ...
    def get(self, job_id: str) -> GuidedJob: ...
