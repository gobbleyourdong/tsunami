"""Tests for tool input validation ("""

import pytest
from tsunami.tools.base import BaseTool, ToolResult


class DummyTool(BaseTool):
    """Minimal tool for testing validation."""
    name = "test_tool"
    description = "A test tool"

    def __init__(self):
        # Skip parent __init__ (needs config) — we only test validate_input
        pass

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "A file path"},
                "count": {"type": "integer", "description": "A count"},
                "ratio": {"type": "number", "description": "A ratio"},
                "force": {"type": "boolean", "description": "Force mode"},
                "optional_note": {"type": "string", "description": "Optional note"},
            },
            "required": ["path", "count"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult("ok")


class TestValidateInput:
    """Verify validate_input catches bad args before execution."""

    def setup_method(self):
        self.tool = DummyTool()

    def test_valid_input_passes(self):
        """All required fields present with correct types — no error."""
        result = self.tool.validate_input(path="/tmp/test", count=5)
        assert result is None

    def test_missing_required_field(self):
        """Missing required field returns error message."""
        result = self.tool.validate_input(count=5)
        assert result is not None
        assert "path" in result

    def test_missing_second_required_field(self):
        """Missing the other required field."""
        result = self.tool.validate_input(path="/tmp/test")
        assert result is not None
        assert "count" in result

    def test_empty_string_required(self):
        """Empty string for required string field is an error."""
        result = self.tool.validate_input(path="", count=5)
        assert result is not None
        assert "empty" in result.lower()

    def test_whitespace_only_string(self):
        """Whitespace-only string for required field is an error."""
        result = self.tool.validate_input(path="   ", count=5)
        assert result is not None
        assert "empty" in result.lower()

    def test_none_required_field(self):
        """None for required field is an error."""
        result = self.tool.validate_input(path=None, count=5)
        assert result is not None
        assert "Missing" in result

    def test_wrong_type_string(self):
        """Integer where string expected."""
        result = self.tool.validate_input(path=123, count=5)
        assert result is not None
        assert "string" in result.lower()

    def test_wrong_type_integer(self):
        """String where integer expected."""
        result = self.tool.validate_input(path="/tmp/test", count="five")
        assert result is not None
        assert "integer" in result.lower()

    def test_wrong_type_boolean(self):
        """String where boolean expected."""
        result = self.tool.validate_input(path="/tmp/test", count=5, force="yes")
        assert result is not None
        assert "boolean" in result.lower()

    def test_number_accepts_int(self):
        """Integer is valid for number type."""
        result = self.tool.validate_input(path="/tmp/test", count=5, ratio=3)
        assert result is None

    def test_number_accepts_float(self):
        """Float is valid for number type."""
        result = self.tool.validate_input(path="/tmp/test", count=5, ratio=3.14)
        assert result is None

    def test_extra_kwargs_ignored(self):
        """Unknown kwargs don't cause validation error (for **kw absorption)."""
        result = self.tool.validate_input(path="/tmp/test", count=5, unknown_param="hi")
        assert result is None

    def test_optional_field_can_be_absent(self):
        """Optional fields don't need to be provided."""
        result = self.tool.validate_input(path="/tmp/test", count=5)
        assert result is None

    def test_all_fields_valid(self):
        """All fields provided with correct types."""
        result = self.tool.validate_input(
            path="/tmp/test", count=5, ratio=0.5, force=True, optional_note="hello"
        )
        assert result is None


class TestValidateInputEdgeCases:
    """Edge cases and regression tests."""

    def test_tool_with_no_required(self):
        """Tool with no required fields — empty call is valid."""
        class OptionalTool(BaseTool):
            name = "optional"
            description = "no required"
            def __init__(self): pass
            def parameters_schema(self):
                return {"type": "object", "properties": {"x": {"type": "string"}}}
            async def execute(self, **kw): return ToolResult("ok")

        tool = OptionalTool()
        assert tool.validate_input() is None

    def test_tool_with_empty_schema(self):
        """Tool with completely empty schema."""
        class EmptyTool(BaseTool):
            name = "empty"
            description = "empty"
            def __init__(self): pass
            def parameters_schema(self):
                return {"type": "object", "properties": {}}
            async def execute(self, **kw): return ToolResult("ok")

        tool = EmptyTool()
        assert tool.validate_input() is None
        assert tool.validate_input(random="stuff") is None
