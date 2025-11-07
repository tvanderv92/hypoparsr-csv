"""Hypothesis tree structure for multi-hypothesis parsing.

This module implements the tree structure that manages the search space of
parsing hypotheses. Each node represents a hypothesis at a specific parsing
level, and children represent hypotheses at the next level.
"""

import uuid
from typing import Any, Callable, Iterator

from anytree import Node, PreOrderIter, PostOrderIter, RenderTree

from hypoparsr.models import Hypothesis, ParseResult


class HypothesisNode(Node):
    """Node in the hypothesis tree.

    Each node represents a parsing hypothesis at a specific level in the pipeline.
    The tree structure allows exploring multiple parsing paths and pruning
    low-confidence branches.

    Attributes:
        name: Unique identifier for this node.
        parsing_level: Level index in pipeline (0=root, 1=encoding, 2=dialect, etc.).
        hypothesis: The hypothesis this node represents (None for root).
        confidence: Confidence score for this hypothesis.
        intermediate: Parsed intermediate result (after applying hypothesis).
        evaluated: Whether this node has been evaluated.
        parent: Parent node in tree.
        children: Child nodes (next level hypotheses).

    Example:
        >>> root = HypothesisNode.create_root("data.csv")
        >>> child = root.add_hypothesis(
        ...     level=1,
        ...     hypothesis=Hypothesis(level="encoding", confidence=0.9, parameters={"encoding": "utf-8"}),
        ... )
        >>> child.confidence
        0.9
    """

    def __init__(
        self,
        name: str,
        parsing_level: int,
        hypothesis: Hypothesis | None = None,
        confidence: float = 1.0,
        intermediate: Any = None,
        evaluated: bool = False,
        parent: "HypothesisNode | None" = None,
        **kwargs: Any,
    ) -> None:
        """Initialize hypothesis node.

        Args:
            name: Unique identifier for this node.
            parsing_level: Level index in pipeline.
            hypothesis: Hypothesis for this node (None for root).
            confidence: Confidence score (0.0-1.0).
            intermediate: Intermediate parsing result.
            evaluated: Whether node has been evaluated.
            parent: Parent node.
            **kwargs: Additional attributes.
        """
        super().__init__(name, parent=parent)
        self.parsing_level = parsing_level
        self.hypothesis = hypothesis
        self.confidence = confidence
        self.intermediate = intermediate
        self.evaluated = evaluated

        # Store parse result metadata
        self.warnings: list[str] = kwargs.get("warnings", [])
        self.edits: int = kwargs.get("edits", 0)
        self.moves: int = kwargs.get("moves", 0)
        self.cells: int = kwargs.get("cells", 0)
        self.metadata: dict[str, Any] = kwargs.get("metadata", {})

    @classmethod
    def create_root(cls, file_path: str) -> "HypothesisNode":
        """Create root node for a file.

        Args:
            file_path: Path to CSV file being parsed.

        Returns:
            Root node with parsing_level=0.

        Example:
            >>> root = HypothesisNode.create_root("data.csv")
            >>> root.parsing_level
            0
            >>> root.intermediate
            'data.csv'
        """
        return cls(
            name=f"file:{file_path}",
            parsing_level=0,
            hypothesis=None,
            confidence=1.0,
            intermediate=file_path,
            evaluated=True,
        )

    def add_hypothesis(
        self,
        level: int,
        hypothesis: Hypothesis,
        confidence: float | None = None,
    ) -> "HypothesisNode":
        """Add child hypothesis node.

        Args:
            level: Parsing level index.
            hypothesis: Hypothesis to add.
            confidence: Override confidence (uses hypothesis.confidence if None).

        Returns:
            New child node.

        Example:
            >>> child = node.add_hypothesis(
            ...     level=1,
            ...     hypothesis=Hypothesis(level="encoding", confidence=0.9, parameters={"encoding": "utf-8"}),
            ... )
        """
        if confidence is None:
            confidence = hypothesis.confidence

        node_name = self._generate_node_name(level, hypothesis, confidence)

        child = HypothesisNode(
            name=node_name,
            parsing_level=level,
            hypothesis=hypothesis,
            confidence=confidence,
            intermediate=None,
            evaluated=False,
            parent=self,
        )

        return child

    def update_result(self, result: ParseResult) -> None:
        """Update node with parse result.

        Args:
            result: Parse result to store.

        Example:
            >>> node.update_result(result)
            >>> node.evaluated
            True
            >>> node.intermediate
            <DataFrame...>
        """
        self.evaluated = True
        self.intermediate = result.intermediate
        self.warnings = result.warnings
        self.edits = result.edits
        self.moves = result.moves
        self.cells = result.cells
        self.metadata = result.metadata

    def get_path_confidence(self) -> float:
        """Get cumulative confidence from root to this node.

        Multiplies confidence scores along the path from root to this node.

        Returns:
            Product of all ancestor confidences.

        Example:
            >>> node.get_path_confidence()
            0.81  # 0.9 * 0.9
        """
        confidence_product = 1.0
        for ancestor in self.ancestors:
            if isinstance(ancestor, HypothesisNode):
                confidence_product *= ancestor.confidence
        confidence_product *= self.confidence
        return confidence_product

    def get_path_hypotheses(self) -> list[Hypothesis]:
        """Get all hypotheses from root to this node.

        Returns:
            List of hypotheses along path (excluding root).

        Example:
            >>> hypotheses = node.get_path_hypotheses()
            >>> [h.level for h in hypotheses]
            ['encoding', 'dialect']
        """
        hypotheses = []
        for ancestor in self.ancestors:
            if isinstance(ancestor, HypothesisNode) and ancestor.hypothesis is not None:
                hypotheses.append(ancestor.hypothesis)
        if self.hypothesis is not None:
            hypotheses.append(self.hypothesis)
        return hypotheses

    def get_path_metadata(self) -> dict[str, Any]:
        """Collect metadata from all ancestors.

        Returns:
            Merged metadata dictionary.

        Example:
            >>> metadata = node.get_path_metadata()
            >>> metadata.keys()
            dict_keys(['encoding_detector', 'dialect_detector'])
        """
        merged_metadata: dict[str, Any] = {}
        for ancestor in self.ancestors:
            if isinstance(ancestor, HypothesisNode):
                merged_metadata.update(ancestor.metadata)
        merged_metadata.update(self.metadata)
        return merged_metadata

    def is_leaf(self) -> bool:
        """Check if this is a leaf node.

        Returns:
            True if node has no children.

        Example:
            >>> node.is_leaf()
            False
        """
        return len(self.children) == 0

    def should_prune(self, threshold: float) -> bool:
        """Check if node should be pruned based on confidence.

        Args:
            threshold: Minimum confidence threshold.

        Returns:
            True if confidence below threshold.

        Example:
            >>> node.confidence = 0.05
            >>> node.should_prune(threshold=0.1)
            True
        """
        return self.confidence < threshold

    @staticmethod
    def _generate_node_name(level: int, hypothesis: Hypothesis, confidence: float) -> str:
        """Generate unique node name.

        Args:
            level: Parsing level.
            hypothesis: Hypothesis.
            confidence: Confidence score.

        Returns:
            Unique node identifier.
        """
        # Create a short UUID
        short_id = str(uuid.uuid4())[:8]

        # Get a short description from hypothesis
        param_str = str(hypothesis.parameters)[:50]

        return f"{hypothesis.level}_c{confidence:.2f}_{short_id}"

    def __repr__(self) -> str:
        """String representation of node."""
        if self.hypothesis:
            return (
                f"HypothesisNode(level={self.parsing_level}, "
                f"hypothesis={self.hypothesis.level!r}, "
                f"confidence={self.confidence:.2f}, "
                f"evaluated={self.evaluated})"
            )
        return f"HypothesisNode(root, level={self.parsing_level})"


