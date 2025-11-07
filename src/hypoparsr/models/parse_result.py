"""Parse result data model."""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from hypoparsr.models.hypothesis import Hypothesis


@dataclass
class ParseResult:
    """Result of applying a hypothesis to input data.

    Contains the intermediate parsed data, the hypothesis used, and
    metadata about the parsing process including warnings and edits.

    Attributes:
        intermediate: Parsed data (can be str, bytes, or DataFrame).
        hypothesis: The hypothesis that was applied.
        warnings: List of warning messages during parsing.
        edits: Number of edits made to the data.
        moves: Number of cell moves performed.
        cells: Total number of cells processed.
        metadata: Additional metadata about the parsing.

    Example:
        >>> result = ParseResult(
        ...     intermediate=pd.DataFrame({"a": [1, 2], "b": [3, 4]}),
        ...     hypothesis=hypothesis,
        ...     warnings=["Missing value in row 2"],
        ...     edits=1
        ... )
    """

    intermediate: pd.DataFrame | str | bytes
    hypothesis: Hypothesis
    warnings: list[str] = field(default_factory=list)
    edits: int = 0
    moves: int = 0
    cells: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate parse result after initialization."""
        if self.edits < 0:
            raise ValueError(f"Edits cannot be negative, got {self.edits}")
        if self.moves < 0:
            raise ValueError(f"Moves cannot be negative, got {self.moves}")
        if self.cells < 0:
            raise ValueError(f"Cells cannot be negative, got {self.cells}")

    def __repr__(self) -> str:
        """Return string representation of parse result."""
        data_type = type(self.intermediate).__name__
        warnings_str = f"{len(self.warnings)} warnings" if self.warnings else "no warnings"
        return (
            f"ParseResult(level={self.hypothesis.level!r}, "
            f"data_type={data_type}, "
            f"edits={self.edits}, "
            f"{warnings_str})"
        )
