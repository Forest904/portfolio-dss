"""Generate frozen, network-free Portfolio DSS case-study reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.application.backtest import FrozenSnapshot, canonical_json
from app.application.case_studies import (
    CaseStudyManifest,
    generate_case_studies,
    render_case_studies_html,
)
from app.application.errors import ApplicationError
from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
from app.infrastructure.simulation import NumpySimulationEngine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = CaseStudyManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
        snapshot = FrozenSnapshot.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
        payload = generate_case_studies(
            manifest, snapshot, ScipyEfficientFrontierGenerator(), NumpySimulationEngine()
        )
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "report.json").write_text(canonical_json(payload) + "\n", encoding="utf-8")
        (args.output / "report.html").write_text(
            render_case_studies_html(payload), encoding="utf-8"
        )
        print(f"Case studies: {args.output / 'report.html'} ({payload['report_hash']})")
        return 0
    except (
        OSError,
        ValueError,
        ArithmeticError,
        ValidationError,
        json.JSONDecodeError,
        ApplicationError,
    ) as exc:
        print(f"Case-study generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
