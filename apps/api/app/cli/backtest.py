"""Acquire a frozen snapshot or replay it without network access."""

from __future__ import annotations

import argparse
import platform
import sys
from importlib.metadata import version
from pathlib import Path

from app.application.backtest import (
    BacktestSettings,
    FrozenSnapshot,
    acquire_snapshot,
    build_engine,
    canonical_json,
    report_payload,
)
from app.domain.errors import ExternalDataUnavailableError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("snapshot", "run"):
        sub = commands.add_parser(command)
        sub.add_argument("--config", type=Path, required=True, help="JSON configuration")
        sub.add_argument("--snapshot", type=Path, required=True, help="Frozen price snapshot JSON")
        if command == "run":
            sub.add_argument("--output", type=Path, required=True, help="Output directory")
    args = parser.parse_args(argv)
    try:
        settings = BacktestSettings.model_validate_json(args.config.read_text(encoding="utf-8"))
        config = settings.to_domain()
        if args.command == "snapshot":
            # Imports and provider construction are deliberately absent from the replay path.
            from app.core.config import load_settings
            from app.infrastructure.cache import SQLiteCache
            from app.infrastructure.wikipedia import WikipediaSP500Provider
            from app.infrastructure.yahoo import YahooFinanceMarketDataProvider

            cache = SQLiteCache(load_settings().cache_path)
            snapshot = acquire_snapshot(
                config,
                YahooFinanceMarketDataProvider(cache, timeout_seconds=30),
                WikipediaSP500Provider(cache, timeout_seconds=30),
            )
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            args.snapshot.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
            print(f"Snapshot: {args.snapshot} ({snapshot.snapshot_hash})")
        else:
            from app.infrastructure.backtest_report import render_html
            from app.infrastructure.optimization import ScipyMeanVarianceOptimizer

            snapshot = FrozenSnapshot.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
            prices = snapshot.validate_for(config)
            runtime = {name: version(name) for name in ("numpy", "scipy", "matplotlib")}
            runtime["python"] = platform.python_version()
            solver = f"scipy-{runtime['scipy']}-SLSQP; ftol=1e-10; maxiter=1000; equal-weight-start"
            report = build_engine(ScipyMeanVarianceOptimizer(), solver).run(config, prices)
            payload = report_payload(report, snapshot, runtime)
            serialized = canonical_json(payload) + "\n"
            html = render_html(report, str(payload["report_hash"]), snapshot.snapshot_hash)
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "report.json").write_text(serialized, encoding="utf-8")
            (args.output / "report.html").write_text(html, encoding="utf-8")
            print(f"Report: {args.output / 'report.html'} ({payload['report_hash']})")
        return 0
    except (ValueError, ArithmeticError, OSError, ExternalDataUnavailableError) as exc:
        print(f"Backtest failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
