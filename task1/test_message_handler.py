"""
Tests for Task 1: AI Message Handler
"""

import pytest
import asyncio
from task1.message_handler import handle_message, MessageResponse


@pytest.mark.asyncio
async def test_empty_message():
    """Test that empty messages return error without API call."""
    response = await handle_message("", "CUST001", "chat")
    assert response.error is not None
    assert response.confidence == 0.0
    assert "empty" in response.error.lower()


@pytest.mark.asyncio
async def test_whitespace_only_message():
    """Test that whitespace-only messages return error without API call."""
    response = await handle_message("   \n\t  ", "CUST001", "voice")
    assert response.error is not None
    assert response.confidence == 0.0


@pytest.mark.asyncio
async def test_invalid_channel():
    """Test invalid channel parameter."""
    response = await handle_message("Hello", "CUST001", "invalid_channel")
    assert response.error is not None
    assert "invalid channel" in response.error.lower()


@pytest.mark.asyncio
async def test_response_structure():
    """Test that response has all required fields."""
    response = await handle_message("Hello", "CUST001", "chat")
    assert isinstance(response, MessageResponse)
    assert hasattr(response, "response_text")
    assert hasattr(response, "confidence")
    assert hasattr(response, "suggested_action")
    assert hasattr(response, "channel_formatted_response")
    assert hasattr(response, "error")


def test_message_response_dataclass():
    """Test MessageResponse dataclass initialization."""
    response = MessageResponse(
        response_text="Hello",
        confidence=0.9,
        suggested_action="general_inquiry",
        channel_formatted_response="Hello",
        error=None,
    )
    assert response.response_text == "Hello"
    assert response.confidence == 0.9
    assert response.error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
