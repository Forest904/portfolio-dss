"""Bounded retrieval over the existing persistent read-through provider."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app.domain import DEFAULT_FINANCIAL_CONVENTIONS, ExternalDataUnavailableError
from app.domain.bulk_history import BulkHistory, HistoryFailure
from app.domain.market_data import AssetPriceSeries, DataProvenance, MarketDataProvider


class BoundedBulkHistoryProvider:
    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    def get_bulk_history(
        self,
        asset_ids: tuple[str, ...],
        start: date,
        end: date,
    ) -> BulkHistory:
        conventions = DEFAULT_FINANCIAL_CONVENTIONS

        def fetch(ids: tuple[str, ...]) -> BulkHistory:
            series: dict[str, AssetPriceSeries] = {}
            provenance: list[DataProvenance] = []
            failures: list[HistoryFailure] = []
            try:
                history = self._provider.get_price_history(
                    ids,
                    start,
                    end,
                    conventions.return_frequency,
                    conventions.price_field,
                )
                series.update((s.asset_id, s) for s in history.series if s.observations)
                provenance.append(history.provenance)
            except ExternalDataUnavailableError:
                pass
            for asset in ids:
                if asset in series:
                    continue
                try:
                    retry = self._provider.get_price_history(
                        (asset,),
                        start,
                        end,
                        conventions.return_frequency,
                        conventions.price_field,
                    )
                    item = next((s for s in retry.series if s.asset_id == asset), None)
                    if item is None or not item.observations:
                        raise ExternalDataUnavailableError("No adjusted-close observations")
                    series[asset] = item
                    provenance.append(retry.provenance)
                except ExternalDataUnavailableError:
                    failures.append(HistoryFailure(asset, "Prices unavailable after one retry"))
            return BulkHistory(
                tuple(series[a] for a in ids if a in series), tuple(failures), tuple(provenance)
            )

        batches = tuple(asset_ids[i : i + 25] for i in range(0, len(asset_ids), 25))
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = tuple(executor.map(fetch, batches))
        return BulkHistory(
            tuple(s for result in results for s in result.series),
            tuple(f for result in results for f in result.failures),
            tuple(p for result in results for p in result.provenance),
        )
