"""Base plugin interface for hypoparsr parsing pipeline.

This module defines the abstract base class that all parsing plugins must implement.
Each parsing level (encoding, dialect, table area, etc.) implements this interface.
"""

from abc import ABC, abstractmethod
from typing import Any

from hypoparsr.models import Hypothesis, ParseResult, ParserConfig


class ParsingPlugin(ABC):
    """Abstract base class for all parsing plugins.

    Each parsing plugin represents one level in the multi-hypothesis parsing pipeline.
    Plugins generate hypotheses about how to parse the data and apply those hypotheses
    to produce intermediate results.

    The plugin interface follows a three-step pattern:
    1. detect() - Generate multiple parsing hypotheses
    2. parse() - Apply a hypothesis to produce a result
    3. describe() - Generate human-readable description

    Example:
        >>> class MyPlugin(ParsingPlugin):
        ...     @property
        ...     def level_name(self) -> str:
        ...         return "my_level"
        ...
        ...     def detect(self, input_data, config):
        ...         # Generate hypotheses
        ...         return [Hypothesis(level="my_level", confidence=0.9, parameters={})]
        ...
        ...     def parse(self, input_data, hypothesis, config):
        ...         # Apply hypothesis
        ...         return ParseResult(intermediate=result, hypothesis=hypothesis)
        ...
        ...     def describe(self, hypothesis):
        ...         return f"My hypothesis: {hypothesis.parameters}"
    """

    @property
    @abstractmethod
    def level_name(self) -> str:
        """Name of this parsing level.

        Returns:
            Level identifier (e.g., "encoding", "dialect", "data_type").

        Example:
            >>> plugin.level_name
            'encoding'
        """
        pass

    @property
    def level_order(self) -> int:
        """Order of this plugin in the parsing pipeline.

        Lower numbers are executed first. Default order:
        1. Encoding
        2. Dialect
        3. Table Area
        4. Row Functions
        5. Column Functions
        6. Data Types

        Returns:
            Pipeline order (1-6).
        """
        return 999  # Default: last

    @abstractmethod
    def detect(self, input_data: Any, config: ParserConfig) -> list[Hypothesis]:
        """Generate parsing hypotheses for this level.

        Analyzes the input data and produces multiple hypotheses about how to
        parse it at this level. Each hypothesis includes a confidence score
        and parameters specific to this parsing level.

        Args:
            input_data: Input to analyze (type depends on parsing level).
                - Encoding: file path (str)
                - Dialect: text content (str)
                - Table area: DataFrame
                - Row/column functions: DataFrame
                - Data types: DataFrame
            config: Parser configuration.

        Returns:
            List of hypotheses, sorted by confidence (highest first).

        Example:
            >>> hypotheses = plugin.detect(text, config)
            >>> len(hypotheses)
            5
            >>> hypotheses[0].confidence
            0.95
        """
        pass

    @abstractmethod
    def parse(
        self, input_data: Any, hypothesis: Hypothesis, config: ParserConfig
    ) -> ParseResult:
        """Apply hypothesis to parse the input data.

        Takes an input and a hypothesis, applies the hypothesis parameters to
        parse the data, and returns the parsed result along with metadata.

        Args:
            input_data: Input to parse (same type as detect()).
            hypothesis: Hypothesis to apply.
            config: Parser configuration.

        Returns:
            Parse result containing intermediate data and metadata.

        Raises:
            ValueError: If hypothesis is invalid or parsing fails.

        Example:
            >>> result = plugin.parse(text, hypothesis, config)
            >>> isinstance(result.intermediate, pd.DataFrame)
            True
            >>> result.warnings
            []
        """
        pass

    @abstractmethod
    def describe(self, hypothesis: Hypothesis) -> str:
        """Generate human-readable description of hypothesis.

        Creates a string description of the hypothesis for logging and debugging.
        Should be concise (1-2 lines) but informative.

        Args:
            hypothesis: Hypothesis to describe.

        Returns:
            Human-readable description.

        Example:
            >>> desc = plugin.describe(hypothesis)
            >>> desc
            'delimiter=",", quotechar="\\"", escape_method=double'
        """
        pass

    def validate_hypothesis(self, hypothesis: Hypothesis) -> bool:
        """Validate that hypothesis is compatible with this plugin.

        Checks that the hypothesis level matches this plugin and that required
        parameters are present.

        Args:
            hypothesis: Hypothesis to validate.

        Returns:
            True if valid, False otherwise.

        Example:
            >>> plugin.validate_hypothesis(hypothesis)
            True
        """
        if hypothesis.level != self.level_name:
            return False

        # Subclasses can override for additional validation
        return True

    def __repr__(self) -> str:
        """String representation of plugin."""
        return f"{self.__class__.__name__}(level={self.level_name!r})"


