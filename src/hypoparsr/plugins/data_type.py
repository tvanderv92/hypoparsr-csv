"""Data type detection and casting plugin.

This plugin detects data types for each column and casts them appropriately,
handling multiple numeric formats, date formats, and NA value representations.
"""

import re
from datetime import datetime
from typing import Any

import pandas as pd

from hypoparsr.core.consistency import get_dominant_type
from hypoparsr.models import Hypothesis, ParseResult, ParserConfig
from hypoparsr.plugins.base import ParsingPlugin

# NA value representations
NA_VALUES = [
    "NULL",
    "null",
    "Null",
    "NA",
    "na",
    "N/A",
    "n/a",
    "NaN",
    "nan",
    "#NA",
    "-",
    "",
]

# Numeric format configurations
NUMERIC_FORMATS = [
    {"decimal": ".", "thousand": ""},
    {"decimal": ".", "thousand": ","},
    {"decimal": ".", "thousand": " "},
    {"decimal": ",", "thousand": ""},
    {"decimal": ",", "thousand": "."},
    {"decimal": ",", "thousand": " "},
]

# Date format patterns
DATE_FORMATS = [
    "%Y-%m-%d",  # 2023-01-15
    "%d-%m-%Y",  # 15-01-2023
    "%m-%d-%Y",  # 01-15-2023
    "%Y/%m/%d",  # 2023/01/15
    "%d/%m/%Y",  # 15/01/2023
    "%m/%d/%Y",  # 01/15/2023
    "%d.%m.%Y",  # 15.01.2023
    "%Y%m%d",  # 20230115
]

# Logical value mappings
LOGICAL_VALUES = {
    "TRUE": True,
    "True": True,
    "true": True,
    "T": True,
    "FALSE": False,
    "False": False,
    "false": False,
    "F": False,
    "YES": True,
    "Yes": True,
    "yes": True,
    "Y": True,
    "NO": False,
    "No": False,
    "no": False,
    "N": False,
}


