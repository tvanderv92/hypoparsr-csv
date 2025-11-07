"""Quality assessment and ranking for parsing results.

This module implements quality-based ranking of parsing results using
multiple features including the data consistency measure from research.
"""

import pandas as pd

from hypoparsr.core.consistency import compute_data_consistency
from hypoparsr.models import ParseResult, QualityMetrics, QualityWeights


def extract_quality_features(result: ParseResult) -> QualityMetrics:
    """Extract quality features from a parsing result.

    Features extracted:
    1. warnings: Number of warnings generated
    2. edits: Number of edits made to data
    3. moves: Number of cell moves
    4. confidence: Sum of path confidences
    5. total_cells: Total number of cells
    6. typed_cells: Cells with typed data (non-text)
    7. empty_headers: Empty column names
    8. empty_cells: Empty data cells
    9. non_latin_chars: Non-Latin character count
    10. row_col_ratio: 1 if rows > cols, 0 otherwise
    11. data_consistency: Data consistency score (research enhancement)

    Args:
        result: Parse result to analyze.

    Returns:
        QualityMetrics with all features.

    Example:
        >>> metrics = extract_quality_features(result)
        >>> metrics.confidence
        0.95
        >>> metrics.typed_cells
        100
    """
    # Default values
    warnings = len(result.warnings)
    edits = result.edits
    moves = result.moves
    total_cells = result.cells

    # Get intermediate data
    intermediate = result.intermediate

    if not isinstance(intermediate, pd.DataFrame):
        # Can't analyze non-DataFrame results
        return QualityMetrics(
            warnings=warnings,
            edits=edits,
            moves=moves,
            confidence=result.hypothesis.confidence,
            total_cells=total_cells,
        )

    df = intermediate

    if df.empty:
        return QualityMetrics(
            warnings=warnings,
            edits=edits,
            moves=moves,
            confidence=result.hypothesis.confidence,
            total_cells=0,
        )

    # Calculate confidence (from metadata or hypothesis)
    path_confidence = result.metadata.get("path_confidence", result.hypothesis.confidence)

    # Calculate total cells
    if total_cells == 0:
        total_cells = df.shape[0] * df.shape[1]

    # Calculate typed cells (non-object dtype or non-empty cells with types)
    typed_cells = 0
    for col in df.columns:
        if df[col].dtype != "object":
            # Numeric, datetime, etc. - count non-NA
            typed_cells += df[col].notna().sum()
        else:
            # Object type - count non-empty strings
            typed_cells += (df[col].notna() & (df[col] != "")).sum()

    # Count empty headers
    empty_headers = sum(1 for col in df.columns if str(col) == "" or pd.isna(col))

    # Count empty cells
    empty_cells = 0
    for col in df.columns:
        empty_cells += (df[col].isna() | (df[col] == "")).sum()

    # Count non-Latin characters (approximate)
    non_latin_chars = 0
    try:
        # Convert DataFrame to string and count non-ASCII characters
        text = df.to_string()
        non_latin_chars = sum(1 for char in text if ord(char) > 127)
    except Exception:
        non_latin_chars = 0

    # Row-to-column ratio
    row_col_ratio = 1.0 if df.shape[0] > df.shape[1] else 0.0

    # Data consistency score (research enhancement!)
    data_consistency = 0.0
    try:
        data_consistency = compute_data_consistency(df, alpha=0.5, beta=0.5)
    except Exception:
        # If consistency calculation fails, use 0
        data_consistency = 0.0

    metrics = QualityMetrics(
        warnings=warnings,
        edits=edits,
        moves=moves,
        confidence=path_confidence,
        total_cells=total_cells,
        typed_cells=typed_cells,
        empty_headers=empty_headers,
        empty_cells=empty_cells,
        non_latin_chars=non_latin_chars,
        row_col_ratio=row_col_ratio,
    )

    # Add data_consistency to metadata (since it's not in base QualityMetrics)
    # We'll need to access it separately
    result.metadata["data_consistency"] = data_consistency

    return metrics


