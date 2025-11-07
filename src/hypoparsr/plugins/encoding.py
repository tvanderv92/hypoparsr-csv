"""Encoding detection plugin using chardet.

This plugin detects the character encoding of CSV files, which is the first
step in the parsing pipeline.
"""

from pathlib import Path

import chardet

from hypoparsr.models import Hypothesis, ParseResult, ParserConfig
from hypoparsr.plugins.base import ParsingPlugin


class EncodingPlugin(ParsingPlugin):
    """Detects file encoding using chardet library.

    This is the first plugin in the parsing pipeline (level 1). It reads a
    sample of the file and detects possible encodings with confidence scores.

    Example:
        >>> plugin = EncodingPlugin()
        >>> hypotheses = plugin.detect("data.csv", config)
        >>> hypotheses[0].parameters['encoding']
        'utf-8'
        >>> hypotheses[0].confidence
        0.99
    """

    @property
    def level_name(self) -> str:
        """Level name for this plugin."""
        return "encoding"

    @property
    def level_order(self) -> int:
        """Pipeline order (1 = first)."""
        return 1

    def detect(self, input_data: str, config: ParserConfig) -> list[Hypothesis]:
        """Detect possible encodings for file.

        Args:
            input_data: File path (str).
            config: Parser configuration.

        Returns:
            List of encoding hypotheses sorted by confidence.

        Example:
            >>> hypotheses = plugin.detect("data.csv", config)
            >>> len(hypotheses)
            3
            >>> hypotheses[0].parameters
            {'encoding': 'utf-8', 'language': 'English'}
        """
        file_path = Path(input_data)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read sample for detection
        sample_size = min(10000, file_path.stat().st_size)

        with open(file_path, "rb") as f:
            raw_sample = f.read(sample_size)

        # Detect encoding using chardet
        detection = chardet.detect(raw_sample)

        hypotheses = []

        # Handle None or empty detection
        if detection is None:
            detection = {"encoding": None, "confidence": 0.0}

        # Primary hypothesis from chardet
        if detection.get("encoding"):
            primary_hypothesis = Hypothesis(
                level=self.level_name,
                confidence=detection["confidence"],
                parameters={
                    "encoding": detection["encoding"],
                    "language": detection.get("language", "unknown"),
                },
                metadata={"detector": "chardet", "sample_size": sample_size},
            )
            hypotheses.append(primary_hypothesis)

        # Add fallback encodings with lower confidence
        fallback_encodings = ["utf-8", "latin-1", "cp1252", "ascii"]
        detected_encoding = detection.get("encoding") or ""
        detected_encoding = detected_encoding.lower()

        for encoding in fallback_encodings:
            # Skip if already detected
            if encoding.lower() == detected_encoding:
                continue

            # Try to decode with this encoding
            try:
                raw_sample.decode(encoding)
                # If successful, add as hypothesis with low confidence
                fallback_hypothesis = Hypothesis(
                    level=self.level_name,
                    confidence=0.3,  # Low confidence for fallbacks
                    parameters={"encoding": encoding, "language": "unknown"},
                    metadata={"detector": "fallback"},
                )
                hypotheses.append(fallback_hypothesis)
            except (UnicodeDecodeError, LookupError):
                # Skip encodings that can't decode the sample
                continue

        # Sort by confidence
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)

        # Limit to top 5 hypotheses
        return hypotheses[:5]

    def parse(
        self, input_data: str, hypothesis: Hypothesis, config: ParserConfig
    ) -> ParseResult:
        """Parse file with specified encoding.

        Args:
            input_data: File path (str).
            hypothesis: Encoding hypothesis to apply.
            config: Parser configuration.

        Returns:
            Parse result with decoded text content.

        Example:
            >>> result = plugin.parse("data.csv", hypothesis, config)
            >>> isinstance(result.intermediate, str)
            True
        """
        if not self.validate_hypothesis(hypothesis):
            raise ValueError(
                f"Invalid hypothesis: expected level={self.level_name!r}, "
                f"got {hypothesis.level!r}"
            )

        file_path = Path(input_data)
        encoding = hypothesis.parameters.get("encoding")

        if not encoding:
            raise ValueError("Encoding parameter missing from hypothesis")

        warnings = []

        try:
            # Read entire file with detected encoding
            with open(file_path, encoding=encoding, errors="strict") as f:
                text_content = f.read()

        except UnicodeDecodeError as e:
            # Try with error handling
            warnings.append(
                f"UnicodeDecodeError with {encoding}: {e}. "
                f"Falling back to 'replace' mode."
            )

            with open(file_path, encoding=encoding, errors="replace") as f:
                text_content = f.read()

        except LookupError as e:
            raise ValueError(f"Unknown encoding: {encoding}") from e

        # Calculate some basic statistics
        num_lines = text_content.count("\n") + 1
        num_chars = len(text_content)

        result = ParseResult(
            intermediate=text_content,
            hypothesis=hypothesis,
            warnings=warnings,
            cells=0,  # Not applicable at this level
            metadata={
                "file_size": file_path.stat().st_size,
                "num_lines": num_lines,
                "num_chars": num_chars,
                "encoding": encoding,
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
            'encoding=utf-8, language=English'
        """
        encoding = hypothesis.parameters.get("encoding", "unknown")
        language = hypothesis.parameters.get("language", "unknown")
        return f"encoding={encoding}, language={language}"
