"""Unit tests for hypothesis tree structure."""

import pytest

from hypoparsr.core.tree import (
    HypothesisNode,
    filter_nodes,
    get_complete_paths,
    get_leaf_nodes,
    get_tree_statistics,
    prune_tree,
    render_tree,
    traverse_tree,
)
from hypoparsr.models import Hypothesis, ParseResult


class TestHypothesisNode:
    """Tests for HypothesisNode."""

    def test_create_root(self):
        """Test creating root node."""
        root = HypothesisNode.create_root("test.csv")

        assert root.parsing_level == 0
        assert root.hypothesis is None
        assert root.confidence == 1.0
        assert root.intermediate == "test.csv"
        assert root.evaluated is True

    def test_add_hypothesis(self):
        """Test adding child hypothesis."""
        root = HypothesisNode.create_root("test.csv")

        hypothesis = Hypothesis(
            level="encoding",
            confidence=0.9,
            parameters={"encoding": "utf-8"},
        )

        child = root.add_hypothesis(level=1, hypothesis=hypothesis)

        assert child.parsing_level == 1
        assert child.hypothesis == hypothesis
        assert child.confidence == 0.9
        assert child.evaluated is False
        assert child.parent == root

    def test_update_result(self):
        """Test updating node with parse result."""
        root = HypothesisNode.create_root("test.csv")
        hypothesis = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child = root.add_hypothesis(level=1, hypothesis=hypothesis)

        result = ParseResult(
            intermediate="decoded_text",
            hypothesis=hypothesis,
            warnings=["warning1"],
            edits=2,
            moves=1,
            cells=100,
        )

        child.update_result(result)

        assert child.evaluated is True
        assert child.intermediate == "decoded_text"
        assert child.warnings == ["warning1"]
        assert child.edits == 2
        assert child.moves == 1
        assert child.cells == 100

    def test_get_path_confidence(self):
        """Test calculating cumulative path confidence."""
        root = HypothesisNode.create_root("test.csv")

        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)

        h2 = Hypothesis(level="dialect", confidence=0.8, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)

        # Root: 1.0, child1: 0.9, child2: 0.8
        # Path confidence: 1.0 * 0.9 * 0.8 = 0.72
        assert child2.get_path_confidence() == pytest.approx(0.72)

    def test_get_path_hypotheses(self):
        """Test getting all hypotheses along path."""
        root = HypothesisNode.create_root("test.csv")

        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)

        h2 = Hypothesis(level="dialect", confidence=0.8, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)

        hypotheses = child2.get_path_hypotheses()

        assert len(hypotheses) == 2
        assert hypotheses[0] == h1
        assert hypotheses[1] == h2

    def test_is_leaf(self):
        """Test checking if node is leaf."""
        root = HypothesisNode.create_root("test.csv")
        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child = root.add_hypothesis(level=1, hypothesis=h1)

        assert root.is_leaf() is False  # Has child
        assert child.is_leaf() is True  # No children

    def test_should_prune(self):
        """Test prune threshold check."""
        root = HypothesisNode.create_root("test.csv")
        h1 = Hypothesis(level="encoding", confidence=0.05, parameters={})
        child = root.add_hypothesis(level=1, hypothesis=h1)

        assert child.should_prune(threshold=0.1) is True
        assert child.should_prune(threshold=0.01) is False


