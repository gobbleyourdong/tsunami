"""Tests for file-type-aware token estimation."""

import json
import os
import tempfile
import pytest

from tsunami.token_estimation import (
    bytes_per_token_for_ext,
    estimate_tokens_for_text,
    estimate_tokens_for_file,
    estimate_tokens_for_message,
    estimate_tokens_for_conversation,
    BYTES_PER_TOKEN,
    IMAGE_TOKEN_ESTIMATE,
)


class TestBytesPerToken:
    """File-type-specific token density ratios."""

    def test_json_denser(self):
        """JSON is 2x denser than default (2 vs 4 bytes/token)."""
        assert bytes_per_token_for_ext(".json") == 2
        assert bytes_per_token_for_ext(".jsonl") == 2

    def test_default_ratio(self):
        assert bytes_per_token_for_ext(".py") == 4
        assert bytes_per_token_for_ext(".ts") == 4
        assert bytes_per_token_for_ext(".md") == 4

    def test_xml_html(self):
        assert bytes_per_token_for_ext(".xml") == 2.5
        assert bytes_per_token_for_ext(".html") == 2.5

    def test_case_insensitive(self):
        assert bytes_per_token_for_ext(".JSON") == 2
        assert bytes_per_token_for_ext(".Html") == 2.5

    def test_unknown_uses_default(self):
        assert bytes_per_token_for_ext(".xyz") == 4

    def test_with_or_without_dot(self):
        assert bytes_per_token_for_ext("json") == 2
        assert bytes_per_token_for_ext(".json") == 2


class TestEstimateTokensForText:
    """Text content estimation with file type awareness."""

    def test_plain_text(self):
        text = "Hello world, this is a test."
        tokens = estimate_tokens_for_text(text)
        # ~27 bytes / 4 = ~6 tokens
        assert 5 <= tokens <= 10

    def test_json_text_denser(self):
        """Same text counted as JSON should give more tokens."""
        text = '{"key": "value", "number": 42}'
        plain_tokens = estimate_tokens_for_text(text, ext=".py")
        json_tokens = estimate_tokens_for_text(text, ext=".json")
        assert json_tokens > plain_tokens

    def test_empty_text(self):
        assert estimate_tokens_for_text("") >= 1  # minimum 1

    def test_unicode_text(self):
        """Unicode characters take more bytes."""
        text = "Hello 世界"
        tokens = estimate_tokens_for_text(text)
        assert tokens > 0


class TestEstimateTokensForFile:
    """File-based estimation using file size and extension."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_python_file(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("x" * 400)
        tokens = estimate_tokens_for_file(path)
        assert tokens == 100  # 400 bytes / 4

    def test_json_file_denser(self):
        path = os.path.join(self.tmpdir, "data.json")
        with open(path, "w") as f:
            f.write("x" * 400)
        tokens = estimate_tokens_for_file(path)
        assert tokens == 200  # 400 bytes / 2

    def test_nonexistent_file(self):
        assert estimate_tokens_for_file("/nonexistent") == 0

    def test_empty_file(self):
        path = os.path.join(self.tmpdir, "empty.py")
        with open(path, "w") as f:
            pass
        tokens = estimate_tokens_for_file(path)
        assert tokens >= 0


class TestEstimateTokensForMessage:
    """Per-message estimation including tool call overhead."""

    def test_simple_text(self):
        tokens = estimate_tokens_for_message("user", "Hello world")
        assert tokens > 0

    def test_tool_call_adds_overhead(self):
        """Messages with tool calls should estimate higher."""
        text_only = estimate_tokens_for_message("assistant", "thinking...")
        with_tool = estimate_tokens_for_message(
            "assistant", "thinking...",
            tool_call={"function": {"name": "file_read", "arguments": {"path": "/tmp/test.py"}}},
        )
        assert with_tool > text_only

    def test_tool_args_json_ratio(self):
        """Tool arguments use JSON ratio (2 bytes/token, not 4)."""
        large_args = {"path": "/tmp/test.py", "content": "x" * 1000}
        tokens = estimate_tokens_for_message(
            "assistant", "",
            tool_call={"function": {"name": "file_write", "arguments": large_args}},
        )
        # 1000 chars of args at JSON ratio (2) = 500 tokens + overhead
        assert tokens > 400

    def test_role_overhead(self):
        """Each message has ~4 tokens of role overhead."""
        tokens = estimate_tokens_for_message("user", "")
        assert tokens >= 4


class TestEstimateTokensForConversation:
    """Full conversation estimation."""

    def test_basic_conversation(self):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        tokens = estimate_tokens_for_conversation(messages)
        assert tokens > 10

    def test_empty_conversation(self):
        assert estimate_tokens_for_conversation([]) == 0

    def test_with_tool_calls(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "read test.py"},
            {"role": "assistant", "content": "", "tool_call": {
                "function": {"name": "file_read", "arguments": {"path": "test.py"}},
            }},
            {"role": "user", "content": "[file_read] contents of test.py..."},
        ]
        tokens = estimate_tokens_for_conversation(messages)
        assert tokens > 20

    def test_more_messages_more_tokens(self):
        small = [{"role": "user", "content": "hi"}]
        large = [{"role": "user", "content": "hi"}] * 10
        assert estimate_tokens_for_conversation(large) > estimate_tokens_for_conversation(small)
