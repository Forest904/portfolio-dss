import json
import socket
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.application.backtest import (
    BacktestSettings,
    FrozenSnapshot,
    acquire_snapshot,
    build_engine,
    canonical_json,
    content_hash,
    report_payload,
)
from app.cli.backtest import main
from app.domain.errors import DomainValidationError
from app.infrastructure.backtest_report import render_html
from app.infrastructure.optimization import ScipyMeanVarianceOptimizer
from tests.domain.test_backtest import fixture
from tests.helpers import FakeMarketDataProvider, FakeUniverseProvider, make_universe

DEMO = Path(__file__).resolve().parents[3] / "examples" / "backtest" / "week9"


def synthetic_snapshot() -> FrozenSnapshot:
    config, prices = fixture()
    provider = FakeMarketDataProvider(
        {
            asset: [(d, str(p)) for d, p in zip(prices.dates, row, strict=True)]
            for asset, row in zip(prices.asset_ids, prices.adjusted_close, strict=True)
        }
    )
    return acquire_snapshot(config, provider, FakeUniverseProvider(make_universe("A", "B")))


def test_snapshot_roundtrip_and_integrity() -> None:
    config, prices = fixture()
    snapshot = synthetic_snapshot()
    assert snapshot.validate_for(config) == prices
    assert FrozenSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    with pytest.raises(DomainValidationError, match="hash mismatch"):
        snapshot.model_copy(update={"universe_as_of": date(2000, 1, 1)}).validate_for(config)
    with pytest.raises(DomainValidationError, match="basket/order"):
        snapshot.validate_for(replace(config, tickers=("B", "A")))
    with pytest.raises(DomainValidationError, match="bounds"):
        snapshot.validate_for(replace(config, history_start=date(2019, 1, 1)))


@pytest.mark.parametrize("asset", ["A", "SPY"])
def test_acquisition_rejects_missing_session_without_intersection(asset: str) -> None:
    config, prices = fixture()
    raw = {
        a: [(d, str(p)) for d, p in zip(prices.dates, row, strict=True)]
        for a, row in zip(prices.asset_ids, prices.adjusted_close, strict=True)
    }
    del raw[asset][5]
    with pytest.raises(DomainValidationError, match="session mismatch"):
        acquire_snapshot(
            config, FakeMarketDataProvider(raw), FakeUniverseProvider(make_universe("A", "B"))
        )


def test_acquisition_rejects_unknown_membership_and_duplicate_dates() -> None:
    config, prices = fixture()
    provider = FakeMarketDataProvider(
        {
            a: [(d, str(p)) for d, p in zip(prices.dates, row, strict=True)]
            for a, row in zip(prices.asset_ids, prices.adjusted_close, strict=True)
        }
    )
    with pytest.raises(DomainValidationError, match="membership"):
        acquire_snapshot(config, provider, FakeUniverseProvider(make_universe("A")))
    provider.prices["A"].insert(0, provider.prices["A"][0])
    with pytest.raises(DomainValidationError, match="duplicates"):
        acquire_snapshot(config, provider, FakeUniverseProvider(make_universe("A", "B")))


@pytest.mark.parametrize(
    "payload",
    [
        '{"training_returns": true}',
        '{"rebalance_sessions": 2.5}',
        '{"window_modes": ["unknown"]}',
        '{"unknown_field": 1}',
        '{"initial_capital": true}',
        '{"initial_capital": "10000"}',
    ],
)
def test_strict_configuration_boundary(payload: str) -> None:
    with pytest.raises(ValidationError):
        BacktestSettings.model_validate_json(payload)


def test_html_metrics_audit_and_no_external_assets() -> None:
    config, prices = fixture()
    report = build_engine(ScipyMeanVarianceOptimizer(), "test").run(config, prices)
    snapshot = synthetic_snapshot()
    payload = report_payload(report, snapshot, {"test": "1"})
    assert payload["report_hash"] == content_hash(
        {k: v for k, v in payload.items() if k != "report_hash"}
    )
    html = render_html(report, str(payload["report_hash"]), snapshot.snapshot_hash)
    assert html == render_html(report, str(payload["report_hash"]), snapshot.snapshot_hash)
    soup = BeautifulSoup(html, "html.parser")
    assert len(soup.select("svg[role=img]")) == 2
    assert not soup.select("script[src], link[href], img[src]")
    rows = soup.select("section")[1].select("tbody tr")
    assert len(rows) == 6
    for row, strategy in zip(rows, report.strategies, strict=True):
        assert f"${strategy.performance.terminal_value_usd:,.2f}" in row.get_text()
        assert f"{strategy.performance.total_return:.2%}" in row.get_text()
    assert len(soup.select("pre")) == sum(len(s.decisions) for s in report.strategies)
    assert "not forecasts or guarantees" in soup.get_text()


def test_cli_replay_is_offline_deterministic_and_failures_do_not_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config, _ = fixture()
    snapshot = synthetic_snapshot()
    config_path, snapshot_path = tmp_path / "config.json", tmp_path / "snapshot.json"
    config_path.write_text(canonical_json(config), encoding="utf-8")
    snapshot_path.write_text(snapshot.model_dump_json(), encoding="utf-8")

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline replay attempted network access")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    common = ["run", "--config", str(config_path), "--snapshot", str(snapshot_path)]
    for directory in ("one", "two"):
        assert main([*common, "--output", str(tmp_path / directory)]) == 0
    for filename in ("report.html", "report.json"):
        assert (tmp_path / "one" / filename).read_bytes() == (
            tmp_path / "two" / filename
        ).read_bytes()
    bad = snapshot.model_copy(update={"snapshot_hash": "tampered"})
    snapshot_path.write_text(bad.model_dump_json(), encoding="utf-8")
    assert main([*common, "--output", str(tmp_path / "failure")]) == 1
    assert not (tmp_path / "failure").exists()
    assert "hash mismatch" in capsys.readouterr().err


def test_frozen_real_market_demo_replays_with_shared_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = BacktestSettings.model_validate_json((DEMO / "config.json").read_text()).to_domain()
    snapshot = FrozenSnapshot.model_validate_json((DEMO / "snapshot.json").read_text())

    def no_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("real-data replay attempted network access")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    engine = build_engine(ScipyMeanVarianceOptimizer(), "test")
    prices = snapshot.validate_for(config)
    report = engine.run(config, prices)
    assert canonical_json(report) == canonical_json(engine.run(config, prices))
    assert len(report.strategies) == 6
    for strategy in report.strategies:
        assert strategy.daily[0].observed_on == date(2019, 1, 2)
        assert strategy.daily[-1].observed_on == date(2025, 12, 31)
        assert strategy.daily[0].equity_usd == 10_000
        assert tuple(p.observed_on for p in strategy.daily) == tuple(
            p.observed_on for p in report.strategies[0].daily
        )
    # The published output is checked with tolerances across platforms/solver builds.
    published = json.loads((DEMO / "report" / "report.json").read_text())
    for actual, expected in zip(report.strategies, published["report"]["strategies"], strict=True):
        assert actual.performance.terminal_value_usd == pytest.approx(
            expected["performance"]["terminal_value_usd"], rel=1e-6
        )
