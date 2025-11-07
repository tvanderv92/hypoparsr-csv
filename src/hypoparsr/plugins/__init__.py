"""Parsing plugins for hypoparsr pipeline."""

from hypoparsr.plugins.base import ParsingPlugin, PluginRegistry
from hypoparsr.plugins.dialect import DialectPlugin, PythonDialectDetector
from hypoparsr.plugins.encoding import EncodingPlugin

__all__ = [
    # Base classes
    "ParsingPlugin",
    "PluginRegistry",
    # Implemented plugins
    "EncodingPlugin",
    "DialectPlugin",
    # Utilities
    "PythonDialectDetector",
]
