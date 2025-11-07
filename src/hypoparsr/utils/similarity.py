"""Similarity metrics for comparing parsing results.

This module provides functions to compare two DataFrames and calculate
similarity metrics, which is used for regression testing against R outputs.
"""

from typing import Any

import numpy as np
import pandas as pd
from Levenshtein import distance as levenshtein_distance


def calculate_structure_similarity(
    df1: pd.DataFrame, df2: pd.DataFrame
) -> dict[str, float]:
    """Calculate structural similarity between two DataFrames.

    Args:
        df1: First DataFrame.
        df2: Second DataFrame.

    Returns:
        Dictionary with similarity metrics:
        - shape_match: 1.0 if shapes match, 0.0 otherwise
        - row_similarity: Ratio of matching row count
        - col_similarity: Ratio of matching column count
        - size_similarity: Ratio of matching total cells

    Example:
        >>> sim = calculate_structure_similarity(df1, df2)
        >>> sim['shape_match']
        1.0
    """
    # Shape matching
    shape_match = 1.0 if df1.shape == df2.shape else 0.0

    # Row and column similarity
    max_rows = max(df1.shape[0], df2.shape[0])
    min_rows = min(df1.shape[0], df2.shape[0])
    row_similarity = min_rows / max_rows if max_rows > 0 else 1.0

    max_cols = max(df1.shape[1], df2.shape[1])
    min_cols = min(df1.shape[1], df2.shape[1])
    col_similarity = min_cols / max_cols if max_cols > 0 else 1.0

    # Total size similarity
    size1 = df1.shape[0] * df1.shape[1]
    size2 = df2.shape[0] * df2.shape[1]
    max_size = max(size1, size2)
    min_size = min(size1, size2)
    size_similarity = min_size / max_size if max_size > 0 else 1.0

    return {
        "shape_match": shape_match,
        "row_similarity": row_similarity,
        "col_similarity": col_similarity,
        "size_similarity": size_similarity,
    }


def calculate_content_similarity(
    df1: pd.DataFrame, df2: pd.DataFrame, normalize: bool = True
) -> dict[str, float]:
    """Calculate content similarity between two DataFrames.

    Compares actual cell values using string representation.

    Args:
        df1: First DataFrame.
        df2: Second DataFrame.
        normalize: If True, normalize values before comparison.

    Returns:
        Dictionary with similarity metrics:
        - cell_match_rate: Ratio of exactly matching cells
        - levenshtein_similarity: Average string similarity (0-1)
        - type_match_rate: Ratio of cells with matching types

    Example:
        >>> sim = calculate_content_similarity(df1, df2)
        >>> sim['cell_match_rate']
        0.85
    """
    # Align shapes for comparison
    min_rows = min(df1.shape[0], df2.shape[0])
    min_cols = min(df1.shape[1], df2.shape[1])

    if min_rows == 0 or min_cols == 0:
        return {
            "cell_match_rate": 0.0,
            "levenshtein_similarity": 0.0,
            "type_match_rate": 0.0,
        }

    # Truncate to common size
    df1_subset = df1.iloc[:min_rows, :min_cols]
    df2_subset = df2.iloc[:min_rows, :min_cols]

    # Normalize if requested
    if normalize:
        df1_subset = _normalize_dataframe(df1_subset)
        df2_subset = _normalize_dataframe(df2_subset)

    # Cell-by-cell comparison
    total_cells = min_rows * min_cols
    exact_matches = 0
    type_matches = 0
    levenshtein_total = 0.0

    for i in range(min_rows):
        for j in range(min_cols):
            val1 = df1_subset.iloc[i, j]
            val2 = df2_subset.iloc[i, j]

            # Exact match
            if _values_equal(val1, val2):
                exact_matches += 1

            # Type match
            if type(val1) == type(val2):
                type_matches += 1

            # Levenshtein similarity
            str1 = str(val1) if not pd.isna(val1) else ""
            str2 = str(val2) if not pd.isna(val2) else ""
            max_len = max(len(str1), len(str2))

            if max_len > 0:
                lev_dist = levenshtein_distance(str1, str2)
                similarity = 1.0 - (lev_dist / max_len)
                levenshtein_total += similarity
            else:
                levenshtein_total += 1.0

    return {
        "cell_match_rate": exact_matches / total_cells,
        "levenshtein_similarity": levenshtein_total / total_cells,
        "type_match_rate": type_matches / total_cells,
    }


