"""Validated HTTP contracts for the guided builder."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import field_validator

from app.api.schemas import ApiModel, ErrorResponse
from app.application.estimators import EstimatorId
from app.application.guided import GuidedReport
from app.application.guided_jobs import GuidedJobs, JobFailure
from app.domain.guided import PreferenceAnswers, map_preferences, validate_capital

router = APIRouter()


class GuidedRequest(ApiModel):
    expected_return_estimator: EstimatorId = "historical_mean"
    version: Literal["guided-preferences-v1"]
    answers: PreferenceAnswers
    capital: Decimal

    @field_validator("capital")
    @classmethod
    def valid_capital(cls, value: Decimal) -> Decimal:
        return validate_capital(value)


class AcceptedJob(ApiModel):
    id: str


class GuidedJobResponse(ApiModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: Literal[
        "queued",
        "loading_universe",
        "loading_prices",
        "checking_coverage",
        "calculating_alternatives",
        "completed",
        "failed",
    ]
    report: GuidedReport | None = None
    error: JobFailure | None = None


@router.post(
    "/api/v1/guided-recommendations",
    status_code=202,
    response_model=AcceptedJob,
    responses={422: {"model": ErrorResponse}},
    tags=["guided"],
)
def submit_guided(payload: GuidedRequest, request: Request) -> AcceptedJob:
    jobs: GuidedJobs = request.app.state.guided_jobs
    return AcceptedJob(
        id=jobs.submit(
            map_preferences(payload.answers, payload.version),
            payload.capital,
            payload.expected_return_estimator,
        )
    )


@router.get(
    "/api/v1/guided-recommendations/{job_id}",
    response_model=GuidedJobResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["guided"],
)
def get_guided(job_id: str, request: Request) -> GuidedJobResponse:
    jobs: GuidedJobs = request.app.state.guided_jobs
    return GuidedJobResponse.model_validate(jobs.get(job_id), from_attributes=True)
