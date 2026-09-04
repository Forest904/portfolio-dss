from datetime import date

from app.domain import (
    SP500_BENCHMARK_ASSET_ID,
    SP500_BENCHMARK_NAME,
    SP500_UNIVERSE_ID,
    InvestmentUniverse,
    MarketUniverseProvider,
)


class InMemoryUniverseProvider:
    def get_universe(self, universe_id: str, as_of: date) -> InvestmentUniverse:
        assert universe_id == SP500_UNIVERSE_ID
        return InvestmentUniverse(
            id=universe_id,
            name="S&P 500",
            as_of_date=as_of,
            asset_ids=("AAPL", "MSFT"),
            benchmark_asset_id=SP500_BENCHMARK_ASSET_ID,
            benchmark_name=SP500_BENCHMARK_NAME,
        )


def load_universe(provider: MarketUniverseProvider) -> InvestmentUniverse:
    return provider.get_universe(SP500_UNIVERSE_ID, date(2026, 9, 4))


def test_provider_contract_keeps_benchmark_separate_from_membership() -> None:
    universe = load_universe(InMemoryUniverseProvider())

    assert universe.benchmark_asset_id == "SPY"
    assert "total-return proxy" in universe.benchmark_name
    assert universe.benchmark_asset_id not in universe.asset_ids
