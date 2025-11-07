"""Enhanced dialect detection plugin with data consistency scoring.

This plugin detects CSV dialect (delimiter, quote char, escape method) using
data consistency measures from the paper "Wrangling Messy CSV Files by Detecting
Row and Type Patterns" (van den Burg et al., 2018).
"""

import csv
import io
import re
from typing import Any

import pandas as pd

from hypoparsr.core.consistency import compute_data_consistency
from hypoparsr.models import Hypothesis, ParseResult, ParserConfig
from hypoparsr.plugins.base import ParsingPlugin

# Dialect detection constants (from R version + CleverCSV paper)
DELIMITERS = [",", ";", "\t", "|", "\u060c", "\u3001", "\x1c", "\x1d", "\x1e", "\x1f"]
QUOTE_CHARS = ["", '"', "'", "`", "\u00b4", "\u2018", "\u2019", "\u201c", "\u201d"]
LINE_TERMINATORS = ["\r\n", "\n", "\r"]


class DialectPlugin(ParsingPlugin):
    """Enhanced dialect detection using data consistency scoring.

    This is the second plugin in the pipeline (level 2). It takes decoded text
    and detects CSV dialect parameters, scoring each hypothesis using data
    consistency measures (row pattern + type pattern).

    **Key Enhancement**: Unlike traditional approaches that treat all dialects
    equally, this plugin scores each dialect by how consistent the resulting
    parsed data is. High consistency = likely correct dialect.

    Example:
        >>> plugin = DialectPlugin()
        >>> hypotheses = plugin.detect(text, config)
        >>> hypotheses[0].parameters
        {'delimiter': ',', 'quotechar': '"', 'escapechar': None, 'doublequote': True}
        >>> hypotheses[0].confidence
        0.95  # High confidence from data consistency
    """

    @property
    def level_name(self) -> str:
        """Level name for this plugin."""
        return "dialect"

    @property
    def level_order(self) -> int:
        """Pipeline order (2 = second)."""
        return 2

    def detect(self, input_data: str, config: ParserConfig) -> list[Hypothesis]:
        """Detect possible CSV dialects using consistency-based scoring.

        **Enhancement**: Uses data consistency measure (row + type patterns)
        to score each dialect hypothesis, as described in van den Burg et al. (2018).

        Args:
            input_data: Decoded text content (str).
            config: Parser configuration.

        Returns:
            List of dialect hypotheses sorted by consistency score.

        Example:
            >>> hypotheses = plugin.detect(text, config)
            >>> hypotheses[0].confidence  # Highest consistency score
            0.95
            >>> hypotheses[-1].confidence  # Lowest consistency score
            0.15
        """
        # Use sample for fast detection (first 5000 chars or 50 lines)
        sample = self._get_sample(input_data, max_chars=5000, max_lines=50)

        hypotheses = []

        # Try each dialect combination
        for delimiter in DELIMITERS:
            for quotechar in QUOTE_CHARS:
                # Determine escape method
                if not quotechar:
                    # No quotechar, no escaping needed
                    escape_methods = [{"doublequote": False, "escapechar": None}]
                else:
                    # With quotechar, try both double-quote and backslash escape
                    escape_methods = [
                        {"doublequote": True, "escapechar": None},  # "" for "
                        {"doublequote": False, "escapechar": "\\"},  # \" for "
                    ]

                for escape_method in escape_methods:
                    try:
                        # Quick parse with this dialect
                        df = self._parse_sample(
                            sample,
                            delimiter=delimiter,
                            quotechar=quotechar if quotechar else None,
                            doublequote=escape_method["doublequote"],
                            escapechar=escape_method["escapechar"],
                        )

                        # Skip if parsing failed or produced invalid result
                        if df is None or df.empty or len(df.columns) == 0:
                            continue

                        # Compute data consistency score (research enhancement!)
                        consistency_score = compute_data_consistency(
                            df, alpha=0.5, beta=0.5
                        )

                        # Create hypothesis with consistency as confidence
                        hypothesis = Hypothesis(
                            level=self.level_name,
                            confidence=consistency_score,
                            parameters={
                                "delimiter": delimiter,
                                "quotechar": quotechar if quotechar else None,
                                "doublequote": escape_method["doublequote"],
                                "escapechar": escape_method["escapechar"],
                                "lineterminator": "\n",  # Default
                            },
                            metadata={
                                "sample_rows": len(df),
                                "sample_cols": len(df.columns),
                                "consistency_score": consistency_score,
                            },
                        )

                        hypotheses.append(hypothesis)

                    except Exception:
                        # Skip dialects that cause parsing errors
                        continue

        # Sort by consistency score (confidence)
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)

        # Apply top-k filtering (keep only top 10 to reduce search space)
        top_k = 10
        hypotheses = hypotheses[:top_k]

        # If no hypotheses generated, add default fallback
        if not hypotheses:
            hypotheses.append(
                Hypothesis(
                    level=self.level_name,
                    confidence=0.5,
                    parameters={
                        "delimiter": ",",
                        "quotechar": '"',
                        "doublequote": True,
                        "escapechar": None,
                        "lineterminator": "\n",
                    },
                    metadata={"fallback": True},
                )
            )

        return hypotheses

    def parse(
        self, input_data: str, hypothesis: Hypothesis, config: ParserConfig
    ) -> ParseResult:
        """Parse text with specified dialect.

        Args:
            input_data: Decoded text content (str).
            hypothesis: Dialect hypothesis to apply.
            config: Parser configuration.

        Returns:
            Parse result with DataFrame.

        Example:
            >>> result = plugin.parse(text, hypothesis, config)
            >>> isinstance(result.intermediate, pd.DataFrame)
            True
        """
        if not self.validate_hypothesis(hypothesis):
            raise ValueError(
                f"Invalid hypothesis: expected level={self.level_name!r}, "
                f"got {hypothesis.level!r}"
            )

        params = hypothesis.parameters
        warnings = []

        try:
            # Parse entire text with pandas
            df = pd.read_csv(
                io.StringIO(input_data),
                delimiter=params["delimiter"],
                quotechar=params.get("quotechar"),
                doublequote=params.get("doublequote", True),
                escapechar=params.get("escapechar"),
                lineterminator=params.get("lineterminator", "\n"),
                header=None,  # No header inference at this stage
                dtype=str,  # Keep all as strings for now
                keep_default_na=False,  # Don't convert "NA" to NaN yet
                skip_blank_lines=False,  # Keep blank lines for now
            )

            # Replace NaN with empty strings
            df = df.fillna("")

        except Exception as e:
            warnings.append(f"Parsing error: {e}")
            # Return empty DataFrame on error
            df = pd.DataFrame()

        # Calculate cells processed
        cells = df.shape[0] * df.shape[1] if not df.empty else 0

        result = ParseResult(
            intermediate=df,
            hypothesis=hypothesis,
            warnings=warnings,
            cells=cells,
            metadata={
                "rows": len(df),
                "cols": len(df.columns),
                "delimiter": params["delimiter"],
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
            'delimiter=",", quotechar="\\"", escape=double'
        """
        params = hypothesis.parameters
        delimiter_repr = repr(params.get("delimiter", ","))
        quotechar = params.get("quotechar")
        quotechar_repr = repr(quotechar) if quotechar else "none"

        if params.get("doublequote"):
            escape = "double"
        elif params.get("escapechar"):
            escape = f"backslash ({params['escapechar']})"
        else:
            escape = "none"

        return f"delimiter={delimiter_repr}, quotechar={quotechar_repr}, escape={escape}"

    def _get_sample(self, text: str, max_chars: int = 5000, max_lines: int = 50) -> str:
        """Extract sample from text for fast detection.

        Args:
            text: Full text content.
            max_chars: Maximum characters to sample.
            max_lines: Maximum lines to sample.

        Returns:
            Sample text.
        """
        # Take first N characters
        sample = text[:max_chars]

        # Or first N lines, whichever is smaller
        lines = sample.split("\n")[:max_lines]
        sample = "\n".join(lines)

        return sample

    def _parse_sample(
        self,
        sample: str,
        delimiter: str,
        quotechar: str | None,
        doublequote: bool,
        escapechar: str | None,
    ) -> pd.DataFrame | None:
        """Parse sample with given dialect parameters.

        Args:
            sample: Sample text.
            delimiter: Field delimiter.
            quotechar: Quote character.
            doublequote: Whether to use double-quote escaping.
            escapechar: Escape character.

        Returns:
            Parsed DataFrame or None if parsing fails.
        """
        try:
            df = pd.read_csv(
                io.StringIO(sample),
                delimiter=delimiter,
                quotechar=quotechar,
                doublequote=doublequote,
                escapechar=escapechar,
                header=None,
                dtype=str,
                keep_default_na=False,
                skip_blank_lines=False,
                on_bad_lines="skip",  # Skip bad lines during detection
            )

            # Replace NaN with empty strings
            df = df.fillna("")

            return df

        except Exception:
            return None


class PythonDialectDetector:
    """Fallback dialect detector using Python's csv.Sniffer.

    This is a simpler alternative that uses Python's built-in csv module
    for dialect detection. Less accurate than data consistency approach,
    but faster and simpler.

    Example:
        >>> detector = PythonDialectDetector()
        >>> dialect = detector.detect(text)
        >>> dialect.delimiter
        ','
    """

    def detect(self, text: str, sample_size: int = 1024) -> csv.Dialect:
        """Detect dialect using csv.Sniffer.

        Args:
            text: Text content.
            sample_size: Size of sample for detection.

        Returns:
            Detected dialect.

        Example:
            >>> dialect = detector.detect(text)
            >>> dialect.delimiter
            ','
        """
        sample = text[:sample_size]
        sniffer = csv.Sniffer()

        try:
            dialect = sniffer.sniff(sample, delimiters=",;\t|")
            return dialect
        except csv.Error:
            # Return default dialect
            return csv.excel
