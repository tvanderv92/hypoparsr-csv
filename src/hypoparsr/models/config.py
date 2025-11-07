"""Parser configuration model."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ParserConfig:
    """Configuration for the parsing process.

    Controls various aspects of the parsing pipeline including pruning,
    data cleaning, and type casting behavior.

    Attributes:
        traversal_order: Order to traverse hypothesis tree ("pre-order" or "post-order").
        pruning_level: Minimum confidence threshold for pruning (0.0 to 1.0).
        remove_aggregates: Whether to remove aggregate rows/columns.
        remove_named_empty_cols: Whether to remove named empty columns.
        interpolate_spanning_column_header_cells: Fill spanning header cells.
        interpolate_spanning_column_data_cells: Fill spanning data cells.
        conservative_type_casting: Preserve text on type cast failures.
        separate_multiple_units: Handle columns with multiple units separately.
        only_one_table: Assume only one table per file.
        max_file_size: Maximum file size in bytes (default 400KB).

    Example:
        >>> config = ParserConfig(
        ...     pruning_level=0.2,
        ...     conservative_type_casting=False,
        ... )
    """

    traversal_order: Literal["pre-order", "post-order"] = "pre-order"
    pruning_level: float = 0.1
    remove_aggregates: bool = False
    remove_named_empty_cols: bool = False
    interpolate_spanning_column_header_cells: bool = True
    interpolate_spanning_column_data_cells: bool = False
    conservative_type_casting: bool = True
    separate_multiple_units: bool = True
    only_one_table: bool = True
    max_file_size: int = 400_000  # 400KB

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not 0.0 <= self.pruning_level <= 1.0:
            raise ValueError(
                f"Pruning level must be between 0.0 and 1.0, got {self.pruning_level}"
            )
        if self.max_file_size <= 0:
            raise ValueError(f"Max file size must be positive, got {self.max_file_size}")


@dataclass
class QualityWeights:
    """Weights for quality scoring.

    Each attribute represents the weight for a specific quality metric.
    Positive weights favor higher values, negative weights penalize them.

    Attributes:
        warnings: Weight for number of warnings (typically negative).
        edits: Weight for number of edits (typically negative).
        moves: Weight for number of cell moves (typically negative).
        confidence: Weight for confidence score (typically positive).
        total_cells: Weight for total cells (typically positive).
        typed_cells: Weight for typed cells (typically positive).
        empty_header: Weight for empty headers (typically negative).
        empty_cells: Weight for empty cells (typically negative).
        non_latin_chars: Weight for non-Latin characters (typically negative).
        row_col_ratio: Weight for row-to-column ratio (typically positive).

    Example:
        >>> weights = QualityWeights(
        ...     warnings=-2.0,
        ...     typed_cells=2.0,
        ...     confidence=1.5,
        ... )
    """

    warnings: float = -1.0
    edits: float = -1.0
    moves: float = -1.0
    confidence: float = 1.0
    total_cells: float = 1.0
    typed_cells: float = 1.0
    empty_header: float = -1.0
    empty_cells: float = -1.0
    non_latin_chars: float = -1.0
    row_col_ratio: float = 1.0

    def to_dict(self) -> dict[str, float]:
        """Convert weights to dictionary."""
        return {
            "warnings": self.warnings,
            "edits": self.edits,
            "moves": self.moves,
            "confidence": self.confidence,
            "total_cells": self.total_cells,
            "typed_cells": self.typed_cells,
            "empty_header": self.empty_header,
            "empty_cells": self.empty_cells,
            "non_latin_chars": self.non_latin_chars,
            "row_col_ratio": self.row_col_ratio,
        }
