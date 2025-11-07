"""Table area detection plugin.

This plugin identifies dense data regions within a parsed DataFrame, handling
files that may contain multiple tables, metadata rows, or leading/trailing empty space.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from hypoparsr.core.consistency import _detect_cell_type
from hypoparsr.models import Hypothesis, ParseResult, ParserConfig
from hypoparsr.plugins.base import ParsingPlugin


@dataclass
class TableArea:
    """Represents a rectangular table area within a DataFrame.

    Attributes:
        row_start: Starting row index (inclusive).
        row_end: Ending row index (inclusive).
        col_start: Starting column index (inclusive).
        col_end: Ending column index (inclusive).
    """

    row_start: int
    row_end: int
    col_start: int
    col_end: int

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "row_start": self.row_start,
            "row_end": self.row_end,
            "col_start": self.col_start,
            "col_end": self.col_end,
        }


class TableAreaPlugin(ParsingPlugin):
    """Detects table areas within parsed CSV data.

    This is the third plugin in the pipeline (level 3). It takes a DataFrame
    from the dialect parser and identifies where actual data tables are located,
    handling:
    - Leading/trailing empty rows and columns
    - Metadata rows before/after tables
    - Multiple tables within a single file

    The algorithm calculates data density (non-empty neighbors) for each cell
    and identifies rectangular regions with high density.

    Example:
        >>> plugin = TableAreaPlugin()
        >>> hypotheses = plugin.detect(df, config)
        >>> hypotheses[0].parameters['table_areas']
        [TableArea(row_start=0, row_end=10, col_start=0, col_end=5)]
    """

    @property
    def level_name(self) -> str:
        """Level name for this plugin."""
        return "table_area"

    @property
    def level_order(self) -> int:
        """Pipeline order (3 = third)."""
        return 3

    def detect(self, input_data: pd.DataFrame, config: ParserConfig) -> list[Hypothesis]:
        """Detect table areas within DataFrame.

        Args:
            input_data: Parsed DataFrame (from dialect plugin).
            config: Parser configuration.

        Returns:
            List of table area hypotheses.

        Example:
            >>> hypotheses = plugin.detect(df, config)
            >>> len(hypotheses)
            2  # Default hypothesis + detected areas
        """
        if not isinstance(input_data, pd.DataFrame):
            raise ValueError(f"Expected DataFrame, got {type(input_data)}")

        if input_data.empty:
            # Return single hypothesis covering empty DataFrame
            return [
                Hypothesis(
                    level=self.level_name,
                    confidence=1.0,
                    parameters={"table_areas": []},
                )
            ]

        hypotheses = []

        # Create type matrix (for density calculation)
        type_matrix = self._create_type_matrix(input_data)

        # Default hypothesis: entire DataFrame is one table
        default_area = TableArea(
            row_start=0,
            row_end=len(input_data) - 1,
            col_start=0,
            col_end=len(input_data.columns) - 1,
        )
        default_area = self._remove_empty_frame(default_area, type_matrix)

        hypotheses.append(
            Hypothesis(
                level=self.level_name,
                confidence=0.6,  # Medium confidence for default
                parameters={"table_areas": [default_area]},
                metadata={"detection_method": "default"},
            )
        )

        # If only_one_table is True, skip multi-table detection
        if config.only_one_table:
            return hypotheses

        # Perform area detection for multiple tables
        density_matrix = self._calculate_density(type_matrix)
        dense_areas = self._find_dense_areas(type_matrix, density_matrix)

        if dense_areas:
            # Expand areas to include headers
            expanded_areas = self._expand_areas(dense_areas, type_matrix)

            # Remove empty frames
            clean_areas = [
                self._remove_empty_frame(area, type_matrix) for area in expanded_areas
            ]

            # Filter out invalid areas
            clean_areas = [
                area
                for area in clean_areas
                if area.row_start <= area.row_end and area.col_start <= area.col_end
            ]

            if clean_areas:
                hypotheses.append(
                    Hypothesis(
                        level=self.level_name,
                        confidence=0.8,  # Higher confidence for detected areas
                        parameters={"table_areas": clean_areas},
                        metadata={
                            "detection_method": "density",
                            "num_tables": len(clean_areas),
                        },
                    )
                )

        # Sort by confidence
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)

        return hypotheses

    def parse(
        self, input_data: pd.DataFrame, hypothesis: Hypothesis, config: ParserConfig
    ) -> ParseResult:
        """Extract table area(s) from DataFrame.

        Args:
            input_data: Parsed DataFrame.
            hypothesis: Table area hypothesis to apply.
            config: Parser configuration.

        Returns:
            Parse result with extracted table(s).

        Note:
            If multiple tables detected, returns the first one.
            Future enhancement: Support multiple table results.

        Example:
            >>> result = plugin.parse(df, hypothesis, config)
            >>> isinstance(result.intermediate, pd.DataFrame)
            True
        """
        if not self.validate_hypothesis(hypothesis):
            raise ValueError(
                f"Invalid hypothesis: expected level={self.level_name!r}, "
                f"got {hypothesis.level!r}"
            )

        table_areas: list[TableArea] = hypothesis.parameters.get("table_areas", [])

        if not table_areas:
            # No table areas, return empty DataFrame
            result = ParseResult(
                intermediate=pd.DataFrame(),
                hypothesis=hypothesis,
                warnings=["No table areas detected"],
            )
            return result

        # Extract first table area
        # TODO: Support multiple tables (requires returning list of results)
        area = table_areas[0]

        # Extract subset
        extracted = input_data.iloc[
            area.row_start : area.row_end + 1, area.col_start : area.col_end + 1
        ].copy()

        # Reset index
        extracted.reset_index(drop=True, inplace=True)

        warnings = []
        if len(table_areas) > 1:
            warnings.append(
                f"Multiple tables detected ({len(table_areas)}), "
                f"but only first table returned"
            )

        result = ParseResult(
            intermediate=extracted,
            hypothesis=hypothesis,
            warnings=warnings,
            cells=extracted.shape[0] * extracted.shape[1],
            metadata={
                "original_shape": input_data.shape,
                "extracted_shape": extracted.shape,
                "area": area.to_dict(),
                "num_tables": len(table_areas),
            },
        )

        return result

    def describe(self, hypothesis: Hypothesis) -> str:
        """Generate human-readable description.

        Args:
            hypothesis: Hypothesis to describe.

        Returns:
            Description string.

        Example:
            >>> plugin.describe(hypothesis)
            'tables=2, method=density'
        """
        table_areas = hypothesis.parameters.get("table_areas", [])
        method = hypothesis.metadata.get("detection_method", "unknown")
        return f"tables={len(table_areas)}, method={method}"

    def _create_type_matrix(self, df: pd.DataFrame) -> np.ndarray:
        """Create matrix of cell types for density calculation.

        Args:
            df: Input DataFrame.

        Returns:
            Matrix where True = non-empty, False = empty.
        """
        type_matrix = np.zeros(df.shape, dtype=bool)

        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                value = str(df.iloc[i, j])
                cell_type = _detect_cell_type(value)
                type_matrix[i, j] = cell_type != "empty"

        return type_matrix

    def _calculate_density(self, type_matrix: np.ndarray) -> np.ndarray:
        """Calculate data density for each cell.

        For each non-empty cell, counts non-empty neighbors in 3x3 window.

        Args:
            type_matrix: Boolean matrix (True = non-empty).

        Returns:
            Density matrix (0-9 for each cell).
        """
        rows, cols = type_matrix.shape
        density = np.zeros((rows, cols), dtype=int)

        for i in range(rows):
            for j in range(cols):
                if type_matrix[i, j]:  # Only for non-empty cells
                    # Count neighbors in 3x3 window
                    row_start = max(0, i - 1)
                    row_end = min(rows, i + 2)
                    col_start = max(0, j - 1)
                    col_end = min(cols, j + 2)

                    window = type_matrix[row_start:row_end, col_start:col_end]
                    density[i, j] = np.sum(window)

        return density

    def _find_dense_areas(
        self, type_matrix: np.ndarray, density_matrix: np.ndarray
    ) -> list[TableArea]:
        """Find dense rectangular areas in the data.

        Args:
            type_matrix: Boolean matrix of cell types.
            density_matrix: Density scores for each cell.

        Returns:
            List of detected table areas.
        """
        density = density_matrix.copy()
        areas = []

        while np.max(density) > 0:
            # Find cell with maximum density
            max_idx = np.unravel_index(np.argmax(density), density.shape)
            max_row, max_col = max_idx

            # Find empty row/column boundaries
            empty_rows = np.where(~type_matrix.any(axis=1))[0]
            empty_cols = np.where(~type_matrix.any(axis=0))[0]

            # Find boundaries
            row_start = (
                empty_rows[empty_rows < max_row].max() + 1
                if len(empty_rows[empty_rows < max_row]) > 0
                else 0
            )
            row_end = (
                empty_rows[empty_rows > max_row].min() - 1
                if len(empty_rows[empty_rows > max_row]) > 0
                else type_matrix.shape[0] - 1
            )
            col_start = (
                empty_cols[empty_cols < max_col].max() + 1
                if len(empty_cols[empty_cols < max_col]) > 0
                else 0
            )
            col_end = (
                empty_cols[empty_cols > max_col].min() - 1
                if len(empty_cols[empty_cols > max_col]) > 0
                else type_matrix.shape[1] - 1
            )

            # Check if valid area
            if row_start == row_end or col_start == col_end:
                break

            # Mark this area as processed
            density[row_start : row_end + 1, col_start : col_end + 1] = -1

            areas.append(
                TableArea(
                    row_start=row_start,
                    row_end=row_end,
                    col_start=col_start,
                    col_end=col_end,
                )
            )

            # Limit to 3 tables maximum
            if len(areas) >= 3:
                break

        return areas

    def _expand_areas(
        self, areas: list[TableArea], type_matrix: np.ndarray
    ) -> list[TableArea]:
        """Expand areas to include headers and surrounding data.

        Args:
            areas: Initial dense areas.
            type_matrix: Boolean matrix of cell types.

        Returns:
            Expanded table areas.
        """
        expanded = []

        for i, area in enumerate(areas):
            # For last area, extend to end of data
            if i == len(areas) - 1:
                area.row_end = type_matrix.shape[0] - 1
                area.col_end = type_matrix.shape[1] - 1

            expanded.append(area)

        return expanded

    def _remove_empty_frame(
        self, area: TableArea, type_matrix: np.ndarray
    ) -> TableArea:
        """Remove leading/trailing empty rows and columns from area.

        Args:
            area: Table area to trim.
            type_matrix: Boolean matrix of cell types.

        Returns:
            Trimmed table area.
        """
        # Extract subset
        subset = type_matrix[
            area.row_start : area.row_end + 1, area.col_start : area.col_end + 1
        ]

        if subset.size == 0:
            return area

        # Find first/last non-empty row
        row_has_data = subset.any(axis=1)
        if not row_has_data.any():
            # All rows empty
            return area

        first_row = np.argmax(row_has_data)
        last_row = len(row_has_data) - 1 - np.argmax(row_has_data[::-1])

        # Find first/last non-empty column
        col_has_data = subset.any(axis=0)
        if not col_has_data.any():
            # All columns empty
            return area

        first_col = np.argmax(col_has_data)
        last_col = len(col_has_data) - 1 - np.argmax(col_has_data[::-1])

        # Adjust area boundaries
        trimmed = TableArea(
            row_start=area.row_start + first_row,
            row_end=area.row_start + last_row,
            col_start=area.col_start + first_col,
            col_end=area.col_start + last_col,
        )

        return trimmed
