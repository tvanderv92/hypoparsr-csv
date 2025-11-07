# Hypoparsr Architecture Analysis & Python Modernization

## Executive Summary

**hypoparsr** is an innovative multi-hypothesis CSV parser that uses a tree-based search approach to test multiple parsing configurations and ranks them by data quality. This document analyzes the original R implementation and proposes a modern Python architecture using layered + plugin-based design patterns.

---

## 1. Original R Package Analysis

### 1.1 Purpose & Domain

**Domain**: Data ingestion, CSV parsing, data quality assessment
**Purpose**: Parse messy, real-world CSV files without manual parameter tuning
**Innovation**: Multi-hypothesis generation with quality-based ranking

**Key Differentiator**: Instead of requiring users to specify delimiters, encodings, and formats, hypoparsr generates multiple parsing hypotheses and selects the best one automatically.

### 1.2 Core Functionality

The package implements an 8-level parsing pipeline where each level generates hypotheses:

```
File → Encoding → Dialect → Table Area → Row Functions →
Column Functions → Data Types → Quality Assessment → Ranking
```

Each level:
1. **Detects** possible configurations (hypotheses)
2. **Parses** using those configurations
3. **Passes results** to the next level
4. Builds a **hypothesis tree** using data.tree

### 1.3 Design Pattern Analysis

**Current Pattern**: Procedural + Tree-based search

**Characteristics**:
- Global `parsing_hierarchy` list stores level configurations
- Each parsing step has three functions: `detect()`, `parse()`, `get_desc()`
- Tree structure (`data.tree::Node`) manages hypothesis space
- Pruning based on confidence thresholds
- Quality-based ranking at the end

**Data Flow**:
```
Raw File → Text (encoding) → DataFrame (dialect) →
Refined DataFrame (table area) → Classified Rows →
Classified Columns → Typed Data → Quality Scores → Ranked Results
```

### 1.4 Key R Dependencies

| R Package | Purpose | Lines Used |
|-----------|---------|------------|
| `data.tree` | Hypothesis tree management | Core (parser_full.R) |
| `readr` | CSV reading & encoding detection | dialect.R, encoding.R |
| `RecordLinkage` | Levenshtein distance for quality | quality_assessment.R |
| `tibble` | Modern data frames | Utilities |

### 1.5 Complexity Analysis

**Lines of Code**: ~1,442 lines across 9 files
**Cyclomatic Complexity**: Medium-High (nested loops, recursive tree traversal)
**Coupling**: Medium (global parsing_hierarchy, shared intermediate structures)
**Testability**: Low-Medium (tightly coupled, global state)

---

## 2. Architectural Challenges & Opportunities

### 2.1 Challenges in Current Design

1. **Global State**: `parsing_hierarchy` is a global list modified by `register_parsing_step()`
2. **Tight Coupling**: Parser functions directly access parent node's intermediate results
3. **Limited Extensibility**: Adding new parsing levels requires modifying core logic
4. **Type Safety**: Dynamic typing makes it hard to track intermediate data structures
5. **Testing**: Difficult to unit test individual parsing levels in isolation

### 2.2 Opportunities for Improvement

1. **Plugin Architecture**: Each parsing level could be a self-contained plugin
2. **Dependency Injection**: Pass configurations explicitly rather than global state
3. **Type Hints**: Python 3.12+ type system can enforce contracts between levels
4. **Async Support**: Hypothesis evaluation could be parallelized
5. **Modern Testing**: Pytest fixtures for each parsing level

---

## 3. Recommended Python Architecture

### 3.1 Architectural Pattern: **Layered + Plugin-Based**

**Why This Pattern?**

1. **Layered**: Natural fit for the sequential parsing pipeline
2. **Plugin-Based**: Each parsing level is a self-contained, testable component
3. **Separation of Concerns**: Clear boundaries between detection, parsing, and quality assessment
4. **Extensibility**: Users can add custom parsing levels or replace existing ones
5. **Testability**: Each layer can be tested independently with mock inputs

