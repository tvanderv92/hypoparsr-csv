"""Advanced usage examples for hypoparsr.

This script demonstrates advanced features including custom configurations,
quality metrics, and detailed inspection of parsing results.
"""

from hypoparsr import parse_file, ParserConfig

# Example 1: Custom configuration
print("=== Example 1: Custom configuration ===")
config = ParserConfig(
    max_hypotheses=5,  # Limit number of hypotheses
    conservative_casting=True,  # Be conservative with type casting
    only_one_table=True,  # Expect only one table
    min_confidence=0.6,  # Minimum confidence threshold
)

result = parse_file("../tests/data/original/33aba867-77a6-4cf9-8b8a-11980b7edce8.csv", config=config)
print(f"Generated {len(result.results)} hypotheses with custom config")
print(f"Best confidence: {result.best.hypothesis.confidence:.2f}")

# Example 2: Inspect quality metrics
print("\n\n=== Example 2: Quality metrics ===")
summary = result.summary()
print(f"Data consistency score: {summary['data_consistency']:.3f}")
print(f"Number of warnings: {len(summary['warnings'])}")

if summary['warnings']:
    print("Warnings:")
    for warning in summary['warnings']:
        print(f"  - {warning}")

# Show detailed quality report
print("\nDetailed quality report:")
quality_report = result.show_alternatives(n=5)
if not quality_report.empty:
    print(quality_report[['rank', 'confidence', 'typed_cells', 'warnings', 'data_consistency']])

# Example 3: Inspect parsing metadata
print("\n\n=== Example 3: Parsing metadata ===")
if result.best:
    metadata = result.best.metadata
    print("Detected table structure:")
    print(f"  Original shape: {metadata.get('original_shape', 'N/A')}")
    print(f"  Extracted shape: {metadata.get('extracted_shape', 'N/A')}")

    # Row functions
    row_functions = metadata.get('row_functions', [])
    if row_functions:
        row_counts = {}
        for rf in row_functions:
            row_counts[rf] = row_counts.get(rf, 0) + 1
        print(f"\n  Row classifications: {row_counts}")

    # Column functions
    col_functions = metadata.get('column_functions', [])
    if col_functions:
        col_counts = {}
        for cf in col_functions:
            col_counts[cf] = col_counts.get(cf, 0) + 1
        print(f"  Column classifications: {col_counts}")

# Example 4: Handle parsing of different file types
print("\n\n=== Example 4: Parse multiple files ===")
import glob

csv_files = glob.glob("../tests/data/original/*.csv")[:3]
for csv_file in csv_files:
    try:
        result = parse_file(csv_file, preset="fast")
        df = result.to_dataframe()
        filename = csv_file.split("/")[-1]
        print(f"{filename}: shape={df.shape}, confidence={result.best.hypothesis.confidence:.2f}")
    except Exception as e:
        print(f"{csv_file}: Error - {e}")

# Example 5: Quality-based filtering
print("\n\n=== Example 5: Filter by quality ===")
result = parse_file("../tests/data/original/8a0ffcfc-2a12-4d8d-963a-d237e19ea506.csv")

high_quality_results = [
    r for r in result.results if r.hypothesis.confidence > 0.8
]
print(f"Results with confidence > 0.8: {len(high_quality_results)} / {len(result.results)}")

if high_quality_results:
    best_high_quality = high_quality_results[0]
    print(f"Best high-quality result:")
    print(f"  Confidence: {best_high_quality.hypothesis.confidence:.2f}")
    print(f"  Warnings: {len(best_high_quality.warnings)}")
    print(f"  Cells: {best_high_quality.cells}")

print("\nDone!")
