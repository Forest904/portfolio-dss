"""Schemas owned by the HTTP boundary."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    status: Literal["ok"]
    service: Literal["portfolio-dss-api"]
    version: str


class ErrorResponse(ApiModel):
    code: str
    message: str
    details: dict[str, Any]


class PositionRequest(ApiModel):
    ticker: str = Field(min_length=1)
    quantity: Decimal


class PortfolioValuationRequest(ApiModel):
    positions: list[PositionRequest] = Field(min_length=1)
    as_of: date | None = None


class ProvenanceResponse(ApiModel):
    provider: str
    retrieved_at: datetime
    content_hash: str
    stale_fallback: bool


class MoneyResponse(ApiModel):
    amount: Decimal
    currency: Literal["USD"]


class ValuationPositionResponse(ApiModel):
    ticker: str
    quantity: Decimal
    unit_price: MoneyResponse
    market_value: MoneyResponse
    weight: Decimal


class UniverseReferenceResponse(ApiModel):
    id: Literal["sp500"]
    as_of: date
    provenance: ProvenanceResponse


class PortfolioValuationResponse(ApiModel):
    requested_as_of: date | None
    valued_on: date
    total_market_value: MoneyResponse
    positions: list[ValuationPositionResponse]
    universe: UniverseReferenceResponse
    price_data: ProvenanceResponse
    snapshot_hash: str
    assumptions: list[str]


class BenchmarkResponse(ApiModel):
    asset_id: str
    name: str


class AssetResponse(ApiModel):
    ticker: str
    name: str
    exchange: str
    currency: Literal["USD"]
    sector: str
    industry: str | None


class UniverseResponse(ApiModel):
    id: Literal["sp500"]
    name: str
    as_of: date
    benchmark: BenchmarkResponse
    assets: list[AssetResponse]
    provenance: ProvenanceResponse
    assumptions: list[str]
