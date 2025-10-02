import pytest

from portfolio_tool.core.brokerage import BrokerageAllocationError, allocate_fees


def test_allocate_fees_buy_only():
    legs = [("buy1", 5000.0), ("sell1", -3000.0), ("buy2", 2500.0)]
    allocation = allocate_fees(30.0, "BUY", legs)
    assert allocation["buy1"] == pytest.approx(20.0)
    assert allocation["buy2"] == pytest.approx(10.0)
    assert allocation["sell1"] == 0.0


def test_allocate_fees_sell_only():
    legs = [("buy", 5000.0), ("sell", -2000.0)]
    allocation = allocate_fees(15.0, "SELL", legs)
    assert allocation["sell"] == pytest.approx(15.0)
    assert allocation["buy"] == 0.0


def test_allocate_split_across_all():
    legs = [("leg1", 2000.0), ("leg2", -1000.0), ("leg3", 1000.0)]
    allocation = allocate_fees(12.0, "SPLIT", legs)
    total = sum(allocation.values())
    assert total == pytest.approx(12.0)
    assert allocation["leg2"] == pytest.approx(3.0)


def test_allocate_raises_when_no_eligible_legs():
    legs = [("sell", -2000.0)]
    with pytest.raises(BrokerageAllocationError):
        allocate_fees(10.0, "BUY", legs)