def rank_results(
    results: list[ParseResult], weights: QualityWeights | None = None
) -> list[int]:
    """Rank parsing results by quality.

    Normalizes each feature to [0, 1] range and computes weighted sum.
    Returns indices sorted by quality (best first).

    Args:
        results: List of parsing results to rank.
        weights: Quality weights (uses defaults if None).

    Returns:
        List of indices sorted by quality score (highest first).

    Example:
        >>> ranking = rank_results(results)
        >>> best_result = results[ranking[0]]
        >>> second_best = results[ranking[1]]
    """
    if not results:
        return []

    if weights is None:
        weights = QualityWeights()

    # Extract features for all results
    all_metrics = [extract_quality_features(result) for result in results]

    # Extract data consistency scores
    consistency_scores = [
        result.metadata.get("data_consistency", 0.0) for result in results
    ]

    # Build feature matrix
    n_results = len(results)
    features = {
        "warnings": [m.warnings for m in all_metrics],
        "edits": [m.edits for m in all_metrics],
        "moves": [m.moves for m in all_metrics],
        "confidence": [m.confidence for m in all_metrics],
        "total_cells": [m.total_cells for m in all_metrics],
        "typed_cells": [m.typed_cells for m in all_metrics],
        "empty_headers": [m.empty_headers for m in all_metrics],
        "empty_cells": [m.empty_cells for m in all_metrics],
        "non_latin_chars": [m.non_latin_chars for m in all_metrics],
        "row_col_ratio": [m.row_col_ratio for m in all_metrics],
        "data_consistency": consistency_scores,  # Research enhancement!
    }

    # Get weights as dict
    weight_dict = weights.to_dict()
    # Add data_consistency weight (default 1.5 - higher than others)
    weight_dict["data_consistency"] = 1.5

    # Calculate quality scores
    quality_scores = [0.0] * n_results

    for feature_name, feature_values in features.items():
        weight = weight_dict.get(feature_name, 0.0)

        # Normalize feature to [0, 1]
        min_val = min(feature_values)
        max_val = max(feature_values)

        if max_val - min_val > 0:
            normalized = [
                (val - min_val) / (max_val - min_val) for val in feature_values
            ]
        else:
            normalized = [0.0] * n_results

        # Add weighted normalized value to quality score
        for i in range(n_results):
            quality_scores[i] += weight * normalized[i]

    # Sort by quality score (descending)
    ranking = sorted(range(n_results), key=lambda i: quality_scores[i], reverse=True)

    return ranking


def get_quality_report(
    results: list[ParseResult], weights: QualityWeights | None = None
) -> pd.DataFrame:
    """Generate quality report for all results.

    Args:
        results: List of parsing results.
        weights: Quality weights.

    Returns:
        DataFrame with quality features and scores for all results.

    Example:
        >>> report = get_quality_report(results)
        >>> report.columns
        ['rank', 'confidence', 'typed_cells', 'warnings', 'quality_score']
    """
    if not results:
        return pd.DataFrame()

    # Extract metrics
    all_metrics = [extract_quality_features(result) for result in results]

    # Get ranking
    ranking = rank_results(results, weights)

    # Build report DataFrame
    report_data = []
    for rank_idx, result_idx in enumerate(ranking):
        metrics = all_metrics[result_idx]
        result = results[result_idx]

        report_data.append(
            {
                "rank": rank_idx + 1,
                "result_index": result_idx,
                "confidence": metrics.confidence,
                "typed_cells": metrics.typed_cells,
                "total_cells": metrics.total_cells,
                "warnings": metrics.warnings,
                "edits": metrics.edits,
                "empty_headers": metrics.empty_headers,
                "data_consistency": result.metadata.get("data_consistency", 0.0),
            }
        )

    report_df = pd.DataFrame(report_data)

    return report_df


def compare_results(result1: ParseResult, result2: ParseResult) -> dict[str, float]:
    """Compare two parsing results.

    Args:
        result1: First result.
        result2: Second result.

    Returns:
        Dictionary with comparison metrics.

    Example:
        >>> comparison = compare_results(best_result, second_best)
        >>> comparison['confidence_diff']
        0.05
    """
    metrics1 = extract_quality_features(result1)
    metrics2 = extract_quality_features(result2)

    comparison = {
        "confidence_diff": metrics1.confidence - metrics2.confidence,
        "typed_cells_diff": metrics1.typed_cells - metrics2.typed_cells,
        "warnings_diff": metrics1.warnings - metrics2.warnings,
        "edits_diff": metrics1.edits - metrics2.edits,
        "consistency_diff": result1.metadata.get("data_consistency", 0.0)
        - result2.metadata.get("data_consistency", 0.0),
    }

    return comparison
