"""Unit tests for parsing plugin system."""

import pytest

from hypoparsr.models import Hypothesis, ParseResult, ParserConfig
from hypoparsr.plugins.base import ParsingPlugin, PluginRegistry


class MockPlugin(ParsingPlugin):
    """Mock plugin for testing."""

    def __init__(self, level_name: str = "mock", level_order: int = 1):
        self._level_name = level_name
        self._level_order = level_order

    @property
    def level_name(self) -> str:
        return self._level_name

    @property
    def level_order(self) -> int:
        return self._level_order

    def detect(self, input_data, config):
        return [
            Hypothesis(
                level=self.level_name,
                confidence=0.9,
                parameters={"param1": "value1"},
            ),
            Hypothesis(
                level=self.level_name,
                confidence=0.7,
                parameters={"param1": "value2"},
            ),
        ]

    def parse(self, input_data, hypothesis, config):
        return ParseResult(
            intermediate=f"parsed_{input_data}",
            hypothesis=hypothesis,
        )

    def describe(self, hypothesis):
        return f"mock: {hypothesis.parameters}"


class TestParsingPlugin:
    """Tests for ParsingPlugin ABC."""

    def test_cannot_instantiate_abc(self):
        """Test that abstract base class cannot be instantiated."""
        with pytest.raises(TypeError):
            ParsingPlugin()  # type: ignore

    def test_mock_plugin_properties(self):
        """Test mock plugin properties."""
        plugin = MockPlugin(level_name="test_level", level_order=5)
        assert plugin.level_name == "test_level"
        assert plugin.level_order == 5

    def test_detect_returns_hypotheses(self):
        """Test detect method returns list of hypotheses."""
        plugin = MockPlugin()
        config = ParserConfig()

        hypotheses = plugin.detect("input", config)

        assert isinstance(hypotheses, list)
        assert len(hypotheses) == 2
        assert all(isinstance(h, Hypothesis) for h in hypotheses)
        assert hypotheses[0].confidence == 0.9
        assert hypotheses[1].confidence == 0.7

    def test_parse_returns_result(self):
        """Test parse method returns ParseResult."""
        plugin = MockPlugin()
        config = ParserConfig()
        hypothesis = Hypothesis(
            level="mock",
            confidence=0.9,
            parameters={"param1": "value1"},
        )

        result = plugin.parse("input", hypothesis, config)

        assert isinstance(result, ParseResult)
        assert result.intermediate == "parsed_input"
        assert result.hypothesis == hypothesis

    def test_describe_returns_string(self):
        """Test describe method returns string."""
        plugin = MockPlugin()
        hypothesis = Hypothesis(
            level="mock",
            confidence=0.9,
            parameters={"param1": "value1"},
        )

        description = plugin.describe(hypothesis)

        assert isinstance(description, str)
        assert "mock" in description

    def test_validate_hypothesis_correct_level(self):
        """Test hypothesis validation accepts correct level."""
        plugin = MockPlugin(level_name="test_level")
        hypothesis = Hypothesis(
            level="test_level",
            confidence=0.9,
            parameters={},
        )

        assert plugin.validate_hypothesis(hypothesis) is True

    def test_validate_hypothesis_wrong_level(self):
        """Test hypothesis validation rejects wrong level."""
        plugin = MockPlugin(level_name="test_level")
        hypothesis = Hypothesis(
            level="wrong_level",
            confidence=0.9,
            parameters={},
        )

        assert plugin.validate_hypothesis(hypothesis) is False

    def test_plugin_repr(self):
        """Test plugin string representation."""
        plugin = MockPlugin(level_name="test_level")
        repr_str = repr(plugin)

        assert "MockPlugin" in repr_str
        assert "test_level" in repr_str