def calculate_overall_similarity(
    df1: pd.DataFrame, df2: pd.DataFrame, weights: dict[str, float] | None = None
) -> float:
    """Calculate overall similarity score between two DataFrames.

    Combines structural and content similarity with weights.

    Args:
        df1: First DataFrame.
        df2: Second DataFrame.
        weights: Custom weights for each metric. If None, uses defaults.

    Returns:
        Overall similarity score (0-1), where 1 is identical.

    Example:
        >>> similarity = calculate_overall_similarity(df1, df2)
        >>> similarity
        0.87
    """
    if weights is None:
        weights = {
            "shape_match": 0.15,
            "row_similarity": 0.10,
            "col_similarity": 0.10,
            "size_similarity": 0.10,
            "cell_match_rate": 0.25,
            "levenshtein_similarity": 0.20,
            "type_match_rate": 0.10,
        }

    # Calculate all metrics
    structure_sim = calculate_structure_similarity(df1, df2)
    content_sim = calculate_content_similarity(df1, df2)

    # Combine metrics
    all_metrics = {**structure_sim, **content_sim}

    # Weighted average
    total_score = 0.0
    total_weight = 0.0

    for metric_name, metric_value in all_metrics.items():
        if metric_name in weights:
            total_score += weights[metric_name] * metric_value
            total_weight += weights[metric_name]

    if total_weight == 0:
        return 0.0

    return total_score / total_weight


def compare_dataframes(
    df1: pd.DataFrame, df2: pd.DataFrame, name1: str = "df1", name2: str = "df2"
) -> dict[str, Any]:
    """Comprehensive comparison of two DataFrames.

    Args:
        df1: First DataFrame.
        df2: Second DataFrame.
        name1: Name for first DataFrame (for reporting).
        name2: Name for second DataFrame (for reporting).

    Returns:
        Dictionary with full comparison report including:
        - structure: Structural similarity metrics
        - content: Content similarity metrics
        - overall_similarity: Combined similarity score
        - differences: Summary of key differences

    Example:
        >>> report = compare_dataframes(python_df, r_df, "Python", "R")
        >>> report['overall_similarity']
        0.87
        >>> report['differences']
        {'shape': 'Match', 'rows_diff': 0, 'cols_diff': 0}
    """
    structure_sim = calculate_structure_similarity(df1, df2)
    content_sim = calculate_content_similarity(df1, df2)
    overall_sim = calculate_overall_similarity(df1, df2)

    # Identify key differences
    differences = {
        "shape": "Match" if df1.shape == df2.shape else "Mismatch",
        "rows_diff": df1.shape[0] - df2.shape[0],
        "cols_diff": df1.shape[1] - df2.shape[1],
        "shape_1": df1.shape,
        "shape_2": df2.shape,
    }

    # Column name differences (if shapes allow)
    if df1.shape[1] == df2.shape[1]:
        col_matches = sum(
            1 for c1, c2 in zip(df1.columns, df2.columns) if str(c1) == str(c2)
        )
        differences["column_name_matches"] = col_matches
        differences["column_name_match_rate"] = col_matches / df1.shape[1]
    else:
        differences["column_name_matches"] = 0
        differences["column_name_match_rate"] = 0.0

    return {
        "name1": name1,
        "name2": name2,
        "structure": structure_sim,
        "content": content_sim,
        "overall_similarity": overall_sim,
        "differences": differences,
    }


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize DataFrame for comparison.

    Converts all values to strings, strips whitespace, lowercases text.

    Args:
        df: DataFrame to normalize.

    Returns:
        Normalized DataFrame.
    """
    df_normalized = df.copy()

    for col in df_normalized.columns:
        df_normalized[col] = df_normalized[col].apply(_normalize_value)

    return df_normalized


def _normalize_value(value: Any) -> Any:
    """Normalize a single value for comparison.

    Args:
        value: Value to normalize.

    Returns:
        Normalized value.
    """
    if pd.isna(value):
        return value

    # Convert to string and normalize
    str_value = str(value).strip().lower()

    # Try to convert back to numeric if possible
    try:
        if "." in str_value:
            return float(str_value)
        return int(str_value)
    except (ValueError, TypeError):
        return str_value


def _values_equal(val1: Any, val2: Any) -> bool:
    """Check if two values are equal, handling NaN.

    Args:
        val1: First value.
        val2: Second value.

    Returns:
        True if values are equal.
    """
    # Both NaN
    if pd.isna(val1) and pd.isna(val2):
        return True

    # One NaN, one not
    if pd.isna(val1) or pd.isna(val2):
        return False

    # Both numeric
    if isinstance(val1, (int, float, np.number)) and isinstance(
        val2, (int, float, np.number)
    ):
        return np.isclose(val1, val2, rtol=1e-5, atol=1e-8)

    # String comparison
    return str(val1) == str(val2)
