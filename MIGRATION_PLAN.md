# Hypoparsr: R → Python Migration Plan

## Document Purpose

This document provides a comprehensive, step-by-step strategy for migrating the hypoparsr R package to a modern Python 3.12+ implementation following the architecture outlined in `ARCHITECTURE.md`.

---

## Table of Contents

1. [Migration Phases](#migration-phases)
2. [Dependency Mapping](#dependency-mapping)
3. [Module Translation Strategy](#module-translation-strategy)
4. [Testing Strategy](#testing-strategy)
5. [Implementation Timeline](#implementation-timeline)
6. [Risk Management](#risk-management)

---

## Migration Phases

### Phase 0: Preparation (Week 1)
**Goal**: Set up infrastructure and tooling

**Tasks**:
- [x] Analyze R codebase structure
- [x] Design Python architecture
- [ ] Set up Python project skeleton
- [ ] Configure development tools (ruff, mypy, pytest)
- [ ] Set up CI/CD pipeline (GitHub Actions)
- [ ] Create initial project structure

**Deliverables**:
- `pyproject.toml` with all dependencies
- `.ruff.toml`, `mypy.ini`, `.gitignore`
- Empty module structure
- CI/CD configuration

---

### Phase 1: Core Infrastructure (Week 2)
**Goal**: Build foundational abstractions

**Tasks**:
1. **Domain Models** (`hypoparsr/models/`)
   - [ ] Create `Hypothesis` dataclass
   - [ ] Create `ParseResult` dataclass
   - [ ] Create `QualityMetrics` dataclass
   - [ ] Create `ParserConfig` dataclass with Pydantic validation
   - [ ] Add comprehensive type hints

2. **Plugin Interface** (`hypoparsr/plugins/base.py`)
   - [ ] Define `ParsingPlugin` ABC
   - [ ] Implement plugin registration mechanism
   - [ ] Create plugin factory pattern

3. **Tree Structure** (`hypoparsr/core/tree.py`)
   - [ ] Implement `HypothesisNode` using anytree
   - [ ] Create tree traversal utilities
   - [ ] Implement pruning logic

4. **Orchestrator** (`hypoparsr/core/orchestrator.py`)
   - [ ] Create `ParserOrchestrator` class
   - [ ] Implement hypothesis tree building
   - [ ] Add pruning and traversal strategies

**Deliverables**:
- Fully typed core models
- Plugin interface with ABC
- Tree management utilities
- Basic orchestrator (without plugins)

**Test Coverage**: 100% for models and interfaces

---

### Phase 2: Utility Functions (Week 3)
**Goal**: Port utility and helper functions

**Tasks**:
1. **Type Detection Patterns** (`hypoparsr/utils/patterns.py`)
   - [ ] Port regex patterns from `R/misc.R`
   - [ ] Compile patterns at module level for performance
   - [ ] Create pattern matching utilities

2. **String Utilities** (`hypoparsr/utils/strings.py`)
   - [ ] Port UUID generation
   - [ ] Create description generators
   - [ ] Add string normalization functions

3. **Hypothesis Management** (`hypoparsr/utils/hypothesis.py`)
   - [ ] Port `create_hypothesis_list()`
   - [ ] Port `add_hypothesis()`
   - [ ] Port `normalize_confidence()`

**Deliverables**:
- Complete utility module
- Unit tests for all utilities
- Performance benchmarks for regex patterns

**Test Coverage**: 100%

---

### Phase 3: Parsing Plugins (Weeks 4-6)
**Goal**: Implement all parsing level plugins

#### 3.1 Encoding Plugin (Week 4, Days 1-2)
**R Source**: `R/encoding.R` (47 lines)
**Python Target**: `hypoparsr/plugins/encoding.py`

**Tasks**:
- [ ] Replace `readr::guess_encoding()` with `chardet.detect()`
- [ ] Implement confidence scoring for encodings
- [ ] Handle edge cases (binary files, mixed encodings)

**Key Translation**:
```python
# R: readr::guess_encoding(file, n_max = 1000)
# Python:
import chardet

def detect_encoding(file_path: str, sample_size: int = 1000) -> List[Hypothesis]:
    with open(file_path, 'rb') as f:
        raw_data = f.read(sample_size)
    result = chardet.detect(raw_data)
    return [Hypothesis(
        level="encoding",
        confidence=result['confidence'],
        parameters={'encoding': result['encoding']}
    )]
```

---

#### 3.2 Dialect Plugin (Week 4, Days 3-5)
**R Source**: `R/dialect.R` (103 lines)
**Python Target**: `hypoparsr/plugins/dialect.py`

**Tasks**:
- [ ] Port delimiter detection (`,`, `;`, `\t`, `|`, unicode)
- [ ] Port quote character detection
- [ ] Port escape method detection (double vs backslash)
- [ ] Replace `readr::read_delim()` with `pandas.read_csv()` or custom CSV parser

**Key Translation**:
```python
# R dialect detection logic
EOLS = ["\r\n", "(?<!\r)\n", "\r(?!\n)"]
DELIMS = [",", ";", "\t", "|", "\u060c", "\u3001", "\034", "\035", "\036", "\037"]
QUOTES = ["", '"', "'", "`", "\u00b4", "\u2018", "\u2019", "\u201c", "\u201d"]

def detect_dialect(text: str, config: ParserConfig) -> List[Hypothesis]:
    hypotheses = []
    for eol in EOLS:
        lines = re.split(eol, text)
        if len(lines) > 1:
            for delim in DELIMS:
                if any(delim in line for line in lines):
                    for quote in QUOTES:
                        if quote in text:
                            # Detect escape method
                            if f"\\{quote}" in text:
                                q_method = "escape"
                            else:
                                q_method = "double"
                            hypotheses.append(Hypothesis(
                                level="dialect",
                                confidence=1.0,
                                parameters={
                                    'delimiter': delim,
                                    'quotechar': quote,
                                    'escapechar': '\\' if q_method == 'escape' else None,
                                    'doublequote': q_method == 'double',
                                    'lineterminator': eol
                                }
                            ))
    return normalize_confidence(hypotheses[:9])  # Keep top 9
```

---

#### 3.3 Table Area Plugin (Week 5, Days 1-2)
**R Source**: `R/table_area.R` (153 lines)
**Python Target**: `hypoparsr/plugins/table_area.py`

**Tasks**:
- [ ] Port density calculation algorithm
- [ ] Port table area detection (finding dense regions)
- [ ] Handle multiple tables within a file
- [ ] Implement `only_one_table` configuration option

**Complexity**: Medium (involves 2D array operations, best suited for NumPy)

---

#### 3.4 Row Classification Plugin (Week 5, Days 3-5)
**R Source**: `R/row_function.R` (264 lines)
**Python Target**: `hypoparsr/plugins/row_classifier.py`

**Tasks**:
- [ ] Port row type detection (header, data, aggregate, metadata, empty)
- [ ] Implement voting-based classification
- [ ] Handle spanning headers
- [ ] Implement row pattern recognition

**Complexity**: High (largest plugin, complex classification logic)

**Key Row Types**:
- `header`: Column headers
- `spanning_header`: Multi-level headers
- `data`: Actual data rows
- `aggregate`: Sum/average rows
- `metadata`: File metadata
- `empty`: Empty rows

---

#### 3.5 Column Classification Plugin (Week 6, Days 1-2)
**R Source**: `R/col_function.R` (166 lines)
**Python Target**: `hypoparsr/plugins/column_classifier.py`

**Tasks**:
- [ ] Port column type detection
- [ ] Handle spanning columns
- [ ] Detect aggregate columns
- [ ] Implement `remove_named_empty_cols` configuration

**Key Column Types**:
- `spanning_header`: Multi-column headers
- `spanning_data`: Multi-column data
- `aggregate`: Sum/average columns
- `metadata`: Metadata columns
- `empty`: Empty columns
- `data`: Regular data columns

---

#### 3.6 Data Type Plugin (Week 6, Days 3-5)
**R Source**: `R/data_type.R` (386 lines)
**Python Target**: `hypoparsr/plugins/data_type.py`

**Tasks**:
- [ ] Port numeric detection (with decimal/thousand separators)
- [ ] Port date detection (multiple formats)
- [ ] Port time detection
- [ ] Port logical/boolean detection
- [ ] Port email, URL detection
- [ ] Implement type casting with error handling
- [ ] Handle NA values (NULL, null, NA, N/A, NaN, etc.)

**Complexity**: Highest (largest module, complex regex patterns)

**Key Data Types**:
- `numeric`: Integers and floats with various formats
- `date`: Multiple date formats (DD.MM.YYYY, MM/DD/YYYY, etc.)
- `time`: Time formats (HH:MM:SS, HH:MM)
- `logical`: Boolean values (TRUE/False/true)
- `email`: Email addresses
- `url`: URLs
- `text`: Plain text
- `id`: Identifiers
- `punctuation`: Special characters

**Numeric Format Handling**:
```python
NUMERIC_SEPARATORS = [
    {"decimal": ".", "thousand": ""},
    {"decimal": ".", "thousand": ","},
    {"decimal": ".", "thousand": " "},
    {"decimal": ",", "thousand": ""},
    {"decimal": ",", "thousand": "."},
    {"decimal": ",", "thousand": " "},
]

def detect_numeric_format(column: pd.Series) -> Dict[str, str]:
    """Detect decimal and thousand separator formats."""
    for sep in NUMERIC_SEPARATORS:
        pattern = build_numeric_pattern(sep)
        matches = column.str.match(pattern)
        if matches.sum() > len(column) * 0.8:  # 80% match threshold
            return sep
    return {"decimal": ".", "thousand": ""}
```

---

### Phase 4: Quality Assessment (Week 7)
**Goal**: Implement quality ranking system

**R Source**: `R/quality_assessment.R` (64 lines)
**Python Target**: `hypoparsr/core/quality.py`

**Tasks**:
- [ ] Port quality feature extraction
- [ ] Implement weighted ranking algorithm
- [ ] Add Levenshtein distance calculation (using `python-Levenshtein`)
- [ ] Create configurable quality weights

**Quality Features**:
1. `warnings`: Number of warnings during parsing
2. `edits`: Number of edits made to data
3. `moves`: Number of cell moves
4. `confidence`: Product of all level confidences
5. `total_cells`: Total number of cells
6. `typed_cells`: Cells with detected types
7. `empty_header`: Number of empty header cells
8. `empty_cells`: Number of empty data cells
9. `non_latin_chars`: Count of non-Latin characters
10. `row_col_ratio`: Ratio of rows to columns

**Ranking Formula**:
```python
def rank_quality(
    results: List[ParseResult],
    weights: Dict[str, float]
) -> List[int]:
    """Rank parsing results by quality score."""
    scores = []
    for result in results:
        metrics = extract_features(result)
        score = sum(metrics[k] * weights[k] for k in weights)
        scores.append(score)
    return np.argsort(scores)[::-1]  # Descending order
```

---

### Phase 5: Public API (Week 8)
**Goal**: Create user-facing API

**R Source**: `R/parser_full.R` (189 lines)
**Python Target**: `hypoparsr/api.py`

**Tasks**:
- [ ] Implement `parse_file()` function
- [ ] Create `ParsingResult` class with `__repr__` and `to_dataframe()`
- [ ] Add input validation
- [ ] Implement error handling and user-friendly messages
- [ ] Create configuration presets (strict, lenient, fast)

**API Design**:
```python
from hypoparsr import parse_file

# Basic usage
result = parse_file("messy_data.csv")
df = result.to_dataframe()  # Best hypothesis

# Advanced usage
result = parse_file(
    "messy_data.csv",
    pruning_level=0.1,
    quality_weights={
        'warnings': -1,
        'typed_cells': 2,
        'confidence': 1.5,
    },
    config={
        'only_one_table': True,
        'conservative_type_casting': True,
    }
)

# Access multiple hypotheses
best_df = result.to_dataframe(rank=0)
second_best_df = result.to_dataframe(rank=1)

# Inspect quality metrics
print(result.metrics)
```

**S3 Method Equivalents**:
```python
# R: print.hypoparser_result
# Python: ParsingResult.__repr__()

# R: as.data.frame.hypoparser_result
# Python: ParsingResult.to_dataframe(rank=0)
```

---

### Phase 6: Testing & Validation (Week 9-10)
**Goal**: Ensure correctness and parity with R version

#### 6.1 Unit Tests
**Target**: 90%+ code coverage

**Test Structure**:
```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_utils.py
│   ├── test_tree.py
│   ├── test_orchestrator.py
│   └── plugins/
│       ├── test_encoding.py
│       ├── test_dialect.py
│       ├── test_table_area.py
│       ├── test_row_classifier.py
│       ├── test_column_classifier.py
│       └── test_data_type.py
├── integration/
│   ├── test_full_pipeline.py
│   └── test_api.py
└── regression/
    └── test_r_parity.py
```

**Unit Test Example**:
```python
# tests/unit/plugins/test_dialect.py
import pytest
from hypoparsr.plugins.dialect import DialectPlugin
from hypoparsr.models import Hypothesis, ParserConfig

def test_detect_comma_delimiter():
    plugin = DialectPlugin()
    text = "a,b,c\n1,2,3\n4,5,6"
    config = ParserConfig()

    hypotheses = plugin.detect(text, config)

    assert len(hypotheses) > 0
    assert any(h.parameters['delimiter'] == ',' for h in hypotheses)

def test_detect_semicolon_delimiter():
    plugin = DialectPlugin()
    text = "a;b;c\n1;2;3\n4;5;6"
    config = ParserConfig()

    hypotheses = plugin.detect(text, config)

    assert len(hypotheses) > 0
    assert any(h.parameters['delimiter'] == ';' for h in hypotheses)
```

#### 6.2 Integration Tests
**Goal**: Test full pipeline with known inputs

**Test Cases**:
1. Perfect CSV (iris dataset)
2. CSV with metadata headers
3. CSV with aggregate rows
4. CSV with spanning headers
5. CSV with mixed encodings
6. CSV with unicode delimiters

#### 6.3 Regression Tests
**Goal**: Ensure parity with R version

**Strategy**:
1. Use existing 65 test files from `tests/data/original/`
2. Load reference results from `.feather` files
3. Compare Python output vs R reference using Levenshtein distance
4. Allow tolerance for minor differences (e.g., floating point precision)

**Test Implementation**:
```python
# tests/regression/test_r_parity.py
import pytest
import pandas as pd
from pathlib import Path
from hypoparsr import parse_file

TEST_FILES = list(Path("tests/data/original").glob("*.csv"))
TOLERANCE = 0.95  # 95% similarity threshold

@pytest.mark.parametrize("csv_file", TEST_FILES)
def test_r_parity(csv_file):
    # Parse with Python
    result = parse_file(str(csv_file))
    python_df = result.to_dataframe()

    # Load R reference
    feather_file = Path("tests/data/cleaned") / f"{csv_file.stem}.feather"
    r_df = pd.read_feather(feather_file)

    # Compare structure
    assert python_df.shape == r_df.shape

    # Compare content (with tolerance)
    similarity = calculate_similarity(python_df, r_df)
    assert similarity >= TOLERANCE, f"Similarity {similarity} < {TOLERANCE}"

def calculate_similarity(df1: pd.DataFrame, df2: pd.DataFrame) -> float:
    """Calculate similarity between two DataFrames using Levenshtein distance."""
    from Levenshtein import distance

    str1 = df1.to_csv(index=False)
    str2 = df2.to_csv(index=False)

    max_len = max(len(str1), len(str2))
    lev_dist = distance(str1, str2)

    return 1 - (lev_dist / max_len)
```

#### 6.4 Property-Based Tests
**Goal**: Find edge cases automatically

**Using `hypothesis` library**:
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=10, max_size=1000))
def test_encoding_never_crashes(text):
    """Encoding detection should never crash, even on random input."""
    from hypoparsr.plugins.encoding import EncodingPlugin
    plugin = EncodingPlugin()

    # Should not raise exception
    hypotheses = plugin.detect(text, ParserConfig())
    assert isinstance(hypotheses, list)
```

---

### Phase 7: Performance Optimization (Week 11)
**Goal**: Ensure acceptable performance

**Benchmarking**:
```python
# tests/benchmark/test_performance.py
import pytest
from hypoparsr import parse_file

@pytest.mark.benchmark
def test_parse_small_file(benchmark):
    result = benchmark(parse_file, "tests/data/small.csv")
    assert result is not None

@pytest.mark.benchmark
def test_parse_large_file(benchmark):
    result = benchmark(parse_file, "tests/data/large.csv")
    assert result is not None
```

**Optimization Targets**:
1. Regex patterns: Pre-compile at module level
2. Type detection: Use NumPy vectorization
3. Tree traversal: Use iterative instead of recursive where possible
4. Hypothesis pruning: Prune aggressively to reduce search space

**Profiling**:
```bash
# Profile with py-spy
py-spy record -o profile.svg -- python -m pytest tests/benchmark/

# Profile with cProfile
python -m cProfile -o profile.stats -m pytest tests/benchmark/
python -m pstats profile.stats
```

---

### Phase 8: Documentation & Packaging (Week 12)
**Goal**: Create production-ready package

**Tasks**:
1. **User Documentation** (`docs/`)
   - [ ] Getting started guide
   - [ ] API reference
   - [ ] Advanced usage examples
   - [ ] Configuration options
   - [ ] Plugin development guide

2. **Developer Documentation**
   - [ ] Architecture overview
   - [ ] Contributing guide
   - [ ] Plugin development tutorial
   - [ ] Testing guide

3. **README.md**
   - [ ] Installation instructions
   - [ ] Quick start example
   - [ ] Comparison with R version
   - [ ] Performance benchmarks
   - [ ] Links to documentation

4. **Packaging**
   - [ ] Verify `pyproject.toml` metadata
   - [ ] Add license file
   - [ ] Create CHANGELOG.md
   - [ ] Set up GitHub releases
   - [ ] Publish to PyPI (test first, then production)

---

## Dependency Mapping

### Core Dependencies

| R Package | Purpose | Python Equivalent | Installation |
|-----------|---------|-------------------|--------------|
| `data.tree` | Tree structure for hypothesis management | `anytree` | `pip install anytree` |
| `readr` | CSV reading and encoding detection | `pandas` + `chardet` | `pip install pandas chardet` |
| `RecordLinkage` | Levenshtein distance | `python-Levenshtein` | `pip install python-Levenshtein` |
| `tibble` | Modern data frame | `pandas.DataFrame` | `pip install pandas` |
| base R | Core functionality | `typing`, `dataclasses`, `re` | Standard library |

### Optional Dependencies

| Purpose | Python Library | Use Case |
|---------|----------------|----------|
| Faster CSV parsing | `polars` | Large files with lazy evaluation |
| Better encoding detection | `charset-normalizer` | More accurate than chardet |
| Parallel processing | `joblib` or `multiprocessing` | Hypothesis evaluation |
| CLI interface | `typer` + `rich` | Beautiful command-line tool |

### Development Dependencies

| Tool | Purpose | Configuration File |
|------|---------|-------------------|
| `ruff` | Linting (replaces flake8, isort, pylint) | `.ruff.toml` |
| `black` | Code formatting | `pyproject.toml` |
| `mypy` | Type checking | `mypy.ini` or `pyproject.toml` |
| `pytest` | Testing framework | `pyproject.toml` |
| `pytest-cov` | Coverage reporting | `pyproject.toml` |
| `pytest-benchmark` | Performance testing | N/A |
| `mkdocs-material` | Documentation | `mkdocs.yml` |

---

## Module Translation Strategy

### Translation Priorities

**High Priority** (Core functionality):
1. `misc.R` → `utils/` (patterns, hypothesis management)
2. `encoding.R` → `plugins/encoding.py`
3. `dialect.R` → `plugins/dialect.py`
4. `parser_full.R` → `core/orchestrator.py` + `api.py`
5. `quality_assessment.R` → `core/quality.py`

**Medium Priority** (Complex but essential):
6. `data_type.R` → `plugins/data_type.py`
7. `row_function.R` → `plugins/row_classifier.py`
8. `col_function.R` → `plugins/column_classifier.py`

**Low Priority** (Can be deferred):
9. `table_area.R` → `plugins/table_area.py` (can start with simple heuristic)

### Translation Guidelines

1. **Preserve Logic Fidelity**: Don't change algorithms unless necessary
2. **Improve Type Safety**: Add type hints to all functions
3. **Add Docstrings**: Document all public functions
4. **Refactor Responsibly**: Only refactor after tests pass
5. **Benchmark Changes**: Measure performance impact of changes

### Common R → Python Patterns

| R Pattern | Python Equivalent | Notes |
|-----------|-------------------|-------|
| `list()` | `[]` or `{}` | Context-dependent |
| `c(1, 2, 3)` | `[1, 2, 3]` | Lists |
| `seq_along(x)` | `range(len(x))` | Iteration |
| `sapply(x, fn)` | `[fn(i) for i in x]` or `map(fn, x)` | List comprehension |
| `grepl(pattern, x)` | `re.search(pattern, x)` | Regex matching |
| `gregexpr(pattern, x)` | `re.finditer(pattern, x)` | Multiple matches |
| `data.frame()` | `pd.DataFrame()` | Tabular data |
| `is.null(x)` | `x is None` | Null checks |
| `is.na(x)` | `pd.isna(x)` | NA checks |
| `paste0(...)` | `"".join(...)` or f-strings | String concatenation |
| `tryCatch({...}, error=fn)` | `try: ... except Exception as e:` | Error handling |

---

## Testing Strategy

### Test Coverage Goals

| Component | Target Coverage | Priority |
|-----------|-----------------|----------|
| Models (`models/`) | 100% | High |
| Utilities (`utils/`) | 100% | High |
| Plugin interface (`plugins/base.py`) | 100% | High |
| Orchestrator (`core/orchestrator.py`) | 95% | High |
| Plugins (`plugins/*.py`) | 90% | Medium |
| API (`api.py`) | 95% | High |
| Quality ranking (`core/quality.py`) | 90% | Medium |

### Test Types

1. **Unit Tests**: Test individual functions in isolation
2. **Integration Tests**: Test full pipeline with mocked inputs
3. **Regression Tests**: Compare against R reference outputs
4. **Property-Based Tests**: Use `hypothesis` library for edge cases
5. **Benchmarks**: Measure performance vs R version

### Continuous Integration

**GitHub Actions Workflow**:
```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.12', '3.13']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[dev]"

      - name: Lint with ruff
        run: ruff check .

      - name: Format check with black
        run: black --check .

      - name: Type check with mypy
        run: mypy src/

      - name: Test with pytest
        run: pytest --cov=hypoparsr --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Implementation Timeline

### Detailed Schedule

| Week | Phase | Deliverables | Est. Hours |
|------|-------|--------------|------------|
| 1 | Preparation | Project skeleton, tooling setup | 20 |
| 2 | Core Infrastructure | Models, plugin interface, tree | 30 |
| 3 | Utilities | Patterns, hypothesis management | 20 |
| 4 | Plugins 1 & 2 | Encoding, Dialect | 30 |
| 5 | Plugins 3 & 4 | Table area, Row classifier | 35 |
| 6 | Plugins 5 & 6 | Column classifier, Data type | 40 |
| 7 | Quality & Orchestration | Quality ranking, orchestrator | 25 |
| 8 | Public API | parse_file(), error handling | 20 |
| 9-10 | Testing | Unit, integration, regression tests | 40 |
| 11 | Performance | Benchmarking, optimization | 20 |
| 12 | Documentation | Docs, README, packaging | 20 |
| **Total** | | | **300 hours** |

### Milestones

- **Week 4**: First working plugin (encoding + dialect)
- **Week 8**: Full pipeline working (all plugins integrated)
- **Week 10**: Passing all regression tests
- **Week 12**: Production-ready release

---

## Risk Management

### High-Risk Areas

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Data type plugin complexity | High | High | Break into sub-modules, test incrementally |
| Performance degradation | Medium | Medium | Profile early, optimize hot paths, consider Polars |
| Regression test failures | High | Medium | Start testing early, iterate on tolerance |
| Missing R edge cases | Medium | High | Port all 65 test files, add more as discovered |

### Contingency Plans

**If performance is unacceptable (<2x R speed)**:
- Use Polars instead of pandas for large files
- Parallelize hypothesis evaluation with multiprocessing
- Optimize regex patterns with compiled patterns
- Consider Cython for hot paths

**If regression tests fail consistently**:
- Adjust tolerance thresholds
- Investigate differences manually
- Fix bugs in Python implementation
- Update R reference data if R version had bugs

**If timeline slips**:
- Defer table area plugin (use simple heuristic)
- Reduce test coverage target to 80%
- Defer performance optimization to post-release
- Focus on core functionality first

---

## Success Criteria

### Functional Requirements
- [ ] All 9 R modules successfully ported
- [ ] All 6 parsing plugins working
- [ ] Full pipeline produces results
- [ ] API matches R interface (parse_file, as.data.frame)

### Quality Requirements
- [ ] 90%+ code coverage
- [ ] 100% type coverage (mypy --strict passes)
- [ ] All regression tests pass with 95%+ similarity
- [ ] Zero critical bugs

### Performance Requirements
- [ ] Parse time within 2x of R version
- [ ] Memory usage within 1.5x of R version
- [ ] Handles 400KB file size limit (same as R)

### Documentation Requirements
- [ ] Complete API documentation
- [ ] User guide with examples
- [ ] Plugin development tutorial
- [ ] Migration guide (R users → Python)

---

## Post-Migration Enhancements

### Future Improvements (Not in Scope for Initial Migration)

1. **Async Support**: Parallelize hypothesis evaluation
2. **CLI Tool**: Add command-line interface with typer + rich
3. **Web API**: REST API for parsing service
4. **GUI**: Simple GUI for interactive parsing
5. **Streaming**: Support for files >400KB with streaming
6. **Custom Plugins**: Plugin marketplace or registry
7. **Performance**: Cython optimization for hot paths
8. **Formats**: Support for Excel, JSON, XML

---

## Conclusion

This migration plan provides a structured, incremental approach to converting hypoparsr from R to Python while maintaining:
- **Functional parity** with the original
- **Improved architecture** for maintainability
- **Modern tooling** for quality assurance
- **Comprehensive testing** for confidence

By following this plan, we can deliver a production-ready Python implementation in ~12 weeks with high confidence in correctness and performance.

---

**Next Steps**: Begin Phase 0 by creating the Python project skeleton (see `pyproject.toml` template below).
