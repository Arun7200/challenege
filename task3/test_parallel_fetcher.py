"""
Tests for Task 3: Parallel Data Fetcher
"""

import pytest
import asyncio
from task3.parallel_fetcher import (
    fetch_sequential,
    fetch_parallel,
    fetch_crm,
    fetch_billing,
    fetch_ticket_history,
    CustomerContext,
)


@pytest.mark.asyncio
async def test_fetch_crm_returns_dict():
    """Test that CRM fetch returns a dictionary with account info."""
    data = await fetch_crm("+1-555-0001")
    assert isinstance(data, dict)
    assert "customer_id" in data
    assert "account_status" in data
    assert "customer_tier" in data


@pytest.mark.asyncio
async def test_fetch_billing_returns_dict():
    """Test that billing fetch returns a dictionary."""
    data = await fetch_billing("+1-555-0002")
    assert isinstance(data, dict)
    assert "current_bill" in data
    assert "payment_status" in data


@pytest.mark.asyncio
async def test_fetch_ticket_history_returns_list():
    """Test that ticket history fetch returns a list."""
    data = await fetch_ticket_history("+1-555-0003")
    assert isinstance(data, list)
    if len(data) > 0:
        assert "ticket_id" in data[0]
        assert "intent" in data[0]


@pytest.mark.asyncio
async def test_fetch_sequential_returns_context():
    """Test that fetch_sequential returns a CustomerContext."""
    context = await fetch_sequential("+1-555-0004")
    assert isinstance(context, CustomerContext)
    assert hasattr(context, "fetch_time_ms")
    assert context.fetch_time_ms > 0


@pytest.mark.asyncio
async def test_fetch_parallel_returns_context():
    """Test that fetch_parallel returns a CustomerContext."""
    context = await fetch_parallel("+1-555-0005")
    assert isinstance(context, CustomerContext)
    assert hasattr(context, "fetch_time_ms")
    assert context.fetch_time_ms > 0


@pytest.mark.asyncio
async def test_parallel_faster_than_sequential():
    """Test that parallel is faster than sequential (2x speedup expected)."""
    phone = "+1-555-0006"
    
    seq_context = await fetch_sequential(phone)
    par_context = await fetch_parallel(phone)
    
    # Parallel should be significantly faster
    # (at least comparable, often 2x faster)
    speedup = seq_context.fetch_time_ms / par_context.fetch_time_ms
    assert speedup >= 1.0, f"Parallel should be faster, got speedup of {speedup}"


@pytest.mark.asyncio
async def test_parallel_handles_billing_timeout():
    """Test that parallel fetch handles billing timeout gracefully."""
    # Run multiple times since billing timeout is 10% random
    for _ in range(20):
        context = await fetch_parallel("+1-555-0007")
        # Should not crash even if billing fails
        assert isinstance(context, CustomerContext)
        # If billing failed, data_complete should be False
        if not context.billing_data:
            assert context.data_complete == False


@pytest.mark.asyncio
async def test_customer_context_dataclass():
    """Test CustomerContext dataclass structure."""
    context = CustomerContext(
        crm_data={"test": "data"},
        data_complete=True,
        fetch_time_ms=100.5,
    )
    assert context.crm_data == {"test": "data"}
    assert context.data_complete == True
    assert context.fetch_time_ms == 100.5
    assert isinstance(context.warnings, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
