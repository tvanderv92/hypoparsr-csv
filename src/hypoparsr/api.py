"""Public API for hypoparsr - CSV parsing for messy data.

This module provides the main user-facing interface for parsing CSV files
with automatic hypothesis generation and quality-based ranking.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from hypoparsr.core.orchestrator import ParserOrchestrator
from hypoparsr.core.quality import get_quality_report, rank_results
from hypoparsr.models import ParseResult, ParserConfig


class ParsingResult:
    """User-friendly wrapper for parsing results.

    Provides easy access to the best parsing result, quality metrics,
    and comparison between different hypotheses.

    Attributes:
        results: All parsing results (sorted by quality, best first).
        best: The highest quality parsing result.
        config: Parser configuration used.

    Example:
        >>> result = parse_file("messy_data.csv")
        >>> df = result.to_dataframe()
        >>> print(result)
        Parsing completed with 5 hypotheses. Best quality: 0.89
        >>> result.show_alternatives(n=3)
        ... displays top 3 parsing alternatives ...
    """

    def __init__(
        self, results: list[ParseResult], config: ParserConfig, file_path: str
    ):
        """Initialize parsing result.

        Args:
            results: List of parsing results (unranked).
            config: Parser configuration.
            file_path: Path to parsed file.
        """
        self.file_path = file_path
        self.config = config

        # Rank results by quality
        if results:
            ranking = rank_results(results)
            self.results = [results[i] for i in ranking]
            self.best = self.results[0]
        else:
            self.results = []
            self.best = None

        # Get quality report
        self._quality_report = get_quality_report(results) if results else None

    def to_dataframe(self) -> pd.DataFrame:
        """Get the best parsing result as a pandas DataFrame.

        Returns:
            DataFrame with the highest quality parsing result.

        Raises:
            ValueError: If no valid parsing results exist.

        Example:
            >>> result = parse_file("data.csv")
            >>> df = result.to_dataframe()
            >>> df.head()
            ... displays first rows of best result ...
        """
        if self.best is None:
            raise ValueError("No valid parsing results available")

        intermediate = self.best.intermediate

        if not isinstance(intermediate, pd.DataFrame):
            raise ValueError(
                f"Expected DataFrame result, got {type(intermediate).__name__}"
            )

        return intermediate.copy()

    def get_alternative(self, index: int) -> pd.DataFrame:
        """Get an alternative parsing result by rank.

        Args:
            index: Rank index (0 = best, 1 = second best, etc.).

        Returns:
            DataFrame for the requested alternative.

        Raises:
            IndexError: If index is out of range.
            ValueError: If result is not a DataFrame.

        Example:
            >>> result = parse_file("data.csv")
            >>> df2 = result.get_alternative(1)  # Second best
        """
        if index < 0 or index >= len(self.results):
            raise IndexError(
                f"Alternative index {index} out of range (0-{len(self.results)-1})"
            )

        alternative = self.results[index].intermediate

        if not isinstance(alternative, pd.DataFrame):
            raise ValueError(
                f"Expected DataFrame result, got {type(alternative).__name__}"
            )

        return alternative.copy()

    def show_alternatives(self, n: int = 5) -> pd.DataFrame:
        """Show quality comparison of top N parsing alternatives.

        Args:
            n: Number of alternatives to show (default: 5).

        Returns:
            DataFrame with quality metrics for each alternative.

        Example:
            >>> result = parse_file("data.csv")
            >>> result.show_alternatives(3)
               rank  confidence  typed_cells  warnings  edits  ...
            0     1        0.89          150         0      2  ...
            1     2        0.82          148         1      3  ...
            2     3        0.79          145         2      5  ...
        """
        if self._quality_report is None or self._quality_report.empty:
            return pd.DataFrame()

        return self._quality_report.head(n).copy()

    def summary(self) -> dict[str, Any]:
        """Get summary statistics about the parsing results.

        Returns:
            Dictionary with summary information.

        Example:
            >>> result = parse_file("data.csv")
            >>> result.summary()
            {
                'file': 'data.csv',
                'num_hypotheses': 5,
                'best_confidence': 0.89,
                'shape': (100, 5),
                'warnings': [],
                'data_consistency': 0.92
            }
        """
        if self.best is None:
            return {
                "file": self.file_path,
                "num_hypotheses": 0,
                "best_confidence": 0.0,
                "shape": (0, 0),
                "warnings": ["No valid parsing results"],
            }

        df = self.to_dataframe()

        return {
            "file": self.file_path,
            "num_hypotheses": len(self.results),
            "best_confidence": self.best.hypothesis.confidence,
            "shape": df.shape,
            "warnings": self.best.warnings,
            "data_consistency": self.best.metadata.get("data_consistency", 0.0),
            "row_functions": self.best.metadata.get("row_functions", []),
            "column_functions": self.best.metadata.get("column_functions", []),
        }

    def __repr__(self) -> str:
        """Human-readable representation.

        Returns:
            String description of parsing results.

        Example:
            >>> result = parse_file("data.csv")
            >>> print(result)
            Parsing 'data.csv' completed with 5 hypotheses
            Best result: confidence=0.89, shape=(100, 5), warnings=0
        """
        if self.best is None:
            return f"Parsing '{self.file_path}' failed: No valid results"

        df = self.to_dataframe()
        confidence = self.best.hypothesis.confidence
        warnings_count = len(self.best.warnings)

        return (
            f"Parsing '{self.file_path}' completed with {len(self.results)} hypotheses\n"
            f"Best result: confidence={confidence:.2f}, shape={df.shape}, "
            f"warnings={warnings_count}"
        )

    def __str__(self) -> str:
        """String representation (same as __repr__)."""
        return self.__repr__()


def parse_file(
    file_path: str,
    config: ParserConfig | None = None,
    preset: str | None = None,
) -> ParsingResult:
    """Parse a CSV file with automatic hypothesis generation.

    This is the main entry point for hypoparsr. It automatically:
    1. Detects file encoding
    2. Tests multiple CSV dialects
    3. Identifies table areas
    4. Classifies rows and columns
    5. Infers and casts data types
    6. Ranks results by quality

    Args:
        file_path: Path to CSV file to parse.
        config: Custom parser configuration (optional).
        preset: Configuration preset name: 'strict', 'lenient', or 'fast' (optional).
            If both config and preset are provided, config takes precedence.

    Returns:
        ParsingResult with best result and alternatives.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If preset is invalid.

    Example:
        >>> # Simple usage with defaults
        >>> result = parse_file("messy_data.csv")
        >>> df = result.to_dataframe()

        >>> # Use preset for faster parsing
        >>> result = parse_file("clean_data.csv", preset="fast")

        >>> # Custom configuration
        >>> config = ParserConfig(
        ...     max_hypotheses=5,
        ...     conservative_casting=True,
        ...     only_one_table=True
        ... )
        >>> result = parse_file("data.csv", config=config)

        >>> # Show alternative parsing results
        >>> result.show_alternatives(3)

        >>> # Get full summary
        >>> result.summary()
    """
    # Validate file path
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")

    # Handle configuration
    if config is None:
        if preset is not None:
            config = get_config_preset(preset)
        else:
            config = ParserConfig()  # Use defaults

    # Parse file using orchestrator
    orchestrator = ParserOrchestrator()
    results = orchestrator.parse_file(str(path), config)

    # Wrap in user-friendly result
    return ParsingResult(results, config, str(path))


def get_config_preset(preset: str) -> ParserConfig:
    """Get a predefined configuration preset.

    Available presets:
    - 'strict': Conservative type casting, single table only, higher pruning
    - 'lenient': Aggressive type casting, multiple tables, lower pruning
    - 'fast': Similar to strict, optimized for clean files

    Args:
        preset: Name of preset ('strict', 'lenient', or 'fast').

    Returns:
        ParserConfig with preset values.

    Raises:
        ValueError: If preset name is invalid.

    Example:
        >>> config = get_config_preset("strict")
        >>> result = parse_file("data.csv", config=config)
    """
    presets = {
        "strict": ParserConfig(
            pruning_level=0.2,
            conservative_type_casting=True,
            only_one_table=True,
            remove_aggregates=True,
            remove_named_empty_cols=True,
        ),
        "lenient": ParserConfig(
            pruning_level=0.05,
            conservative_type_casting=False,
            only_one_table=False,
            remove_aggregates=False,
            remove_named_empty_cols=False,
        ),
        "fast": ParserConfig(
            pruning_level=0.15,
            conservative_type_casting=True,
            only_one_table=True,
            remove_aggregates=True,
            remove_named_empty_cols=True,
        ),
    }

    if preset not in presets:
        valid = ", ".join(presets.keys())
        raise ValueError(f"Invalid preset '{preset}'. Valid presets: {valid}")

    return presets[preset]


# Convenience aliases
parse = parse_file  # Shorter alias
read_csv = parse_file  # pandas-style alias
