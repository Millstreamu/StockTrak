"""View exports for the Textual app."""
from .actionables import ActionablesView
from .cgt import CGTCalendarView
from .config import ConfigView
from .dashboard import DashboardView
from .lots import LotsView
from .positions import PositionsView
from .prices import PricesView
from .trades import TradesView

__all__ = [
    "DashboardView",
    "TradesView",
    "PositionsView",
    "LotsView",
    "CGTCalendarView",
    "ActionablesView",
    "PricesView",
    "ConfigView",
]
