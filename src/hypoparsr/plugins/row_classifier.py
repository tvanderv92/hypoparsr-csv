"""Row classification plugin.

This plugin classifies rows in a DataFrame by their function/role in the table
structure (header, data, metadata, aggregate, empty).
"""

from enum import Enum

import numpy as np
import pandas as pd

from hypoparsr.core.consistency import _detect_cell_type
from hypoparsr.models import Hypothesis, ParseResult, ParserConfig
from hypoparsr.plugins.base import ParsingPlugin


class RowType(Enum):
    """Row type classifications."""

    HEADER = "header"
    SPANNING_HEADER = "spanning_header"
    DATA = "data"
    AGGREGATE = "aggregate"
    METADATA = "metadata"
    EMPTY = "empty"


class RowClassifierPlugin(ParsingPlugin):
    """Classifies rows by their function in the table.

    This is the fourth plugin in the pipeline (level 4). It analyzes each row
    and classifies it as:
    - header: Column headers
    - spanning_header: Multi-level headers
    - data: Actual data rows
    - aggregate: Sum/total rows
    - metadata: Metadata about the table
    - empty: Empty rows

    Uses a voting-based approach where multiple heuristics vote on each row's type.

    Example:
        >>> plugin = RowClassifierPlugin()
        >>> hypotheses = plugin.detect(df, config)
        >>> hypotheses[0].parameters['row_functions']
        ['header', 'data', 'data', 'aggregate']
    """

    @property
    def level_name(self) -> str:
        """Level name for this plugin."""
        return "row_function"

    @property
    def level_order(self) -> int:
        """Pipeline order (4 = fourth)."""
        return 4

    def detect(self, input_data: pd.DataFrame, config: ParserConfig) -> list[Hypothesis]:
        """Detect row classifications.

        Args:
            input_data: DataFrame with table area extracted.
            config: Parser configuration.

        Returns:
            List of row classification hypotheses.

        Example:
            >>> hypotheses = plugin.detect(df, config)
            >>> hypotheses[0].parameters['row_functions']
            ['header', 'data', 'data', 'data']
        """
        if not isinstance(input_data, pd.DataFrame):
            raise ValueError(f"Expected DataFrame, got {type(input_data)}")

        if input_data.empty:
            return [
                Hypothesis(
                    level=self.level_name,
                    confidence=1.0,
                    parameters={"row_functions": []},
                )
            ]

        # Create type matrix
        type_matrix = self._create_type_matrix(input_data)

        # Count votes for each row
        function_votes = self._count_function_votes(type_matrix)

        # Normalize votes
        normalized_votes = self._normalize_function_votes(function_votes)

        # Generate hypotheses
        hypotheses = []

        # Hypothesis 1: Default (all data)
        default_functions = [RowType.DATA.value] * len(input_data)
        hypotheses.append(
            Hypothesis(
                level=self.level_name,
                confidence=0.5,
                parameters={"row_functions": default_functions},
                metadata={"method": "default"},
            )
        )

        # Hypothesis 2: Classified based on votes
        row_functions = self._classify_rows(normalized_votes, function_votes)

        # Find data boundaries
        data_indices = [
            i for i, rt in enumerate(row_functions) if rt == RowType.DATA.value
        ]
        data_start = data_indices[0] if data_indices else 0
        data_end = data_indices[-1] if data_indices else len(row_functions) - 1

        # Finalize classification
        row_functions = self._finalize_classification(
            row_functions, function_votes, data_start, data_end
        )

        hypotheses.append(
            Hypothesis(
                level=self.level_name,
                confidence=0.8,
                parameters={"row_functions": row_functions},
                metadata={
                    "method": "voting",
                    "data_start": data_start,
                    "data_end": data_end,
                },
            )
        )

        # Sort by confidence
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)

        return hypotheses

    def parse(
        self, input_data: pd.DataFrame, hypothesis: Hypothesis, config: ParserConfig
    ) -> ParseResult:
        """Apply row classification to DataFrame.

        Args:
            input_data: DataFrame to classify.
            hypothesis: Row classification hypothesis.
            config: Parser configuration.

        Returns:
            Parse result with row classifications as metadata.

        Example:
            >>> result = plugin.parse(df, hypothesis, config)
            >>> result.metadata['row_functions']
            ['header', 'data', 'data']
        """
        if not self.validate_hypothesis(hypothesis):
            raise ValueError(
                f"Invalid hypothesis: expected level={self.level_name!r}, "
                f"got {hypothesis.level!r}"
            )

        row_functions = hypothesis.parameters.get("row_functions", [])

        # For now, just pass through DataFrame with classifications as metadata
        # Future enhancement: Actually remove metadata/aggregate rows, set headers
        result = ParseResult(
            intermediate=input_data.copy(),
            hypothesis=hypothesis,
            cells=input_data.shape[0] * input_data.shape[1],
            metadata={
                "row_functions": row_functions,
                "row_counts": {
                    "header": row_functions.count(RowType.HEADER.value),
                    "data": row_functions.count(RowType.DATA.value),
                    "aggregate": row_functions.count(RowType.AGGREGATE.value),
                    "metadata": row_functions.count(RowType.METADATA.value),
                    "empty": row_functions.count(RowType.EMPTY.value),
                },
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
            'header=1, data=10, aggregate=1'
        """
        row_functions = hypothesis.parameters.get("row_functions", [])
        counts = {
            "header": row_functions.count(RowType.HEADER.value),
            "data": row_functions.count(RowType.DATA.value),
            "aggregate": row_functions.count(RowType.AGGREGATE.value),
        }
        return f"header={counts['header']}, data={counts['data']}, aggregate={counts['aggregate']}"

    def _create_type_matrix(self, df: pd.DataFrame) -> list[list[str]]:
        """Create matrix of cell types.

        Args:
            df: Input DataFrame.

        Returns:
            Matrix of cell type strings.
        """
        type_matrix = []
        for i in range(len(df)):
            row_types = []
            for j in range(len(df.columns)):
                value = str(df.iloc[i, j])
                cell_type = _detect_cell_type(value)
                row_types.append(cell_type)
            type_matrix.append(row_types)
        return type_matrix

    def _count_function_votes(self, type_matrix: list[list[str]]) -> pd.DataFrame:
        """Count votes for each row function.

        Args:
            type_matrix: Matrix of cell types.

        Returns:
            DataFrame with vote counts for each function.
        """
        n_rows = len(type_matrix)
        votes = pd.DataFrame(
            {
                "header": [0.0] * n_rows,
                "aggregate": [0.0] * n_rows,
                "metadata": [0.0] * n_rows,
                "data": [0.0] * n_rows,
                "empty": [0.0] * n_rows,
            }
        )

        for i in range(n_rows):
            # Empty vote
            empty_score = self._empty_vote(i, type_matrix)
            if empty_score > 0.5:
                votes.loc[i, "empty"] = 1.0
                continue

            # Other votes
            votes.loc[i, "header"] = self._header_vote(i, type_matrix)
            votes.loc[i, "aggregate"] = self._aggregate_vote(i, type_matrix)
            votes.loc[i, "metadata"] = self._metadata_vote(i, type_matrix)
            votes.loc[i, "data"] = self._data_vote(i, type_matrix)

        return votes

    def _empty_vote(self, i: int, type_matrix: list[list[str]]) -> float:
        """Vote for empty row.

        Args:
            i: Row index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        row = type_matrix[i]
        empty_count = sum(1 for t in row if t in ("empty", "text"))
        return empty_count / len(row) if row else 0.0

    def _aggregate_vote(self, i: int, type_matrix: list[list[str]]) -> float:
        """Vote for aggregate row (total, sum, etc.).

        Args:
            i: Row index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        row = type_matrix[i]

        votes = 0
        # Check for "total" keywords
        # (In full implementation, would check actual text content)

        # Check if mostly numeric
        numeric_count = sum(1 for t in row if t == "numeric")
        if numeric_count / len(row) > 0.7:
            votes += 1

        return votes / 3

    def _header_vote(self, i: int, type_matrix: list[list[str]]) -> float:
        """Vote for header row.

        Headers typically have different types from subsequent rows.

        Args:
            i: Row index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        if i >= len(type_matrix) - 1:
            return 0.0

        row = type_matrix[i]
        n_cols = len(row)

        # Compare with next 30 rows (or fewer)
        max_rows = min(30, len(type_matrix))
        if i + 1 >= max_rows:
            return 0.0

        diff_count = 0
        compared_rows = 0

        for j in range(i + 1, max_rows):
            next_row = type_matrix[j]
            if len(next_row) != n_cols:
                continue

            # Count type differences
            for col in range(n_cols):
                if (
                    row[col] != next_row[col]
                    and row[col] != "empty"
                    and next_row[col] != "empty"
                ):
                    diff_count += 1

            compared_rows += 1

        if compared_rows == 0:
            return 0.0

        return diff_count / (compared_rows * n_cols)

    def _metadata_vote(self, i: int, type_matrix: list[list[str]]) -> float:
        """Vote for metadata row.

        Metadata rows typically have many empty cells.

        Args:
            i: Row index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        row = type_matrix[i]
        has_content = any(t != "empty" for t in row)

        if not has_content:
            return 0.0

        empty_count = sum(1 for t in row if t == "empty")
        return empty_count / len(row)

    def _data_vote(self, i: int, type_matrix: list[list[str]]) -> float:
        """Vote for data row.

        Data rows contain typed data (numeric, date, etc.).

        Args:
            i: Row index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        row = type_matrix[i]
        data_types = {"numeric", "date", "time", "email", "url", "logical"}
        data_count = sum(1 for t in row if t in data_types)
        return data_count / len(row)

    def _normalize_function_votes(self, votes: pd.DataFrame) -> pd.DataFrame:
        """Normalize vote scores.

        Args:
            votes: Raw vote DataFrame.

        Returns:
            Normalized vote DataFrame.
        """
        normalized = votes.copy()

        for col in votes.columns:
            # Subtract max of other columns
            other_cols = [c for c in votes.columns if c != col]
            max_others = votes[other_cols].max(axis=1)
            normalized[col] = votes[col] - max_others

        return normalized

    def _classify_rows(
        self, normalized_votes: pd.DataFrame, raw_votes: pd.DataFrame
    ) -> list[str]:
        """Classify rows based on vote scores.

        Args:
            normalized_votes: Normalized vote DataFrame.
            raw_votes: Raw vote DataFrame.

        Returns:
            List of row type strings.
        """
        row_functions = []

        for i in range(len(normalized_votes)):
            # Get max vote
            max_col = normalized_votes.iloc[i].idxmax()

            # Map to RowType
            row_type_map = {
                "header": RowType.HEADER.value,
                "data": RowType.DATA.value,
                "aggregate": RowType.AGGREGATE.value,
                "metadata": RowType.METADATA.value,
                "empty": RowType.EMPTY.value,
            }

            row_functions.append(row_type_map.get(max_col, RowType.DATA.value))

        return row_functions

    def _finalize_classification(
        self,
        row_functions: list[str],
        raw_votes: pd.DataFrame,
        data_start: int,
        data_end: int,
    ) -> list[str]:
        """Finalize row classifications with post-processing rules.

        Args:
            row_functions: Initial classifications.
            raw_votes: Raw vote scores.
            data_start: Start index of data region.
            data_end: End index of data region.

        Returns:
            Finalized row classifications.
        """
        result = row_functions.copy()

        # Apply empty classifications (definite)
        for i in range(len(result)):
            if raw_votes.loc[i, "empty"] == 1.0:
                result[i] = RowType.EMPTY.value

        # Apply aggregate outside data region
        for i in range(len(result)):
            if (
                raw_votes.loc[i, "aggregate"] > 0
                and result[i]
                not in (RowType.HEADER.value, RowType.SPANNING_HEADER.value)
                and (i < data_start or i > data_end)
            ):
                result[i] = RowType.AGGREGATE.value

        return result
