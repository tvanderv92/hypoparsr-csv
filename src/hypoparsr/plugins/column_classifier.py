"""Column classification plugin.

This plugin classifies columns in a DataFrame by their function/role in the table
structure (data, spanning, aggregate, metadata, empty).
"""

from enum import Enum

import pandas as pd

from hypoparsr.core.consistency import _detect_cell_type
from hypoparsr.models import Hypothesis, ParseResult, ParserConfig
from hypoparsr.plugins.base import ParsingPlugin


class ColumnType(Enum):
    """Column type classifications."""

    DATA = "data"
    SPANNING_HEADER = "spanning_header"
    SPANNING_DATA = "spanning_data"
    AGGREGATE = "aggregate"
    METADATA = "metadata"
    EMPTY = "empty"


class ColumnClassifierPlugin(ParsingPlugin):
    """Classifies columns by their function in the table.

    This is the fifth plugin in the pipeline (level 5). It analyzes each column
    and classifies it as:
    - data: Regular data columns
    - spanning_header: Columns that span multiple columns in header
    - spanning_data: Columns that contain spanning data cells
    - aggregate: Sum/total columns
    - metadata: Metadata about rows
    - empty: Empty columns

    Example:
        >>> plugin = ColumnClassifierPlugin()
        >>> hypotheses = plugin.detect(df, config)
        >>> hypotheses[0].parameters['column_functions']
        ['data', 'data', 'data', 'aggregate']
    """

    @property
    def level_name(self) -> str:
        """Level name for this plugin."""
        return "column_function"

    @property
    def level_order(self) -> int:
        """Pipeline order (5 = fifth)."""
        return 5

    def detect(
        self, input_data: pd.DataFrame, config: ParserConfig
    ) -> list[Hypothesis]:
        """Detect column classifications.

        Args:
            input_data: DataFrame with rows classified.
            config: Parser configuration.

        Returns:
            List of column classification hypotheses.

        Example:
            >>> hypotheses = plugin.detect(df, config)
            >>> hypotheses[0].parameters['column_functions']
            ['data', 'data', 'data']
        """
        if not isinstance(input_data, pd.DataFrame):
            raise ValueError(f"Expected DataFrame, got {type(input_data)}")

        if input_data.empty:
            return [
                Hypothesis(
                    level=self.level_name,
                    confidence=1.0,
                    parameters={"column_functions": []},
                )
            ]

        # Create type matrix
        type_matrix = self._create_type_matrix(input_data)

        # Count votes for each column
        function_votes = self._count_function_votes(type_matrix)

        # Generate hypotheses
        hypotheses = []

        # Hypothesis 1: Default (all data)
        default_functions = [ColumnType.DATA.value] * len(input_data.columns)
        hypotheses.append(
            Hypothesis(
                level=self.level_name,
                confidence=0.5,
                parameters={"column_functions": default_functions},
                metadata={"method": "default"},
            )
        )

        # Hypothesis 2: Classified based on votes
        column_functions = self._classify_columns(function_votes)

        hypotheses.append(
            Hypothesis(
                level=self.level_name,
                confidence=0.8,
                parameters={"column_functions": column_functions},
                metadata={"method": "voting"},
            )
        )

        # Sort by confidence
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)

        return hypotheses

    def parse(
        self, input_data: pd.DataFrame, hypothesis: Hypothesis, config: ParserConfig
    ) -> ParseResult:
        """Apply column classification to DataFrame.

        Args:
            input_data: DataFrame to classify.
            hypothesis: Column classification hypothesis.
            config: Parser configuration.

        Returns:
            Parse result with column classifications as metadata.

        Example:
            >>> result = plugin.parse(df, hypothesis, config)
            >>> result.metadata['column_functions']
            ['data', 'data', 'aggregate']
        """
        if not self.validate_hypothesis(hypothesis):
            raise ValueError(
                f"Invalid hypothesis: expected level={self.level_name!r}, "
                f"got {hypothesis.level!r}"
            )

        column_functions = hypothesis.parameters.get("column_functions", [])

        # Pass through DataFrame with classifications as metadata
        result = ParseResult(
            intermediate=input_data.copy(),
            hypothesis=hypothesis,
            cells=input_data.shape[0] * input_data.shape[1],
            metadata={
                "column_functions": column_functions,
                "column_counts": {
                    "data": column_functions.count(ColumnType.DATA.value),
                    "aggregate": column_functions.count(ColumnType.AGGREGATE.value),
                    "metadata": column_functions.count(ColumnType.METADATA.value),
                    "empty": column_functions.count(ColumnType.EMPTY.value),
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
            'data=10, aggregate=1, empty=0'
        """
        column_functions = hypothesis.parameters.get("column_functions", [])
        counts = {
            "data": column_functions.count(ColumnType.DATA.value),
            "aggregate": column_functions.count(ColumnType.AGGREGATE.value),
            "empty": column_functions.count(ColumnType.EMPTY.value),
        }
        return (
            f"data={counts['data']}, "
            f"aggregate={counts['aggregate']}, "
            f"empty={counts['empty']}"
        )

    def _create_type_matrix(self, df: pd.DataFrame) -> list[list[str]]:
        """Create matrix of cell types.

        Args:
            df: Input DataFrame.

        Returns:
            Matrix of cell type strings (transposed for column analysis).
        """
        type_matrix = []
        for j in range(len(df.columns)):
            col_types = []
            for i in range(len(df)):
                value = str(df.iloc[i, j])
                cell_type = _detect_cell_type(value)
                col_types.append(cell_type)
            type_matrix.append(col_types)
        return type_matrix

    def _count_function_votes(self, type_matrix: list[list[str]]) -> pd.DataFrame:
        """Count votes for each column function.

        Args:
            type_matrix: Matrix of cell types (columns as rows).

        Returns:
            DataFrame with vote counts for each function.
        """
        n_cols = len(type_matrix)
        votes = pd.DataFrame(
            {
                "data": [0.0] * n_cols,
                "aggregate": [0.0] * n_cols,
                "metadata": [0.0] * n_cols,
                "empty": [0.0] * n_cols,
            }
        )

        for j in range(n_cols):
            # Empty vote
            empty_score = self._empty_vote(j, type_matrix)
            if empty_score > 0.9:
                votes.loc[j, "empty"] = 1.0
                continue

            # Other votes
            votes.loc[j, "data"] = self._data_vote(j, type_matrix)
            votes.loc[j, "aggregate"] = self._aggregate_vote(j, type_matrix)
            votes.loc[j, "metadata"] = self._metadata_vote(j, type_matrix)

        return votes

    def _empty_vote(self, j: int, type_matrix: list[list[str]]) -> float:
        """Vote for empty column.

        Args:
            j: Column index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        col = type_matrix[j]
        empty_count = sum(1 for t in col if t == "empty")
        return empty_count / len(col) if col else 0.0

    def _aggregate_vote(self, j: int, type_matrix: list[list[str]]) -> float:
        """Vote for aggregate column (total, sum, etc.).

        Args:
            j: Column index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        col = type_matrix[j]

        # Check if mostly numeric (aggregates are typically numeric)
        numeric_count = sum(1 for t in col if t == "numeric")
        if numeric_count / len(col) > 0.8:
            # Check if it's the last column (common position for totals)
            if j == len(type_matrix) - 1:
                return 0.5
            return 0.3

        return 0.0

    def _metadata_vote(self, j: int, type_matrix: list[list[str]]) -> float:
        """Vote for metadata column.

        Metadata columns typically have many empty cells and are often
        at the beginning or end.

        Args:
            j: Column index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        col = type_matrix[j]
        has_content = any(t != "empty" for t in col)

        if not has_content:
            return 0.0

        empty_count = sum(1 for t in col if t == "empty")
        empty_ratio = empty_count / len(col)

        # Higher score if at edges
        if j == 0 or j == len(type_matrix) - 1:
            return empty_ratio * 1.5

        return empty_ratio

    def _data_vote(self, j: int, type_matrix: list[list[str]]) -> float:
        """Vote for data column.

        Data columns contain typed data (numeric, date, etc.).

        Args:
            j: Column index.
            type_matrix: Matrix of cell types.

        Returns:
            Vote score (0.0-1.0).
        """
        col = type_matrix[j]
        data_types = {"numeric", "date", "time", "email", "url", "logical", "text"}
        data_count = sum(1 for t in col if t in data_types)
        return data_count / len(col)

    def _classify_columns(self, votes: pd.DataFrame) -> list[str]:
        """Classify columns based on vote scores.

        Args:
            votes: Vote DataFrame.

        Returns:
            List of column type strings.
        """
        column_functions = []

        for j in range(len(votes)):
            # Get max vote
            max_col = votes.iloc[j].idxmax()

            # Map to ColumnType
            type_map = {
                "data": ColumnType.DATA.value,
                "aggregate": ColumnType.AGGREGATE.value,
                "metadata": ColumnType.METADATA.value,
                "empty": ColumnType.EMPTY.value,
            }

            column_functions.append(type_map.get(max_col, ColumnType.DATA.value))

        return column_functions
