from portfolio_tool.config import Config
from ui.textual_app import PriceStatus
from ui.widgets.header import HeaderWidget


def render_text_for_reason(reason: str) -> str:
    widget = HeaderWidget(Config())
    widget.update_status(PriceStatus(asof=None, stale=reason != "ok", reason=reason))
    return widget.render().plain


def test_header_shows_offline_when_offline_mode() -> None:
    text = render_text_for_reason("offline_mode")
    assert "[O] Offline [offline_mode]" in text


def test_header_shows_prices_current_message_when_ok() -> None:
    text = render_text_for_reason("ok")
    assert "[P] Prices current" in text
    assert "[O] Offline" not in text


def test_header_shows_prices_stale_message() -> None:
    text = render_text_for_reason("stale")
    assert "[P] Prices stale" in text
    assert "[O] Offline" not in text


def test_header_shows_no_cached_prices_message() -> None:
    text = render_text_for_reason("no_prices")
    assert "[P] No cached prices" in text
    assert "[O] Offline" not in text
