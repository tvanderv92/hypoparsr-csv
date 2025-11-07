"""Parsing plugins for hypoparsr pipeline."""

from hypoparsr.plugins.base import ParsingPlugin, PluginRegistry
from hypoparsr.plugins.column_classifier import ColumnClassifierPlugin
from hypoparsr.plugins.data_type import DataTypePlugin
from hypoparsr.plugins.dialect import DialectPlugin, PythonDialectDetector
from hypoparsr.plugins.encoding import EncodingPlugin
from hypoparsr.plugins.row_classifier import RowClassifierPlugin
from hypoparsr.plugins.table_area import TableAreaPlugin

__all__ = [
    # Base classes
    "ParsingPlugin",
    "PluginRegistry",
    # Implemented plugins (in pipeline order)
    "EncodingPlugin",  # Level 1
    "DialectPlugin",  # Level 2
    "TableAreaPlugin",  # Level 3
    "RowClassifierPlugin",  # Level 4
    "ColumnClassifierPlugin",  # Level 5
    "DataTypePlugin",  # Level 6
    # Utilities
    "PythonDialectDetector",
]
