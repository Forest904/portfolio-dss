"""Schemas owned by the HTTP boundary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response returned by the operational health endpoint."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: Literal["portfolio-dss-api"]
    version: str
