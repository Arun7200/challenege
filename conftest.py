"""
Pytest configuration for NexusAI Intern Challenge
Enables async test support and common fixtures.
"""

import pytest
import asyncio
from typing import Generator


def pytest_configure(config):
    """Configure pytest plugins and markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (deselect with '-m \"not asyncio\"')"
    )


@pytest.fixture
def event_loop() -> Generator:
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Example async fixtures can be added here
@pytest.fixture
async def sample_customer_context():
    """Sample customer context for testing."""
    from task3.parallel_fetcher import CustomerContext
    
    return CustomerContext(
        crm_data={"customer_id": "TEST001", "customer_tier": "standard"},
        billing_data={"overdue_amount": 0, "payment_status": "current"},
        ticket_history=[],
        data_complete=True,
        fetch_time_ms=100.0,
    )
