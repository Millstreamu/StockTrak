"""Rules plugin registry."""
from __future__ import annotations

from importlib import import_module
from typing import Sequence

from ...core.rules import RuleCallable

_RULE_PACKS = {
    "starter_pack": "portfolio_tool.plugins.rules.starter_pack",
}


def get_rules(pack: str = "starter_pack") -> Sequence[RuleCallable]:
    module_path = _RULE_PACKS.get(pack)
    if module_path is None:
        raise ValueError(f"Unknown rule pack: {pack}")
    module = import_module(module_path)
    return module.get_rules()


__all__ = ["get_rules"]
