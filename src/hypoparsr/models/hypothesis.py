"""Hypothesis data model."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hypothesis:
    """Represents a parsing hypothesis at a specific level.

    A hypothesis contains a set of parameters that define how to parse
    data at a particular stage in the parsing pipeline (e.g., encoding,
    delimiter, data types).

    Attributes:
        level: Name of the parsing level (e.g., "encoding", "dialect").
        confidence: Confidence score for this hypothesis (0.0 to 1.0).
        parameters: Dictionary of parsing parameters specific to this level.
        metadata: Optional metadata about this hypothesis.

    Example:
        >>> hypothesis = Hypothesis(
        ...     level="dialect",
        ...     confidence=0.95,
        ...     parameters={"delimiter": ",", "quotechar": '"'}
        ... )
    """

    level: str
    confidence: float
    parameters: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate hypothesis after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        if not self.level:
            raise ValueError("Level cannot be empty")

    def __repr__(self) -> str:
        """Return string representation of hypothesis."""
        params_str = ", ".join(f"{k}={v}" for k, v in list(self.parameters.items())[:3])
        if len(self.parameters) > 3:
            params_str += ", ..."
        return (
            f"Hypothesis(level={self.level!r}, "
            f"confidence={self.confidence:.2f}, "
            f"parameters={{{params_str}}})"
        )
