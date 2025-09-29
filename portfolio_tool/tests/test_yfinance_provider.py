from __future__ import annotations

from decimal import Decimal

import pytest

from portfolio_tool.providers.yfinance_provider import YFinanceProvider


class _FakeIloc:
    def __init__(self, values: list[object]):
        self._values = values

    def __getitem__(self, index: int) -> object:
        return self._values[index]


class _FakeSeries:
    def __init__(self, values: list[object]):
        self._values = values

    @property
    def iloc(self) -> _FakeIloc:
        return _FakeIloc(self._values)


class _FakeCloseData:
    def __init__(self, data: dict[str, list[object]]):
        self._data = data
        self.columns = list(data.keys())
        self.empty = not data

    def __getitem__(self, key: str) -> _FakeSeries:
        return _FakeSeries(self._data[key])


class _FakeDownloadFrame:
    def __init__(self, close_data: dict[str, list[object]]):
        self._close_data = close_data
        self.empty = False
        self.columns = ["Close"]

    def __getitem__(self, key: str) -> _FakeCloseData:
        if key != "Close":  # pragma: no cover - defensive
            raise KeyError(key)
        return _FakeCloseData(self._close_data)


class _FakeHistory:
    def __init__(self, values: list[object]):
        self._series = _FakeSeries(values)
        self.empty = False

    def __getitem__(self, key: str) -> _FakeSeries:
        if key != "Close":  # pragma: no cover - defensive
            raise KeyError(key)
        return self._series


class _FakeTicker:
    def __init__(self, _symbol: str, history_values: list[object]):
        self._history = _FakeHistory(history_values)

    def history(self, period: str = "1d") -> _FakeHistory:  # noqa: ARG002
        return self._history


@pytest.mark.parametrize(
    "raw_price, expected",
    [("100.5", Decimal("100.5")), ("NaN", None), (None, None)],
)
def test_parse_price_handles_invalid_values(raw_price: object, expected: Decimal | None):
    provider = YFinanceProvider()
    assert provider._parse_price(raw_price) == expected


def test_yfinance_skips_nan_prices(monkeypatch):
    provider = YFinanceProvider()

    def fake_download(symbols, *_, **__):
        return _FakeDownloadFrame({symbol: [float("nan")] for symbol in symbols})

    def fake_ticker(symbol):
        return _FakeTicker(symbol, [float("nan")])

    monkeypatch.setattr(
        "portfolio_tool.providers.yfinance_provider.yf.download",
        fake_download,
    )
    monkeypatch.setattr(
        "portfolio_tool.providers.yfinance_provider.yf.Ticker",
        fake_ticker,
    )

    quotes = provider.get_last(["DRO"])

    assert quotes == {}