class DataTypePlugin(ParsingPlugin):
    """Detects and casts data types for each column.

    This is the sixth and final plugin in the pipeline (level 6). It analyzes
    each column to determine the best data type and casts the data accordingly.

    Supported types:
    - numeric (int, float) with various formats
    - date (multiple formats)
    - time
    - logical (boolean)
    - text (default)

    Example:
        >>> plugin = DataTypePlugin()
        >>> hypotheses = plugin.detect(df, config)
        >>> hypotheses[0].parameters['data_types']
        [{'type': 'numeric'}, {'type': 'text'}, {'type': 'date'}]
    """

    @property
    def level_name(self) -> str:
        """Level name for this plugin."""
        return "data_type"

    @property
    def level_order(self) -> int:
        """Pipeline order (6 = sixth/last)."""
        return 6

    def detect(self, input_data: pd.DataFrame, config: ParserConfig) -> list[Hypothesis]:
        """Detect data types for each column.

        Args:
            input_data: DataFrame with columns classified.
            config: Parser configuration.

        Returns:
            List of data type hypotheses.

        Example:
            >>> hypotheses = plugin.detect(df, config)
            >>> hypotheses[0].parameters['data_types']
            [{'type': 'numeric', 'format': {'decimal': '.'}}, ...]
        """
        if not isinstance(input_data, pd.DataFrame):
            raise ValueError(f"Expected DataFrame, got {type(input_data)}")

        if input_data.empty:
            return [
                Hypothesis(
                    level=self.level_name,
                    confidence=1.0,
                    parameters={"data_types": []},
                )
            ]

        # Detect data types for each column
        data_types = []
        for col in input_data.columns:
            col_type = self._detect_column_type(input_data[col])
            data_types.append(col_type)

        # Create single hypothesis with detected types
        hypothesis = Hypothesis(
            level=self.level_name,
            confidence=0.9,
            parameters={"data_types": data_types, "na_values": NA_VALUES},
            metadata={"method": "detection"},
        )

        return [hypothesis]

    def parse(
        self, input_data: pd.DataFrame, hypothesis: Hypothesis, config: ParserConfig
    ) -> ParseResult:
        """Cast columns to detected data types.

        Args:
            input_data: DataFrame to cast.
            hypothesis: Data type hypothesis to apply.
            config: Parser configuration.

        Returns:
            Parse result with typed DataFrame.

        Example:
            >>> result = plugin.parse(df, hypothesis, config)
            >>> result.intermediate.dtypes
            dtype: object
            age       int64
            name     object
            date     datetime64[ns]
        """
        if not self.validate_hypothesis(hypothesis):
            raise ValueError(
                f"Invalid hypothesis: expected level={self.level_name!r}, "
                f"got {hypothesis.level!r}"
            )

        data_types = hypothesis.parameters.get("data_types", [])
        na_values = hypothesis.parameters.get("na_values", NA_VALUES)

        if len(data_types) != len(input_data.columns):
            raise ValueError(
                f"Number of data types ({len(data_types)}) does not match "
                f"number of columns ({len(input_data.columns)})"
            )

        # Cast each column
        df_typed = input_data.copy()
        warnings = []
        edits = 0
        typed_cells = 0

        for i, col in enumerate(df_typed.columns):
            col_type = data_types[i]
            try:
                df_typed[col], cast_warnings, cast_edits, cast_typed = self._cast_column(
                    df_typed[col],
                    col_type,
                    na_values,
                    config.conservative_type_casting,
                )
                warnings.extend(cast_warnings)
                edits += cast_edits
                typed_cells += cast_typed
            except Exception as e:
                warnings.append(f"Error casting column {col}: {e}")

        result = ParseResult(
            intermediate=df_typed,
            hypothesis=hypothesis,
            warnings=warnings,
            edits=edits,
            cells=df_typed.shape[0] * df_typed.shape[1],
            metadata={
                "typed_cells": typed_cells,
                "total_cells": df_typed.shape[0] * df_typed.shape[1],
                "type_distribution": {
                    dt["type"]: sum(1 for d in data_types if d["type"] == dt["type"])
                    for dt in data_types
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
            'numeric=5, text=3, date=1'
        """
        data_types = hypothesis.parameters.get("data_types", [])
        type_counts = {}
        for dt in data_types:
            t = dt.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        return ", ".join(f"{k}={v}" for k, v in sorted(type_counts.items()))

    def _detect_column_type(self, series: pd.Series) -> dict[str, Any]:
        """Detect the best data type for a column.

        Args:
            series: Column to analyze.

        Returns:
            Dictionary with type and format information.
        """
        # Get dominant type from consistency module
        df_temp = pd.DataFrame({0: series})
        dominant = get_dominant_type(df_temp, 0)

        result = {"type": dominant}

        # Detect format for specific types
        if dominant == "numeric":
            result["format"] = self._detect_numeric_format(series)
        elif dominant == "date":
            result["format"] = self._detect_date_format(series)

        return result

    def _detect_numeric_format(self, series: pd.Series) -> dict[str, str]:
        """Detect numeric format (decimal/thousand separators).

        Args:
            series: Column to analyze.

        Returns:
            Format dictionary.
        """
        non_empty = series[series.notna() & (series != "")]

        for fmt in NUMERIC_FORMATS:
            # Build pattern for this format
            decimal = re.escape(fmt["decimal"])
            thousand = re.escape(fmt["thousand"]) if fmt["thousand"] else ""

            if thousand:
                pattern = rf"^-?\d{{1,3}}({thousand}\d{{3}})*({decimal}\d+)?$"
            else:
                pattern = rf"^-?\d+({decimal}\d+)?$"

            matches = non_empty.astype(str).str.match(pattern).sum()

            if matches / len(non_empty) > 0.8 if len(non_empty) > 0 else False:
                return fmt

        return {"decimal": ".", "thousand": ""}

    def _detect_date_format(self, series: pd.Series) -> str:
        """Detect date format.

        Args:
            series: Column to analyze.

        Returns:
            Date format string.
        """
        non_empty = series[series.notna() & (series != "")]

        for fmt in DATE_FORMATS:
            matches = 0
            for value in non_empty.head(10):  # Check first 10
                try:
                    datetime.strptime(str(value), fmt)
                    matches += 1
                except (ValueError, TypeError):
                    pass

            if matches / min(len(non_empty), 10) > 0.8:
                return fmt

        return "%Y-%m-%d"  # Default

    def _cast_column(
        self,
        series: pd.Series,
        col_type: dict[str, Any],
        na_values: list[str],
        conservative: bool,
    ) -> tuple[pd.Series, list[str], int, int]:
        """Cast column to specified type.

        Args:
            series: Column to cast.
            col_type: Type specification.
            na_values: List of NA value representations.
            conservative: If True, keep as text on casting errors.

        Returns:
            Tuple of (casted_series, warnings, edits, typed_cells).
        """
        warnings = []
        edits = 0
        typed_cells = 0

        # Replace NA values with None
        series = series.copy()
        for na_val in na_values:
            series = series.replace(na_val, None)

        dtype = col_type.get("type", "text")

        if dtype == "numeric":
            series, w, e, t = self._cast_numeric(series, col_type, conservative)
            warnings.extend(w)
            edits += e
            typed_cells += t

        elif dtype == "date":
            series, w, e, t = self._cast_date(series, col_type, conservative)
            warnings.extend(w)
            edits += e
            typed_cells += t

        elif dtype == "logical":
            series, w, e, t = self._cast_logical(series, conservative)
            warnings.extend(w)
            edits += e
            typed_cells += t

        else:
            # Keep as text
            typed_cells = series.notna().sum()

        return series, warnings, edits, typed_cells

    def _cast_numeric(
        self, series: pd.Series, col_type: dict[str, Any], conservative: bool
    ) -> tuple[pd.Series, list[str], int, int]:
        """Cast to numeric type.

        Args:
            series: Column to cast.
            col_type: Type specification with format.
            conservative: Keep as text on errors.

        Returns:
            Tuple of (casted_series, warnings, edits, typed_cells).
        """
        warnings = []
        edits = 0

        fmt = col_type.get("format", {"decimal": ".", "thousand": ""})
        series_clean = series.copy()

        # Remove thousand separators
        if fmt["thousand"]:
            series_clean = series_clean.str.replace(fmt["thousand"], "", regex=False)

        # Replace decimal separator with standard dot
        if fmt["decimal"] != ".":
            series_clean = series_clean.str.replace(fmt["decimal"], ".", regex=False)

        # Convert to numeric
        series_numeric = pd.to_numeric(series_clean, errors="coerce")

        # Count failures
        failures = series_numeric.isna().sum() - series.isna().sum()
        edits += int(failures)

        if failures > 0 and conservative:
            warnings.append(f"Failed to convert {failures} values to numeric")
            return series, warnings, edits, 0

        # Check if all are integers
        if series_numeric.notna().any():
            if (series_numeric.dropna() % 1 == 0).all():
                series_numeric = series_numeric.astype("Int64")  # Nullable int

        typed_cells = series_numeric.notna().sum()
        return series_numeric, warnings, edits, typed_cells

    def _cast_date(
        self, series: pd.Series, col_type: dict[str, Any], conservative: bool
    ) -> tuple[pd.Series, list[str], int, int]:
        """Cast to date type.

        Args:
            series: Column to cast.
            col_type: Type specification with format.
            conservative: Keep as text on errors.

        Returns:
            Tuple of (casted_series, warnings, edits, typed_cells).
        """
        warnings = []
        edits = 0

        fmt = col_type.get("format", "%Y-%m-%d")

        try:
            series_date = pd.to_datetime(series, format=fmt, errors="coerce")
            failures = series_date.isna().sum() - series.isna().sum()
            edits += int(failures)

            if failures > 0 and conservative:
                warnings.append(f"Failed to convert {failures} values to date")
                return series, warnings, edits, 0

            typed_cells = series_date.notna().sum()
            return series_date, warnings, edits, typed_cells

        except Exception as e:
            warnings.append(f"Date casting error: {e}")
            return series, warnings, 0, 0

    def _cast_logical(
        self, series: pd.Series, conservative: bool
    ) -> tuple[pd.Series, list[str], int, int]:
        """Cast to logical/boolean type.

        Args:
            series: Column to cast.
            conservative: Keep as text on errors.

        Returns:
            Tuple of (casted_series, warnings, edits, typed_cells).
        """
        warnings = []
        edits = 0

        series_bool = series.map(LOGICAL_VALUES)
        failures = series_bool.isna().sum() - series.isna().sum()
        edits += int(failures)

        if failures > 0 and conservative:
            warnings.append(f"Failed to convert {failures} values to boolean")
            return series, warnings, edits, 0

        typed_cells = series_bool.notna().sum()
        return series_bool, warnings, edits, typed_cells
