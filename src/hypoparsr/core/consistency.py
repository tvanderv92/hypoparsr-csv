"""Data consistency measures for CSV parsing.

This module implements data consistency scoring based on the paper:
"Wrangling Messy CSV Files by Detecting Row and Type Patterns"
by van den Burg, Nazabal, and Sutton (2018).

The consistency measure combines:
1. Row pattern score - structural regularity (consistent row lengths)
2. Type pattern score - data type coherence (consistent column types)
"""

import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import entropy


def compute_row_pattern_score(df: pd.DataFrame) -> float:
    """Compute row pattern consistency score.

    Measures structural regularity by analyzing row length distribution.
    Uses entropy-based measure where lower entropy indicates more consistent
    row lengths (better structure).

    Args:
        df: Parsed DataFrame to evaluate.

    Returns:
        Score between 0.0 (inconsistent) and 1.0 (perfectly consistent).

    Examples:
        >>> df = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        >>> score = compute_row_pattern_score(df)
        >>> score
        1.0

        >>> df = pd.DataFrame({0: [1, 2, 3], 1: [4, None, None]})
        >>> score = compute_row_pattern_score(df)
        >>> score < 0.5
        True
    """
    if df.empty:
        return 0.0

    # Count non-empty cells per row
    row_lengths = df.notna().sum(axis=1)

    if len(row_lengths) == 0:
        return 0.0

    # All rows same length → perfect consistency
    if row_lengths.nunique() == 1:
        return 1.0

    # Compute normalized entropy of row length distribution
    value_counts = row_lengths.value_counts(normalize=True)
    row_entropy = entropy(value_counts.values, base=2)

    # Maximum entropy: all rows have different lengths
    max_entropy = np.log2(len(row_lengths))

    if max_entropy == 0:
        return 1.0

    # Normalize and invert: high entropy → low score
    normalized_entropy = row_entropy / max_entropy
    consistency_score = 1.0 - normalized_entropy

    return float(consistency_score)


def compute_type_pattern_score(df: pd.DataFrame) -> float:
    """Compute type pattern consistency score.

    Measures data type coherence by analyzing column-wise type purity.
    A correct parse produces columns with coherent types (e.g., all numeric,
    all dates). An incorrect parse produces mixed types.

    Args:
        df: Parsed DataFrame to evaluate.

    Returns:
        Score between 0.0 (incoherent) and 1.0 (perfectly coherent).

    Examples:
        >>> df = pd.DataFrame({"age": ["25", "30", "35"], "name": ["Alice", "Bob", "Charlie"]})
        >>> score = compute_type_pattern_score(df)
        >>> score > 0.9
        True

        >>> df = pd.DataFrame({"mixed": ["25,Alice", "30,Bob", "35,Charlie"]})
        >>> score = compute_type_pattern_score(df)
        >>> score < 0.5
        True
    """
    if df.empty:
        return 0.0

    column_purities = []

    for col in df.columns:
        # Skip columns with all NA values
        non_na_values = df[col].dropna()
        if len(non_na_values) == 0:
            continue

        # Detect type for each non-empty cell
        types = [_detect_cell_type(str(value)) for value in non_na_values]

        if not types:
            continue

        # Compute type purity: fraction of most common type
        type_counts = Counter(types)
        most_common_count = type_counts.most_common(1)[0][1]
        purity = most_common_count / len(types)

        column_purities.append(purity)

    if not column_purities:
        return 0.0

    # Average purity across all columns
    avg_purity = float(np.mean(column_purities))

    return avg_purity