class TestTreeTraversal:
    """Tests for tree traversal functions."""

    def test_traverse_tree_preorder(self):
        """Test pre-order traversal."""
        root = HypothesisNode.create_root("test.csv")
        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)
        h2 = Hypothesis(level="dialect", confidence=0.8, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)

        nodes = list(traverse_tree(root, order="pre-order"))

        assert len(nodes) == 3
        assert nodes[0] == root
        assert nodes[1] == child1
        assert nodes[2] == child2

    def test_traverse_tree_postorder(self):
        """Test post-order traversal."""
        root = HypothesisNode.create_root("test.csv")
        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)
        h2 = Hypothesis(level="dialect", confidence=0.8, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)

        nodes = list(traverse_tree(root, order="post-order"))

        assert len(nodes) == 3
        # Post-order: children before parents
        assert nodes[0] == child2
        assert nodes[1] == child1
        assert nodes[2] == root

    def test_filter_nodes(self):
        """Test filtering nodes by predicate."""
        root = HypothesisNode.create_root("test.csv")
        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)
        h2 = Hypothesis(level="dialect", confidence=0.3, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)

        # Filter for high confidence (>0.5)
        high_conf = filter_nodes(root, lambda n: n.confidence > 0.5)

        assert len(high_conf) == 2  # root (1.0) and child1 (0.9)
        assert root in high_conf
        assert child1 in high_conf
        assert child2 not in high_conf

    def test_get_leaf_nodes(self):
        """Test getting all leaf nodes."""
        root = HypothesisNode.create_root("test.csv")
        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)
        h2 = Hypothesis(level="dialect", confidence=0.8, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)

        leaves = get_leaf_nodes(root)

        assert len(leaves) == 1
        assert leaves[0] == child2

    def test_get_complete_paths(self):
        """Test getting complete parsing paths."""
        root = HypothesisNode.create_root("test.csv")

        # Path 1: root -> child1 -> child2 (level 2)
        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)
        h2 = Hypothesis(level="dialect", confidence=0.8, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)
        child2.evaluated = True

        # Path 2: root -> child3 (level 1, incomplete)
        h3 = Hypothesis(level="encoding", confidence=0.7, parameters={})
        child3 = root.add_hypothesis(level=1, hypothesis=h3)
        child3.evaluated = True

        # Get complete paths (level 2)
        complete = get_complete_paths(root, max_level=2)

        assert len(complete) == 1
        assert complete[0] == child2

    def test_prune_tree(self):
        """Test pruning low-confidence branches."""
        root = HypothesisNode.create_root("test.csv")

        # High confidence branch
        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)

        # Low confidence branch (should be pruned)
        h2 = Hypothesis(level="encoding", confidence=0.05, parameters={})
        child2 = root.add_hypothesis(level=1, hypothesis=h2)

        # Prune with threshold 0.1
        pruned_count = prune_tree(root, threshold=0.1)

        assert pruned_count == 1
        assert len(root.children) == 1
        assert child1.parent == root
        assert child2.parent is None  # Detached


class TestTreeStatistics:
    """Tests for tree statistics."""

    def test_get_tree_statistics(self):
        """Test computing tree statistics."""
        root = HypothesisNode.create_root("test.csv")

        # Build small tree
        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)
        child1.evaluated = True

        h2 = Hypothesis(level="dialect", confidence=0.8, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)
        child2.evaluated = True

        h3 = Hypothesis(level="encoding", confidence=0.7, parameters={})
        child3 = root.add_hypothesis(level=1, hypothesis=h3)
        child3.evaluated = False

        stats = get_tree_statistics(root)

        assert stats["total_nodes"] == 4  # root + 3 children
        assert stats["leaf_nodes"] == 2  # child2 and child3
        assert stats["max_depth"] == 2
        assert stats["evaluated_nodes"] == 3  # root, child1, child2
        assert 0.0 <= stats["avg_confidence"] <= 1.0

    def test_render_tree(self):
        """Test rendering tree as ASCII."""
        root = HypothesisNode.create_root("test.csv")

        h1 = Hypothesis(level="encoding", confidence=0.9, parameters={})
        child1 = root.add_hypothesis(level=1, hypothesis=h1)

        h2 = Hypothesis(level="dialect", confidence=0.8, parameters={})
        child2 = child1.add_hypothesis(level=2, hypothesis=h2)

        tree_str = render_tree(root, max_depth=3)

        assert isinstance(tree_str, str)
        assert "root" in tree_str
        assert "encoding" in tree_str
        assert "dialect" in tree_str


class TestTreeEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_tree(self):
        """Test operations on single-node tree."""
        root = HypothesisNode.create_root("test.csv")

        assert root.is_leaf() is True
        assert root.get_path_confidence() == 1.0
        assert root.get_path_hypotheses() == []

        leaves = get_leaf_nodes(root)
        assert len(leaves) == 1
        assert leaves[0] == root

    def test_deep_tree(self):
        """Test tree with many levels."""
        root = HypothesisNode.create_root("test.csv")
        current = root

        # Create 10-level tree
        for i in range(1, 11):
            h = Hypothesis(
                level=f"level{i}",
                confidence=0.9,
                parameters={},
            )
            current = current.add_hypothesis(level=i, hypothesis=h)

        # Check depth
        stats = get_tree_statistics(root)
        assert stats["max_depth"] == 10

        # Check path
        hypotheses = current.get_path_hypotheses()
        assert len(hypotheses) == 10

    def test_wide_tree(self):
        """Test tree with many branches."""
        root = HypothesisNode.create_root("test.csv")

        # Create 20 children
        for i in range(20):
            h = Hypothesis(
                level="encoding",
                confidence=0.5 + i * 0.01,
                parameters={"index": i},
            )
            root.add_hypothesis(level=1, hypothesis=h)

        assert len(root.children) == 20

        leaves = get_leaf_nodes(root)
        assert len(leaves) == 20
