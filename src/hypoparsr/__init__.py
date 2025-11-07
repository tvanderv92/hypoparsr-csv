"""
Hypoparsr: Multi-hypothesis CSV parser for messy, real-world data.

This package provides a novel approach to CSV parsing by generating multiple
parsing hypotheses and selecting the best one based on data quality metrics.
"""

from hypoparsr.api import parse_file, ParsingResult
from hypoparsr.models import Hypothesis, ParseResult, ParserConfig, QualityMetrics

__version__ = "0.1.0"
__all__ = [
    "parse_file",
    "ParsingResult",
    "Hypothesis",
    "ParseResult",
    "ParserConfig",
    "QualityMetrics",
]
