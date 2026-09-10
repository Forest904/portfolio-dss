"""Deterministic property-test configuration."""

from hypothesis import settings

settings.register_profile("portfolio-dss", derandomize=True, database=None, max_examples=75)
settings.load_profile("portfolio-dss")