class PluginRegistry:
    """Registry for managing parsing plugins.

    Maintains a collection of plugins and provides methods to register,
    retrieve, and order plugins for the parsing pipeline.

    Example:
        >>> registry = PluginRegistry()
        >>> registry.register(EncodingPlugin())
        >>> registry.register(DialectPlugin())
        >>> plugins = registry.get_ordered_plugins()
        >>> [p.level_name for p in plugins]
        ['encoding', 'dialect']
    """

    def __init__(self) -> None:
        """Initialize empty plugin registry."""
        self._plugins: dict[str, ParsingPlugin] = {}

    def register(self, plugin: ParsingPlugin) -> None:
        """Register a parsing plugin.

        Args:
            plugin: Plugin to register.

        Raises:
            ValueError: If plugin with same level already registered.

        Example:
            >>> registry.register(EncodingPlugin())
        """
        if plugin.level_name in self._plugins:
            raise ValueError(
                f"Plugin for level {plugin.level_name!r} already registered: "
                f"{self._plugins[plugin.level_name]}"
            )
        self._plugins[plugin.level_name] = plugin

    def get_plugin(self, level_name: str) -> ParsingPlugin:
        """Get plugin by level name.

        Args:
            level_name: Level identifier.

        Returns:
            Plugin for the specified level.

        Raises:
            KeyError: If no plugin registered for level.

        Example:
            >>> plugin = registry.get_plugin("encoding")
            >>> plugin.level_name
            'encoding'
        """
        if level_name not in self._plugins:
            raise KeyError(
                f"No plugin registered for level {level_name!r}. "
                f"Available levels: {list(self._plugins.keys())}"
            )
        return self._plugins[level_name]

    def get_ordered_plugins(self) -> list[ParsingPlugin]:
        """Get all plugins ordered by pipeline position.

        Returns:
            List of plugins sorted by level_order.

        Example:
            >>> plugins = registry.get_ordered_plugins()
            >>> [p.level_name for p in plugins]
            ['encoding', 'dialect', 'table_area', 'row_function', 'column_function', 'data_type']
        """
        return sorted(self._plugins.values(), key=lambda p: p.level_order)

    def has_plugin(self, level_name: str) -> bool:
        """Check if plugin is registered for level.

        Args:
            level_name: Level identifier.

        Returns:
            True if plugin registered, False otherwise.

        Example:
            >>> registry.has_plugin("encoding")
            True
            >>> registry.has_plugin("unknown")
            False
        """
        return level_name in self._plugins

    def list_levels(self) -> list[str]:
        """List all registered plugin levels.

        Returns:
            List of level names.

        Example:
            >>> registry.list_levels()
            ['encoding', 'dialect', 'table_area']
        """
        return list(self._plugins.keys())

    def __len__(self) -> int:
        """Number of registered plugins."""
        return len(self._plugins)

    def __repr__(self) -> str:
        """String representation of registry."""
        levels = ", ".join(self._plugins.keys())
        return f"PluginRegistry({len(self)} plugins: {levels})"