def compute_data_consistency(
    df: pd.DataFrame, alpha: float = 0.5, beta: float = 0.5
) -> float:
    """Compute overall data consistency score.

    Combines row pattern and type pattern scores into a single consistency
    measure. This is the core metric for evaluating dialect quality.

    Args:
        df: Parsed DataFrame to evaluate.
        alpha: Weight for row pattern score (default 0.5).
        beta: Weight for type pattern score (default 0.5).

    Returns:
        Weighted consistency score between 0.0 and 1.0.

    Raises:
        ValueError: If alpha + beta != 1.0.

    Examples:
        >>> df = pd.DataFrame([[1, 2, 3], [4, 5, 6]])
        >>> score = compute_data_consistency(df)
        >>> 0.0 <= score <= 1.0
        True
    """
    if not np.isclose(alpha + beta, 1.0):
        raise ValueError(f"Weights must sum to 1.0, got alpha={alpha}, beta={beta}")

    row_score = compute_row_pattern_score(df)
    type_score = compute_type_pattern_score(df)

    consistency = alpha * row_score + beta * type_score

    return float(consistency)


def _detect_cell_type(value: str) -> str:
    """Detect the data type of a cell value.

    Args:
        value: String cell value to classify.

    Returns:
        Type label: "numeric", "date", "logical", "email", "url", "empty", or "text".

    Examples:
        >>> _detect_cell_type("123")
        'numeric'
        >>> _detect_cell_type("2023-01-15")
        'date'
        >>> _detect_cell_type("true")
        'logical'
        >>> _detect_cell_type("test@example.com")
        'email'
    """
    # Empty or whitespace
    if not value or value.strip() == "":
        return "empty"

    value = value.strip()

    # Numeric: integer or float
    if re.match(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$", value):
        return "numeric"

    # Numeric with separators (e.g., 1,000.00)
    if re.match(r"^[+-]?\d{1,3}(,\d{3})*(\.\d+)?$", value):
        return "numeric"

    # Date patterns (various formats)
    # YYYY-MM-DD, DD-MM-YYYY, MM/DD/YYYY, etc.
    date_patterns = [
        r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$",  # YYYY-MM-DD
        r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{4}$",  # DD-MM-YYYY or MM-DD-YYYY
        r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2}$",  # DD-MM-YY
    ]
    if any(re.match(pattern, value) for pattern in date_patterns):
        return "date"

    # Logical/Boolean
    if value.lower() in ("true", "false", "yes", "no", "t", "f", "y", "n", "1", "0"):
        return "logical"

    # Email
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        return "email"

    # URL
    if re.match(r"^https?://[^\s]+$", value, re.IGNORECASE):
        return "url"

    # Default to text
    return "text"


def compute_column_type_purity(df: pd.DataFrame, column: str | int) -> float:
    """Compute type purity for a single column.

    Args:
        df: DataFrame containing the column.
        column: Column name or index.

    Returns:
        Type purity score between 0.0 and 1.0.

    Examples:
        >>> df = pd.DataFrame({"col": ["1", "2", "3", "text"]})
        >>> purity = compute_column_type_purity(df, "col")
        >>> purity
        0.75
    """
    if column not in df.columns:
        raise ValueError(f"Column {column!r} not found in DataFrame")

    non_na_values = df[column].dropna()
    if len(non_na_values) == 0:
        return 0.0

    types = [_detect_cell_type(str(value)) for value in non_na_values]

    if not types:
        return 0.0

    # Compute purity
    type_counts = Counter(types)
    most_common_count = type_counts.most_common(1)[0][1]
    purity = most_common_count / len(types)

    return float(purity)


def get_dominant_type(df: pd.DataFrame, column: str | int) -> str:
    """Get the dominant (most common) data type in a column.

    Args:
        df: DataFrame containing the column.
        column: Column name or index.

    Returns:
        Dominant type label.

    Examples:
        >>> df = pd.DataFrame({"col": ["1", "2", "3", "text"]})
        >>> get_dominant_type(df, "col")
        'numeric'
    """
    if column not in df.columns:
        raise ValueError(f"Column {column!r} not found in DataFrame")

    non_na_values = df[column].dropna()
    if len(non_na_values) == 0:
        return "empty"

    types = [_detect_cell_type(str(value)) for value in non_na_values]

    if not types:
        return "empty"

    # Get most common type
    type_counts = Counter(types)
    dominant_type = type_counts.most_common(1)[0][0]

    return dominant_type