def traverse_tree(
    root: HypothesisNode, order: str = "pre-order"
) -> Iterator[HypothesisNode]:
    """Traverse hypothesis tree in specified order.

    Args:
        root: Root node to start traversal.
        order: Traversal order ("pre-order" or "post-order").

    Yields:
        Nodes in traversal order.

    Example:
        >>> for node in traverse_tree(root, order="pre-order"):
        ...     print(node.parsing_level)
        0
        1
        2
    """
    if order == "pre-order":
        for node in PreOrderIter(root):
            if isinstance(node, HypothesisNode):
                yield node
    elif order == "post-order":
        for node in PostOrderIter(root):
            if isinstance(node, HypothesisNode):
                yield node
    else:
        raise ValueError(f"Unknown traversal order: {order!r}")


def filter_nodes(
    root: HypothesisNode, predicate: Callable[[HypothesisNode], bool]
) -> list[HypothesisNode]:
    """Filter nodes matching predicate.

    Args:
        root: Root node to start search.
        predicate: Function returning True for matching nodes.

    Returns:
        List of matching nodes.

    Example:
        >>> # Find all evaluated leaf nodes
        >>> leaves = filter_nodes(root, lambda n: n.is_leaf() and n.evaluated)
        >>> len(leaves)
        5
    """
    return [node for node in PreOrderIter(root) if predicate(node)]


