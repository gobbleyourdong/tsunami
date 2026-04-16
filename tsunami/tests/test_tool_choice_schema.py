"""Regression guard for the tool_choice payload schema on ChatRequest.

Context: commit 539504b widened `tool_choice: str` to `str | dict` as a
[race-mode] fix for Pydantic 422s when the #14 deliver-gate sent a dict
payload. That untyped widening lost the schema contract — a typo in
{"type": "func"} or a missing function.name would have passed through
as an opaque dict.

This test pins the refactored shape: the string form accepts only the
canonical sentinels, and the object form validates structurally.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tsunami.serve_transformers import ChatRequest, ForceToolChoice


def test_tool_choice_defaults_to_auto():
    req = ChatRequest(messages=[])
    assert req.tool_choice == "auto"


@pytest.mark.parametrize("sentinel", ["auto", "none", "required"])
def test_tool_choice_accepts_sentinels(sentinel):
    req = ChatRequest(messages=[], tool_choice=sentinel)
    assert req.tool_choice == sentinel


def test_tool_choice_rejects_unknown_sentinel():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[], tool_choice="forced")


def test_tool_choice_accepts_force_function():
    req = ChatRequest(
        messages=[],
        tool_choice={"type": "function", "function": {"name": "message_result"}},
    )
    assert isinstance(req.tool_choice, ForceToolChoice)
    assert req.tool_choice.function.name == "message_result"


def test_tool_choice_rejects_wrong_type_literal():
    # "func" is a typo; schema should reject it rather than silently pass through
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[],
            tool_choice={"type": "func", "function": {"name": "x"}},
        )


def test_tool_choice_rejects_missing_function_name():
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[],
            tool_choice={"type": "function", "function": {}},
        )


def test_tool_choice_roundtrips_through_model_dump():
    """_proxy_chat_completions forwards the body via model_dump; verify
    the serialized form is wire-compatible with OpenAI's chat-completions
    contract (what llama-server expects)."""
    req = ChatRequest(
        messages=[],
        tool_choice={"type": "function", "function": {"name": "message_result"}},
    )
    body = req.model_dump(exclude_none=True)
    assert body["tool_choice"] == {
        "type": "function",
        "function": {"name": "message_result"},
    }