### 3.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (Public Interface)              │
│  - parse_file()                                              │
│  - ParserConfig                                              │
│  - ParsingResult                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 Orchestration Layer                          │
│  - HypothesisTreeBuilder                                     │
│  - ParserOrchestrator                                        │
│  - QualityRanker                                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Parsing Plugins (Pipeline Stages)               │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Encoding   │→ │   Dialect    │→ │  Table Area  │      │
│  │   Detector   │  │   Detector   │  │   Detector   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                  │               │
│         ▼                 ▼                  ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │     Row      │→ │   Column     │→ │  Data Type   │      │
│  │  Classifier  │  │  Classifier  │  │   Detector   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  Each plugin implements:                                     │
│  - detect(input, config) → List[Hypothesis]                 │
│  - parse(input, hypothesis, config) → ParseResult           │
│  - describe(hypothesis) → str                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Core Domain Models                         │
│  - Hypothesis (dataclass)                                    │
│  - ParseResult (dataclass)                                   │
│  - HypothesisNode (tree node)                                │
│  - QualityMetrics (dataclass)                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Utility Layer                              │
│  - Type detection patterns                                   │
│  - String utilities                                          │
│  - Tree traversal utilities                                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 Layer Responsibilities

#### **API Layer** (`hypoparsr.api`)
- Public-facing functions and classes
- Input validation
- Configuration management
- Result formatting

#### **Orchestration Layer** (`hypoparsr.core`)
- Builds hypothesis tree
- Manages parsing pipeline execution
- Handles pruning and traversal strategies
- Aggregates quality metrics and ranks results

#### **Plugin Layer** (`hypoparsr.plugins`)
- Self-contained parsing stages
- Each plugin is independently testable
- Follows common interface (`ParsingPlugin` ABC)
- Easy to add custom plugins

#### **Domain Model Layer** (`hypoparsr.models`)
- Type-safe data structures
- Hypothesis representations
- Parsing results
- Quality metrics

#### **Utility Layer** (`hypoparsr.utils`)
- Reusable helper functions
- Pattern matching
- Data type detection
- Tree operations

---

## 4. Design Principles

### 4.1 SOLID Principles Application

**Single Responsibility**: Each parsing plugin handles one parsing level
**Open/Closed**: New plugins can be added without modifying core
**Liskov Substitution**: All plugins implement common interface
**Interface Segregation**: Plugins only implement needed methods
**Dependency Inversion**: Core depends on plugin abstractions, not implementations

### 4.2 Plugin Interface

```python
from abc import ABC, abstractmethod
from typing import List, Any
from hypoparsr.models import Hypothesis, ParseResult, ParserConfig

class ParsingPlugin(ABC):
    """Abstract base class for all parsing plugins."""

    @property
    @abstractmethod
    def level_name(self) -> str:
        """Name of this parsing level (e.g., 'encoding', 'dialect')."""
        pass

    @abstractmethod
    def detect(
        self,
        input_data: Any,
        config: ParserConfig
    ) -> List[Hypothesis]:
        """Generate parsing hypotheses for this level."""
        pass

    @abstractmethod
    def parse(
        self,
        input_data: Any,
        hypothesis: Hypothesis,
        config: ParserConfig
    ) -> ParseResult:
        """Apply hypothesis to parse the input data."""
        pass

    @abstractmethod
    def describe(self, hypothesis: Hypothesis) -> str:
        """Generate human-readable description of hypothesis."""
        pass
```

### 4.3 Type Safety

All data structures use **dataclasses** with full type hints:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd

@dataclass
class Hypothesis:
    """Represents a parsing hypothesis at a specific level."""
    level: str
    confidence: float
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ParseResult:
    """Result of applying a hypothesis to input data."""
    intermediate: pd.DataFrame | str | bytes
    hypothesis: Hypothesis
    warnings: List[str] = field(default_factory=list)
    edits: int = 0
    moves: int = 0
    cells: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class QualityMetrics:
    """Metrics for ranking parsing results."""
    warnings: int
    edits: int
    moves: int
    confidence: float
    total_cells: int
    typed_cells: int
    empty_headers: int
    empty_cells: int
    non_latin_chars: int
    row_col_ratio: float
```

---

## 5. Key Improvements Over R Version

### 5.1 Modularity
- **R**: Global `parsing_hierarchy` list with function registration
- **Python**: Plugin architecture with dependency injection

### 5.2 Type Safety
- **R**: Dynamic typing with runtime type checking
- **Python**: Full type hints with mypy validation

### 5.3 Testability
- **R**: Coupled functions, global state
- **Python**: Injectable plugins, isolated unit tests

### 5.4 Async Support
- **R**: Sequential hypothesis evaluation
- **Python**: Potential for `asyncio` parallelization

### 5.5 Modern Tooling
- **R**: devtools, testthat
- **Python**: uv, ruff, black, mypy, pytest

### 5.6 Documentation
- **R**: Roxygen comments
- **Python**: Type hints + docstrings + mkdocs

---

## 6. Technology Stack

### 6.1 Core Libraries

| R Package | Python Equivalent | Justification |
|-----------|-------------------|---------------|
| `readr` | `chardet` + `pandas` | Encoding detection + CSV parsing |
| `data.tree` | `anytree` | Tree structure for hypothesis management |
| `RecordLinkage` | `python-Levenshtein` | String distance for quality assessment |
| `tibble` | `pandas.DataFrame` | Tabular data structure |

### 6.2 Development Tools

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "pandas>=2.2.0",
    "polars>=0.20.0",  # Optional: faster alternative to pandas
    "chardet>=5.2.0",
    "anytree>=2.12.0",
    "python-Levenshtein>=0.25.0",
    "pydantic>=2.6.0",  # For config validation
    "rich>=13.7.0",     # For beautiful CLI output
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.8.0",
    "ruff>=0.2.0",
    "black>=24.1.0",
]
docs = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.5.0",
    "mkdocstrings[python]>=0.24.0",
]
```

