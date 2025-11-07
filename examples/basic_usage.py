"""Basic usage examples for hypoparsr.

This script demonstrates the simplest way to use hypoparsr to parse CSV files.
"""

from hypoparsr import parse_file

# Example 1: Parse a simple CSV file
print("=== Example 1: Basic parsing ===")
result = parse_file("../tests/data/original/8a0ffcfc-2a12-4d8d-963a-d237e19ea506.csv")

# Get the best result as a DataFrame
df = result.to_dataframe()
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print("\nFirst few rows:")
print(df.head())

# Show result summary
print("\nResult summary:")
summary = result.summary()
for key, value in summary.items():
    if key not in ["row_functions", "column_functions"]:
        print(f"  {key}: {value}")

# Example 2: View multiple parsing alternatives
print("\n\n=== Example 2: Multiple hypotheses ===")
print(f"Generated {len(result.results)} parsing hypotheses")
print("\nTop 3 alternatives:")
alternatives = result.show_alternatives(n=3)
print(alternatives)

# Example 3: Use configuration presets
print("\n\n=== Example 3: Configuration presets ===")

# Fast parsing (fewer hypotheses)
result_fast = parse_file(
    "../tests/data/original/25d30819-3484-4e38-b569-3c84210442e5.csv", preset="fast"
)
print(f"Fast mode: {len(result_fast.results)} hypotheses")
print(f"Shape: {result_fast.to_dataframe().shape}")

# Strict parsing (conservative)
result_strict = parse_file(
    "../tests/data/original/25d30819-3484-4e38-b569-3c84210442e5.csv", preset="strict"
)
print(f"Strict mode: {len(result_strict.results)} hypotheses")
print(f"Shape: {result_strict.to_dataframe().shape}")

# Example 4: Get alternative parsing result
print("\n\n=== Example 4: Compare alternatives ===")
if len(result.results) > 1:
    best = result.to_dataframe()
    second = result.get_alternative(1)

    print(f"Best result: shape={best.shape}, columns={len(best.columns)}")
    print(f"Second best: shape={second.shape}, columns={len(second.columns)}")

print("\nDone!")
