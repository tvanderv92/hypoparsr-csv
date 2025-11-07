"""Core components for hypoparsr parsing pipeline."""

from hypoparsr.core.consistency import (
    compute_column_type_purity,
    compute_data_consistency,
    compute_row_pattern_score,
    compute_type_pattern_score,
    get_dominant_type,
)
from hypoparsr.core.orchestrator import ParserOrchestrator, SimplePipelineOrchestrator
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

__all__ = [
    # Consistency scoring
    "compute_data_consistency",
    "compute_row_pattern_score",
    "compute_type_pattern_score",
    "compute_column_type_purity",
    "get_dominant_type",
    # Orchestrators
    "ParserOrchestrator",
    "SimplePipelineOrchestrator",
    # Tree structure
    "HypothesisNode",
    "traverse_tree",
    "filter_nodes",
    "get_leaf_nodes",
    "get_complete_paths",
    "prune_tree",
    "render_tree",
    "get_tree_statistics",
]
