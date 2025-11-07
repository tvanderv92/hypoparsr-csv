# Hypoparsr Examples

This directory contains example scripts demonstrating how to use hypoparsr for CSV parsing.

## Running the Examples

Make sure you have hypoparsr installed:

```bash
pip install -e .
```

Then run any example script:

```bash
cd examples
python basic_usage.py
python advanced_usage.py
```

## Available Examples

### basic_usage.py

Demonstrates the fundamental usage of hypoparsr:

- Basic parsing with `parse_file()`
- Getting results as pandas DataFrame
- Viewing multiple parsing alternatives
- Using configuration presets (fast, strict, lenient)
- Comparing alternative parsing results

**Key concepts:**
- `parse_file()` - Main entry point
- `ParsingResult.to_dataframe()` - Get best result
- `ParsingResult.show_alternatives()` - View quality rankings
- Configuration presets for quick setup

### advanced_usage.py

Shows advanced features for power users:

- Custom configuration with `ParserConfig`
- Inspecting quality metrics and data consistency
- Examining parsing metadata (row/column classifications)
- Batch processing multiple files
- Filtering results by quality thresholds

**Key concepts:**
- `ParserConfig` - Fine-grained control
- Quality metrics and data consistency scores
- Metadata inspection
- Error handling
- Quality-based filtering

## Quick Start

The simplest way to use hypoparsr:

```python
from hypoparsr import parse_file

# Parse a CSV file
result = parse_file("messy_data.csv")

# Get the best result as a DataFrame
df = result.to_dataframe()

# View summary
print(result.summary())
```

## Configuration Presets

Hypoparsr provides three built-in presets:

- **fast**: Quick parsing with fewer hypotheses (good for clean files)
- **strict**: Conservative type casting, single table only
- **lenient**: Aggressive parsing, supports multiple tables

```python
result = parse_file("data.csv", preset="fast")
```

## Custom Configuration

For fine-grained control:

```python
from hypoparsr import ParserConfig

config = ParserConfig(
    pruning_level=0.15,  # Higher pruning threshold
    conservative_type_casting=True,
    only_one_table=True,
    remove_aggregates=True,
)

result = parse_file("data.csv", config=config)
```

## Understanding Results

Each `ParsingResult` contains:

- **best**: Highest quality parsing result
- **results**: All parsing hypotheses, ranked by quality
- **config**: Configuration used
- **to_dataframe()**: Get best result as DataFrame
- **show_alternatives()**: Compare top hypotheses
- **summary()**: Get detailed summary with metrics

## Quality Metrics

Hypoparsr ranks results using 11 quality features:

1. **warnings**: Number of parsing warnings
2. **edits**: Number of data edits
3. **moves**: Number of cell moves
4. **confidence**: Hypothesis confidence
5. **total_cells**: Total number of cells
6. **typed_cells**: Cells with typed data
7. **empty_headers**: Empty column names
8. **empty_cells**: Empty data cells
9. **non_latin_chars**: Non-Latin character count
10. **row_col_ratio**: Shape ratio indicator
11. **data_consistency**: Data consistency score (research-backed)

The **data_consistency** metric is based on published research and measures
structural regularity and type purity across the table.

## Need Help?

- Check the [main README](../README_PYTHON.md) for full documentation
- Review the [architecture document](../ARCHITECTURE.md) for technical details
- See [tests](../tests/) for more usage examples