class TestPluginRegistry:
    """Tests for PluginRegistry."""

    def test_empty_registry(self):
        """Test creating empty registry."""
        registry = PluginRegistry()
        assert len(registry) == 0
        assert registry.list_levels() == []

    def test_register_plugin(self):
        """Test registering a plugin."""
        registry = PluginRegistry()
        plugin = MockPlugin(level_name="test_level")

        registry.register(plugin)

        assert len(registry) == 1
        assert registry.has_plugin("test_level")
        assert "test_level" in registry.list_levels()

    def test_register_duplicate_level_raises_error(self):
        """Test that registering duplicate level raises error."""
        registry = PluginRegistry()
        plugin1 = MockPlugin(level_name="test_level")
        plugin2 = MockPlugin(level_name="test_level")

        registry.register(plugin1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(plugin2)

    def test_get_plugin(self):
        """Test retrieving plugin by level name."""
        registry = PluginRegistry()
        plugin = MockPlugin(level_name="test_level")
        registry.register(plugin)

        retrieved = registry.get_plugin("test_level")

        assert retrieved is plugin
        assert retrieved.level_name == "test_level"

    def test_get_plugin_not_found(self):
        """Test that getting non-existent plugin raises error."""
        registry = PluginRegistry()

        with pytest.raises(KeyError, match="No plugin registered"):
            registry.get_plugin("nonexistent")

    def test_get_ordered_plugins(self):
        """Test getting plugins in order."""
        registry = PluginRegistry()

        plugin1 = MockPlugin(level_name="level1", level_order=2)
        plugin2 = MockPlugin(level_name="level2", level_order=1)
        plugin3 = MockPlugin(level_name="level3", level_order=3)

        registry.register(plugin1)
        registry.register(plugin2)
        registry.register(plugin3)

        ordered = registry.get_ordered_plugins()

        assert len(ordered) == 3
        assert ordered[0].level_name == "level2"  # order=1
        assert ordered[1].level_name == "level1"  # order=2
        assert ordered[2].level_name == "level3"  # order=3

    def test_has_plugin(self):
        """Test checking if plugin exists."""
        registry = PluginRegistry()
        plugin = MockPlugin(level_name="test_level")
        registry.register(plugin)

        assert registry.has_plugin("test_level") is True
        assert registry.has_plugin("nonexistent") is False

    def test_list_levels(self):
        """Test listing all registered levels."""
        registry = PluginRegistry()

        plugin1 = MockPlugin(level_name="level1")
        plugin2 = MockPlugin(level_name="level2")

        registry.register(plugin1)
        registry.register(plugin2)

        levels = registry.list_levels()

        assert len(levels) == 2
        assert "level1" in levels
        assert "level2" in levels

    def test_registry_repr(self):
        """Test registry string representation."""
        registry = PluginRegistry()
        plugin = MockPlugin(level_name="test_level")
        registry.register(plugin)

        repr_str = repr(registry)

        assert "PluginRegistry" in repr_str
        assert "1 plugin" in repr_str
        assert "test_level" in repr_str


class TestPluginIntegration:
    """Integration tests for plugin system."""

    def test_full_plugin_workflow(self):
        """Test complete workflow: register, detect, parse."""
        registry = PluginRegistry()
        plugin = MockPlugin(level_name="test_level")
        config = ParserConfig()

        # Register plugin
        registry.register(plugin)

        # Detect hypotheses
        hypotheses = plugin.detect("test_input", config)
        assert len(hypotheses) > 0

        # Select best hypothesis
        best_hypothesis = max(hypotheses, key=lambda h: h.confidence)
        assert best_hypothesis.confidence == 0.9

        # Parse with best hypothesis
        result = plugin.parse("test_input", best_hypothesis, config)
        assert result.intermediate == "parsed_test_input"
        assert result.hypothesis == best_hypothesis

    def test_multiple_plugins_ordered(self):
        """Test multiple plugins are correctly ordered."""
        registry = PluginRegistry()

        # Register plugins in random order
        plugin3 = MockPlugin(level_name="third", level_order=3)
        plugin1 = MockPlugin(level_name="first", level_order=1)
        plugin2 = MockPlugin(level_name="second", level_order=2)

        registry.register(plugin3)
        registry.register(plugin1)
        registry.register(plugin2)

        # Get ordered plugins
        ordered = registry.get_ordered_plugins()

        # Check order
        assert [p.level_name for p in ordered] == ["first", "second", "third"]
        assert [p.level_order for p in ordered] == [1, 2, 3]
