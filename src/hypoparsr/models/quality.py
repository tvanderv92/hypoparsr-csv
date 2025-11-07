"""Quality metrics data model."""

from dataclasses import dataclass


@dataclass
class QualityMetrics:
    """Metrics for evaluating parsing quality.

    These metrics are used to rank different parsing hypotheses and
    select the best result.

    Attributes:
        warnings: Number of warnings generated during parsing.
        edits: Number of edits made to the data.
        moves: Number of cell moves performed.
        confidence: Overall confidence score (product of all level confidences).
        total_cells: Total number of cells in the result.
        typed_cells: Number of cells with detected types (non-text).
        empty_headers: Number of empty header cells.
        empty_cells: Number of empty data cells.
        non_latin_chars: Count of non-Latin characters.
        row_col_ratio: Ratio of rows to columns.

    Example:
        >>> metrics = QualityMetrics(
        ...     warnings=0,
        ...     edits=2,
        ...     confidence=0.95,
        ...     typed_cells=100,
        ...     total_cells=120,
        ... )
    """

    warnings: int = 0
    edits: int = 0
    moves: int = 0
    confidence: float = 1.0
    total_cells: int = 0
    typed_cells: int = 0
    empty_headers: int = 0
    empty_cells: int = 0
    non_latin_chars: int = 0
    row_col_ratio: float = 0.0

    def __post_init__(self) -> None:
        """Validate metrics after initialization."""
        if self.warnings < 0:
            raise ValueError(f"Warnings cannot be negative, got {self.warnings}")
        if self.edits < 0:
            raise ValueError(f"Edits cannot be negative, got {self.edits}")
        if self.moves < 0:
            raise ValueError(f"Moves cannot be negative, got {self.moves}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        if self.total_cells < 0:
            raise ValueError(f"Total cells cannot be negative, got {self.total_cells}")
        if self.typed_cells < 0:
            raise ValueError(f"Typed cells cannot be negative, got {self.typed_cells}")

    def score(self, weights: dict[str, float]) -> float:
        """Calculate weighted quality score.

        Args:
            weights: Dictionary of weights for each metric.

        Returns:
            Weighted quality score.

        Example:
            >>> metrics = QualityMetrics(confidence=0.9, typed_cells=100, warnings=2)
            >>> score = metrics.score({"confidence": 1.0, "typed_cells": 1.0, "warnings": -1.0})
            >>> score
            98.9
        """
        return (
            self.warnings * weights.get("warnings", 0.0)
            + self.edits * weights.get("edits", 0.0)
            + self.moves * weights.get("moves", 0.0)
            + self.confidence * weights.get("confidence", 0.0)
            + self.total_cells * weights.get("total_cells", 0.0)
            + self.typed_cells * weights.get("typed_cells", 0.0)
            + self.empty_headers * weights.get("empty_header", 0.0)
            + self.empty_cells * weights.get("empty_cells", 0.0)
            + self.non_latin_chars * weights.get("non_latin_chars", 0.0)
            + self.row_col_ratio * weights.get("row_col_ratio", 0.0)
        )

    def __repr__(self) -> str:
        """Return string representation of quality metrics."""
        return (
            f"QualityMetrics(confidence={self.confidence:.2f}, "
            f"typed={self.typed_cells}/{self.total_cells}, "
            f"warnings={self.warnings}, edits={self.edits})"
        )
