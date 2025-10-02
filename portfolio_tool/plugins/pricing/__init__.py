"""Pricing providers registry."""

from .manual_inline import ManualInlineProvider
from .online_default import OnlineDefaultProvider
from .provider_base import PriceProvider, ProviderPrice

_PROVIDERS = {
    ManualInlineProvider.name: ManualInlineProvider,
    OnlineDefaultProvider.name: OnlineDefaultProvider,
}


def get_provider(name: str, **kwargs) -> PriceProvider:
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown price provider: {name}")
    return cls(**kwargs)


__all__ = [
    "get_provider",
    "ManualInlineProvider",
    "OnlineDefaultProvider",
    "PriceProvider",
    "ProviderPrice",
]