def get_leaf_nodes(root: HypothesisNode) -> list[HypothesisNode]:
    """Get all leaf nodes (endpoints) in tree.

    Args:
        root: Root node.

    Returns:
        List of leaf nodes.

    Example:
        >>> leaves = get_leaf_nodes(root)
        >>> all(leaf.is_leaf() for leaf in leaves)
        True
    """
    return filter_nodes(root, lambda n: n.is_leaf())


def get_complete_paths(root: HypothesisNode, max_level: int) -> list[HypothesisNode]:
    """Get leaf nodes representing complete parsing paths.

    Args:
        root: Root node.
        max_level: Maximum parsing level (e.g., 6 for data types).

    Returns:
        List of leaf nodes at max_level (complete parses).

    Example:
        >>> complete = get_complete_paths(root, max_level=6)
        >>> all(node.parsing_level == 6 for node in complete)
        True
    """
    return filter_nodes(
        root, lambda n: n.is_leaf() and n.parsing_level == max_level and n.evaluated
    )


def prune_tree(root: HypothesisNode, threshold: float) -> int:
    """Prune tree by removing low-confidence branches.

    Removes all nodes (and their descendants) with confidence below threshold.

    Args:
        root: Root node.
        threshold: Minimum confidence threshold.

    Returns:
        Number of nodes pruned.

    Example:
        >>> pruned_count = prune_tree(root, threshold=0.1)
        >>> pruned_count
        12
    """
    nodes_to_prune = filter_nodes(root, lambda n: n.should_prune(threshold) and n.parent)

    count = 0
    for node in nodes_to_prune:
        # Count this node and all descendants
        count += 1 + len(list(PreOrderIter(node))) - 1
        # Remove from tree
        node.parent = None

    return count


def render_tree(root: HypothesisNode, max_depth: int | None = None) -> str:
    """Render tree as ASCII art.

    Args:
        root: Root node.
        max_depth: Maximum depth to render (None for unlimited).

    Returns:
        ASCII tree representation.

    Example:
        >>> print(render_tree(root, max_depth=3))
        file:data.csv
        ├── encoding_c0.95_a1b2c3d4
        │   ├── dialect_c0.90_e5f6g7h8
        │   └── dialect_c0.85_i9j0k1l2
        └── encoding_c0.80_m3n4o5p6
    """
    lines = []
    for pre, _fill, node in RenderTree(root):
        if max_depth and node.depth > max_depth:
            continue

        if isinstance(node, HypothesisNode):
            if node.hypothesis:
                label = f"{node.hypothesis.level} (conf={node.confidence:.2f})"
            else:
                label = f"root: {node.intermediate}"
            lines.append(f"{pre}{label}")

    return "\n".join(lines)


def get_tree_statistics(root: HypothesisNode) -> dict[str, Any]:
    """Compute statistics about hypothesis tree.

    Args:
        root: Root node.

    Returns:
        Dictionary with tree statistics.

    Example:
        >>> stats = get_tree_statistics(root)
        >>> stats
        {
            'total_nodes': 42,
            'leaf_nodes': 12,
            'max_depth': 6,
            'evaluated_nodes': 38,
            'avg_confidence': 0.82
        }
    """
    all_nodes = list(PreOrderIter(root))
    leaf_nodes = [n for n in all_nodes if isinstance(n, HypothesisNode) and n.is_leaf()]
    evaluated_nodes = [n for n in all_nodes if isinstance(n, HypothesisNode) and n.evaluated]

    confidences = [n.confidence for n in all_nodes if isinstance(n, HypothesisNode)]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "total_nodes": len(all_nodes),
        "leaf_nodes": len(leaf_nodes),
        "max_depth": max(n.depth for n in all_nodes) if all_nodes else 0,
        "evaluated_nodes": len(evaluated_nodes),
        "avg_confidence": avg_confidence,
        "levels": {
            level: len([n for n in all_nodes if isinstance(n, HypothesisNode) and n.parsing_level == level])
            for level in range(7)
        },
    }
