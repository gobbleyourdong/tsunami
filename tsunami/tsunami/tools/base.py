"""Base tool interface — every tool inherits from this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import TsunamiConfig


@dataclass
class ToolResult:
    content: str
    is_error: bool = False

    def __str__(self) -> str:
        return self.content


class BaseTool(ABC):
    """Abstract base for all Tsunami tools.

    Tools are limbs, not features. They are how the agent
    interacts with reality.
    """

    name: str = ""
    description: str = ""
    # Concurrency safety flag (.
    # True = safe to run in parallel with other concurrent-safe tools
    # False = must run exclusively (has side effects: writes, shell, etc.)
    concurrent_safe: bool = False

    def __init__(self, config: TsunamiConfig):
        self.config = config

    @abstractmethod
    def parameters_schema(self) -> dict:
        """Return JSON Schema for this tool's parameters."""
        ...

    def validate_input(self, **kwargs) -> str | None:
        """Validate input parameters before execution.

        Returns error message string if invalid, None if OK.
        
        Checks required fields and basic type constraints from schema.
        """
        schema = self.parameters_schema()
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required fields are present and non-empty
        for field in required:
            if field not in kwargs or kwargs[field] is None:
                return f"Missing required parameter: '{field}'"
            val = kwargs[field]
            prop = properties.get(field, {})
            expected_type = prop.get("type")
            # String fields must be non-empty
            if expected_type == "string" and isinstance(val, str) and not val.strip():
                return f"Parameter '{field}' cannot be empty"

        # Type checking for provided fields
        type_map = {"string": str, "integer": int, "number": (int, float), "boolean": bool}
        for field, val in kwargs.items():
            if field not in properties:
                continue  # allow extra kwargs (absorbed by **kw)
            prop = properties[field]
            expected_type = prop.get("type")
            if expected_type and expected_type in type_map:
                py_type = type_map[expected_type]
                if not isinstance(val, py_type):
                    # Allow int where number expected
                    if expected_type == "number" and isinstance(val, (int, float)):
                        continue
                    return f"Parameter '{field}' expected {expected_type}, got {type(val).__name__}"

        return None

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool and return a result."""
        ...
