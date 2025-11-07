"""Parser orchestrator for multi-hypothesis CSV parsing.

This module implements the orchestrator that coordinates the entire parsing pipeline,
building and traversing the hypothesis tree while managing plugins.
"""

from pathlib import Path
from typing import Any

from hypoparsr.core.tree import (
    HypothesisNode,
    get_complete_paths,
    get_tree_statistics,
    prune_tree,
    traverse_tree,
)
from hypoparsr.models import Hypothesis, ParserConfig, ParseResult
from hypoparsr.plugins.base import ParsingPlugin, PluginRegistry


class ParserOrchestrator:
    """Orchestrates multi-hypothesis parsing pipeline.

    The orchestrator coordinates the parsing process by:
    1. Building a hypothesis tree using registered plugins
    2. Evaluating hypotheses at each parsing level
    3. Pruning low-confidence branches
    4. Collecting complete parsing results

    Example:
        >>> orchestrator = ParserOrchestrator()
        >>> results = orchestrator.parse_file("data.csv", config)
        >>> len(results)
        5
    """

    def __init__(self, auto_register: bool = True) -> None:
        """Initialize orchestrator with plugin registry.

        Args:
            auto_register: If True, automatically register all built-in plugins.
                          If False, plugins must be manually registered.
        """
        self.registry = PluginRegistry()
        self._stats: dict[str, Any] = {}

        if auto_register:
            self._register_default_plugins()

    def _register_default_plugins(self) -> None:
        """Register all built-in parsing plugins in pipeline order."""
        # Import here to avoid circular imports
        from hypoparsr.plugins import (
            ColumnClassifierPlugin,
            DataTypePlugin,
            DialectPlugin,
            EncodingPlugin,
            RowClassifierPlugin,
            TableAreaPlugin,
        )

        # Register in pipeline order (level 1-6)
        self.register_plugin(EncodingPlugin())  # Level 1
        self.register_plugin(DialectPlugin())  # Level 2
        self.register_plugin(TableAreaPlugin())  # Level 3
        self.register_plugin(RowClassifierPlugin())  # Level 4
        self.register_plugin(ColumnClassifierPlugin())  # Level 5
        self.register_plugin(DataTypePlugin())  # Level 6

    def register_plugin(self, plugin: ParsingPlugin) -> None:
        """Register a parsing plugin.

        Args:
            plugin: Plugin to register.

        Example:
            >>> orchestrator.register_plugin(EncodingPlugin())
        """
        self.registry.register(plugin)

    def parse_file(
        self, file_path: str, config: ParserConfig | None = None
    ) -> list[ParseResult]:
        """Parse file using multi-hypothesis approach.

        Builds hypothesis tree, evaluates all hypotheses, and returns
        complete parsing results sorted by quality.

        Args:
            file_path: Path to CSV file.
            config: Parser configuration (uses defaults if None).

        Returns:
            List of complete parse results.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If no plugins registered or parsing fails.

        Example:
            >>> results = orchestrator.parse_file("data.csv")
            >>> len(results)
            3
            >>> results[0].hypothesis.level
            'data_type'
        """
        if config is None:
            config = ParserConfig()

        # Validate file
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.stat().st_size > config.max_file_size:
            raise ValueError(
                f"File size {path.stat().st_size} exceeds limit {config.max_file_size}"
            )

        # Check plugins
        if len(self.registry) == 0:
            raise ValueError("No parsing plugins registered")

        # Build hypothesis tree
        tree = self._build_hypothesis_tree(file_path, config)

        # Collect statistics
        self._stats = get_tree_statistics(tree)

        # Extract complete results
        plugins = self.registry.get_ordered_plugins()
        max_level = len(plugins)

        complete_nodes = get_complete_paths(tree, max_level)

        if not complete_nodes:
            raise ValueError(
                f"Parsing failed: no complete paths found (max_level={max_level}, "
                f"stats={self._stats})"
            )

        # Convert nodes to ParseResults
        results = []
        for node in complete_nodes:
            # Collect hypotheses from root to leaf
            hypotheses = node.get_path_hypotheses()

            # Get final hypothesis (data type level)
            final_hypothesis = hypotheses[-1] if hypotheses else None

            # Create ParseResult
            result = ParseResult(
                intermediate=node.intermediate,
                hypothesis=final_hypothesis if final_hypothesis else Hypothesis(
                    level="unknown", confidence=0.0, parameters={}
                ),
                warnings=node.warnings,
                edits=node.edits,
                moves=node.moves,
                cells=node.cells,
                metadata={
                    "path_hypotheses": hypotheses,
                    "path_confidence": node.get_path_confidence(),
                    **node.get_path_metadata(),
                },
            )
            results.append(result)

        return results

    def _build_hypothesis_tree(
        self, file_path: str, config: ParserConfig
    ) -> HypothesisNode:
        """Build hypothesis tree by evaluating plugins at each level.

        Args:
            file_path: Path to CSV file.
            config: Parser configuration.

        Returns:
            Root node of hypothesis tree.
        """
        # Create root node
        root = HypothesisNode.create_root(file_path)

        # Get ordered plugins
        plugins = self.registry.get_ordered_plugins()

        # Generate initial hypotheses (level 1)
        if plugins:
            first_plugin = plugins[0]
            hypotheses = first_plugin.detect(root.intermediate, config)

            for hypothesis in hypotheses:
                root.add_hypothesis(
                    level=1, hypothesis=hypothesis, confidence=hypothesis.confidence
                )

        # Traverse tree and expand nodes
        for node in traverse_tree(root, order=config.traversal_order):
            # Skip root and already evaluated nodes
            if node.parsing_level == 0 or node.evaluated:
                continue

            # Check if should prune
            if node.should_prune(config.pruning_level):
                continue

            # Get plugin for this level
            plugin_index = node.parsing_level - 1
            if plugin_index >= len(plugins):
                continue

            plugin = plugins[plugin_index]

            # Parse with this node's hypothesis
            try:
                result = plugin.parse(node.parent.intermediate, node.hypothesis, config)
                node.update_result(result)
            except Exception as e:
                # Mark as evaluated but failed
                node.evaluated = True
                node.warnings.append(f"Parse error: {e}")
                continue

            # If this is not the last level, generate child hypotheses
            if plugin_index < len(plugins) - 1:
                next_plugin = plugins[plugin_index + 1]
                try:
                    child_hypotheses = next_plugin.detect(node.intermediate, config)

                    for hypothesis in child_hypotheses:
                        node.add_hypothesis(
                            level=node.parsing_level + 1,
                            hypothesis=hypothesis,
                            confidence=hypothesis.confidence,
                        )
                except Exception as e:
                    node.warnings.append(f"Detection error at next level: {e}")

        # Prune low-confidence branches
        if config.pruning_level > 0:
            pruned_count = prune_tree(root, config.pruning_level)
            if pruned_count > 0:
                root.metadata["pruned_nodes"] = pruned_count

        return root

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics from last parse operation.

        Returns:
            Dictionary with tree statistics.

        Example:
            >>> stats = orchestrator.get_statistics()
            >>> stats['total_nodes']
            42
        """
        return self._stats.copy()

    def list_plugins(self) -> list[str]:
        """List registered plugin levels.

        Returns:
            List of plugin level names.

        Example:
            >>> orchestrator.list_plugins()
            ['encoding', 'dialect', 'table_area']
        """
        return self.registry.list_levels()

    def __repr__(self) -> str:
        """String representation of orchestrator."""
        return f"ParserOrchestrator({len(self.registry)} plugins: {self.list_plugins()})"


class SimplePipelineOrchestrator:
    """Simplified orchestrator for linear (non-branching) parsing pipeline.

    This orchestrator doesn't build a full hypothesis tree. Instead, it:
    1. Runs each plugin's detect() to get hypotheses
    2. Selects the best hypothesis (highest confidence)
    3. Runs parse() with that hypothesis
    4. Passes result to next plugin

    Useful for testing or when you only want the best result at each level.

    Example:
        >>> orchestrator = SimplePipelineOrchestrator()
        >>> orchestrator.register_plugin(EncodingPlugin())
        >>> orchestrator.register_plugin(DialectPlugin())
        >>> result = orchestrator.parse_file_simple("data.csv")
        >>> result.hypothesis.level
        'dialect'
    """

    def __init__(self) -> None:
        """Initialize simple orchestrator."""
        self.registry = PluginRegistry()

    def register_plugin(self, plugin: ParsingPlugin) -> None:
        """Register a parsing plugin.

        Args:
            plugin: Plugin to register.
        """
        self.registry.register(plugin)

    def parse_file_simple(
        self, file_path: str, config: ParserConfig | None = None
    ) -> ParseResult:
        """Parse file using simple linear pipeline (best hypothesis at each level).

        Args:
            file_path: Path to CSV file.
            config: Parser configuration.

        Returns:
            Final parse result (after last plugin).

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If no plugins registered or parsing fails.

        Example:
            >>> result = orchestrator.parse_file_simple("data.csv")
            >>> isinstance(result.intermediate, pd.DataFrame)
            True
        """
        if config is None:
            config = ParserConfig()

        # Validate file
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.stat().st_size > config.max_file_size:
            raise ValueError(
                f"File size {path.stat().st_size} exceeds limit {config.max_file_size}"
            )

        # Check plugins
        if len(self.registry) == 0:
            raise ValueError("No parsing plugins registered")

        # Get ordered plugins
        plugins = self.registry.get_ordered_plugins()

        # Start with file path
        intermediate: Any = file_path
        all_hypotheses: list[Hypothesis] = []
        all_warnings: list[str] = []
        all_metadata: dict[str, Any] = {}

        # Run through pipeline
        for plugin in plugins:
            # Detect hypotheses
            hypotheses = plugin.detect(intermediate, config)

            if not hypotheses:
                raise ValueError(f"No hypotheses generated by {plugin.level_name}")

            # Select best hypothesis (highest confidence)
            best_hypothesis = max(hypotheses, key=lambda h: h.confidence)
            all_hypotheses.append(best_hypothesis)

            # Parse with best hypothesis
            result = plugin.parse(intermediate, best_hypothesis, config)

            # Accumulate warnings and metadata
            all_warnings.extend(result.warnings)
            all_metadata[plugin.level_name] = result.metadata

            # Update intermediate for next plugin
            intermediate = result.intermediate

        # Create final result
        final_result = ParseResult(
            intermediate=intermediate,
            hypothesis=all_hypotheses[-1] if all_hypotheses else Hypothesis(
                level="unknown", confidence=0.0, parameters={}
            ),
            warnings=all_warnings,
            edits=0,
            moves=0,
            cells=0,
            metadata={
                "path_hypotheses": all_hypotheses,
                "plugin_metadata": all_metadata,
            },
        )

        return final_result

    def __repr__(self) -> str:
        """String representation."""
        return f"SimplePipelineOrchestrator({len(self.registry)} plugins)"
