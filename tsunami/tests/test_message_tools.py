"""Tests for message tools in non-interactive contexts."""

import asyncio

from tsunami.config import TsunamiConfig
from tsunami.tools.message import MessageAsk


def test_message_ask_does_not_crash_without_input_callback():
    tool = MessageAsk(TsunamiConfig())
    result = asyncio.run(tool.execute(text="Need clarification?"))

    assert not result.is_error
    assert "No interactive stdin" in result.content