### 6.3 Quality Tools

- **Linting**: `ruff` (replaces flake8, isort, pylint)
- **Formatting**: `black` (opinionated formatter)
- **Type Checking**: `mypy --strict`
- **Testing**: `pytest` with coverage reporting
- **Benchmarking**: `pytest-benchmark` for performance testing

---

## 7. Performance Considerations

### 7.1 Bottlenecks in R Version

1. **Sequential Evaluation**: Hypotheses evaluated one at a time
2. **String Operations**: Regex matching on large files
3. **Tree Traversal**: Recursive tree operations

### 7.2 Python Optimizations

1. **Parallel Hypothesis Evaluation**: Use `asyncio` or `multiprocessing`
2. **Compiled Regex**: Pre-compile patterns at module level
3. **NumPy Vectorization**: For type detection and data validation
4. **Polars Alternative**: Offer Polars backend for large files (lazy evaluation)

### 7.3 Benchmarking Strategy

- Compare parsing time R vs Python on test suite (65 files)
- Measure memory usage for large files
- Profile with `py-spy` to identify hotspots
- Target: <2x slowdown vs R (acceptable for improved maintainability)

---

## 8. Migration Risks & Mitigation

### 8.1 Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Different parsing results | High | Comprehensive test suite with R reference data |
| Performance degradation | Medium | Benchmark early, optimize hot paths |
| Missing edge cases | Medium | Port all 65 test files, add more |
| Library incompatibilities | Low | Pin dependency versions, test matrix |

### 8.2 Validation Strategy

1. **Unit Tests**: Each plugin tested independently
2. **Integration Tests**: Full pipeline tests with known inputs
3. **Regression Tests**: Compare Python results vs R .feather reference files
4. **Property-Based Tests**: Use `hypothesis` library for edge cases

---

## 9. Extensibility Examples

### 9.1 Adding a Custom Plugin

```python
from hypoparsr.plugins.base import ParsingPlugin
from hypoparsr.models import Hypothesis, ParseResult, ParserConfig

class CustomEncodingDetector(ParsingPlugin):
    """Custom encoding detector using charset-normalizer."""

    @property
    def level_name(self) -> str:
        return "encoding"

    def detect(self, file_path: str, config: ParserConfig) -> List[Hypothesis]:
        # Custom detection logic
        pass

    def parse(self, file_path: str, hypothesis: Hypothesis, config: ParserConfig) -> ParseResult:
        # Custom parsing logic
        pass

    def describe(self, hypothesis: Hypothesis) -> str:
        return f"Encoding: {hypothesis.parameters['encoding']}"

# Register custom plugin
from hypoparsr import ParserOrchestrator

orchestrator = ParserOrchestrator()
orchestrator.register_plugin(CustomEncodingDetector(), level=1)
```

### 9.2 Custom Quality Metrics

```python
from hypoparsr.core.quality import QualityRanker

class CustomRanker(QualityRanker):
    """Custom quality ranking with domain-specific weights."""

    def score(self, result: ParseResult) -> float:
        # Custom scoring logic
        return (
            result.metrics.typed_cells * 2.0 +
            result.metrics.confidence * 1.5 -
            result.metrics.warnings * 3.0
        )
```

---

## 10. Conclusion

The recommended architecture for hypoparsr's Python migration is a **Layered + Plugin-Based** design that:

1. **Preserves** the multi-hypothesis innovation
2. **Improves** modularity, testability, and extensibility
3. **Leverages** Python's type system and modern tooling
4. **Enables** future enhancements (async, custom plugins, performance)

This architecture balances **fidelity to the original design** with **modern software engineering best practices**, resulting in a maintainable, well-tested, and extensible codebase.

---

## Next Steps

See `MIGRATION_PLAN.md` for detailed implementation strategy and timeline.
