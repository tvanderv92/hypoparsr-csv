"""Performance benchmarking suite for hypoparsr.

This module provides benchmarking utilities to measure parsing performance
including speed, memory usage, and hypothesis generation efficiency.
"""

import time
from pathlib import Path
from typing import Any

import pandas as pd
import psutil

from hypoparsr import parse_file
from hypoparsr.models import ParserConfig


class PerformanceBenchmark:
    """Performance benchmarking utilities.

    Measures various performance metrics for CSV parsing including:
    - Parsing time (total, per phase)
    - Memory usage
    - Hypothesis generation count
    - Quality ranking time

    Example:
        >>> benchmark = PerformanceBenchmark()
        >>> results = benchmark.benchmark_file("data.csv")
        >>> print(f"Time: {results['total_time']:.2f}s")
    """

    def __init__(self) -> None:
        """Initialize benchmarker."""
        self.process = psutil.Process()

    def benchmark_file(
        self, file_path: str, config: ParserConfig | None = None, iterations: int = 1
    ) -> dict[str, Any]:
        """Benchmark parsing of a single file.

        Args:
            file_path: Path to CSV file.
            config: Parser configuration (optional).
            iterations: Number of iterations to average (default: 1).

        Returns:
            Dictionary with benchmark results:
            - total_time: Total parsing time (seconds)
            - peak_memory_mb: Peak memory usage (MB)
            - num_hypotheses: Number of hypotheses generated
            - file_size_bytes: Input file size
            - throughput_mb_per_sec: Parsing throughput

        Example:
            >>> results = benchmark.benchmark_file("data.csv", iterations=5)
            >>> results['total_time']
            0.45
        """
        file_size = Path(file_path).stat().st_size

        times = []
        memory_deltas = []
        num_hypotheses_list = []

        for _ in range(iterations):
            # Measure memory before
            mem_before = self.process.memory_info().rss / 1024 / 1024  # MB

            # Time the parsing
            start_time = time.perf_counter()
            result = parse_file(file_path, config=config)
            end_time = time.perf_counter()

            # Measure memory after
            mem_after = self.process.memory_info().rss / 1024 / 1024  # MB

            times.append(end_time - start_time)
            memory_deltas.append(mem_after - mem_before)
            num_hypotheses_list.append(len(result.results))

        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        avg_memory_delta = sum(memory_deltas) / len(memory_deltas)
        avg_hypotheses = sum(num_hypotheses_list) / len(num_hypotheses_list)

        # Calculate throughput (MB/sec)
        throughput = (file_size / 1024 / 1024) / avg_time if avg_time > 0 else 0

        return {
            "file": Path(file_path).name,
            "file_size_bytes": file_size,
            "total_time": avg_time,
            "min_time": min_time,
            "max_time": max_time,
            "peak_memory_mb": avg_memory_delta,
            "num_hypotheses": avg_hypotheses,
            "throughput_mb_per_sec": throughput,
            "iterations": iterations,
        }

    def benchmark_directory(
        self,
        directory: str,
        config: ParserConfig | None = None,
        max_files: int | None = None,
    ) -> pd.DataFrame:
        """Benchmark all CSV files in a directory.

        Args:
            directory: Path to directory containing CSV files.
            config: Parser configuration (optional).
            max_files: Maximum number of files to benchmark (optional).

        Returns:
            DataFrame with benchmark results for all files.

        Example:
            >>> results_df = benchmark.benchmark_directory("data/", max_files=10)
            >>> results_df.describe()
        """
        csv_files = list(Path(directory).glob("*.csv"))

        if max_files:
            csv_files = csv_files[:max_files]

        results = []

        print(f"Benchmarking {len(csv_files)} files...")

        for i, csv_file in enumerate(csv_files, 1):
            try:
                print(f"  [{i}/{len(csv_files)}] {csv_file.name}...", end=" ")

                result = self.benchmark_file(str(csv_file), config=config)
                results.append(result)

                print(f"{result['total_time']:.3f}s")

            except Exception as e:
                print(f"ERROR: {e}")
                results.append(
                    {
                        "file": csv_file.name,
                        "error": str(e),
                    }
                )

        return pd.DataFrame(results)

    def profile_phases(
        self, file_path: str, config: ParserConfig | None = None
    ) -> dict[str, float]:
        """Profile time spent in each parsing phase.

        This is a simplified profiling - for detailed profiling use cProfile.

        Args:
            file_path: Path to CSV file.
            config: Parser configuration (optional).

        Returns:
            Dictionary with timing for each phase.

        Example:
            >>> timings = benchmark.profile_phases("data.csv")
            >>> timings['total']
            0.45
        """
        # For now, just measure total time
        # In a full implementation, we'd instrument each plugin
        start_time = time.perf_counter()
        result = parse_file(file_path, config=config)
        end_time = time.perf_counter()

        total_time = end_time - start_time

        return {
            "total": total_time,
            "num_hypotheses": len(result.results),
            "best_confidence": result.best.hypothesis.confidence if result.best else 0.0,
        }


def compare_configs(
    file_path: str, configs: dict[str, ParserConfig], iterations: int = 3
) -> pd.DataFrame:
    """Compare performance across different configurations.

    Args:
        file_path: Path to CSV file.
        configs: Dictionary of config_name -> ParserConfig.
        iterations: Number of iterations per config.

    Returns:
        DataFrame comparing configurations.

    Example:
        >>> configs = {
        ...     "strict": get_config_preset("strict"),
        ...     "lenient": get_config_preset("lenient"),
        ...     "fast": get_config_preset("fast"),
        ... }
        >>> comparison = compare_configs("data.csv", configs)
        >>> comparison[['config', 'total_time', 'num_hypotheses']]
    """
    benchmark = PerformanceBenchmark()
    results = []

    for config_name, config in configs.items():
        print(f"Benchmarking '{config_name}' config...")
        result = benchmark.benchmark_file(file_path, config=config, iterations=iterations)
        result["config"] = config_name
        results.append(result)

    df = pd.DataFrame(results)

    # Reorder columns
    cols = ["config", "total_time", "num_hypotheses", "throughput_mb_per_sec", "peak_memory_mb"]
    remaining_cols = [c for c in df.columns if c not in cols]
    return df[cols + remaining_cols]


def generate_benchmark_report(
    benchmark_results: pd.DataFrame, output_file: str | None = None
) -> str:
    """Generate a human-readable benchmark report.

    Args:
        benchmark_results: DataFrame from benchmark_directory().
        output_file: Optional path to save report as text file.

    Returns:
        Report as string.

    Example:
        >>> results = benchmark.benchmark_directory("data/")
        >>> report = generate_benchmark_report(results, "benchmark_report.txt")
        >>> print(report)
    """
    lines = []
    lines.append("=" * 80)
    lines.append("HYPOPARSR PERFORMANCE BENCHMARK REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Filter out errors
    valid_results = benchmark_results[~benchmark_results.get("error", pd.Series()).notna()]

    if len(valid_results) == 0:
        lines.append("No successful benchmarks to report.")
        report = "\n".join(lines)
        if output_file:
            Path(output_file).write_text(report)
        return report

    lines.append(f"Files benchmarked: {len(valid_results)}")
    lines.append(f"Errors: {len(benchmark_results) - len(valid_results)}")
    lines.append("")

    # Summary statistics
    lines.append("TIMING STATISTICS")
    lines.append("-" * 80)
    lines.append(f"  Total time:   {valid_results['total_time'].sum():.2f}s")
    lines.append(f"  Average time: {valid_results['total_time'].mean():.3f}s per file")
    lines.append(f"  Median time:  {valid_results['total_time'].median():.3f}s per file")
    lines.append(f"  Min time:     {valid_results['total_time'].min():.3f}s")
    lines.append(f"  Max time:     {valid_results['total_time'].max():.3f}s")
    lines.append("")

    # Throughput statistics
    lines.append("THROUGHPUT STATISTICS")
    lines.append("-" * 80)
    lines.append(
        f"  Average: {valid_results['throughput_mb_per_sec'].mean():.2f} MB/s"
    )
    lines.append(
        f"  Median:  {valid_results['throughput_mb_per_sec'].median():.2f} MB/s"
    )
    lines.append("")

    # Memory statistics
    lines.append("MEMORY STATISTICS")
    lines.append("-" * 80)
    lines.append(
        f"  Average delta: {valid_results['peak_memory_mb'].mean():.2f} MB"
    )
    lines.append(
        f"  Max delta:     {valid_results['peak_memory_mb'].max():.2f} MB"
    )
    lines.append("")

    # Hypothesis statistics
    lines.append("HYPOTHESIS GENERATION")
    lines.append("-" * 80)
    lines.append(
        f"  Average hypotheses: {valid_results['num_hypotheses'].mean():.1f}"
    )
    lines.append(
        f"  Median hypotheses:  {valid_results['num_hypotheses'].median():.0f}"
    )
    lines.append(
        f"  Max hypotheses:     {valid_results['num_hypotheses'].max():.0f}"
    )
    lines.append("")

    # Slowest files
    lines.append("SLOWEST FILES (Top 10)")
    lines.append("-" * 80)
    slowest = valid_results.nlargest(10, "total_time")[["file", "total_time", "file_size_bytes"]]
    for _, row in slowest.iterrows():
        size_kb = row["file_size_bytes"] / 1024
        lines.append(f"  {row['file']:50s} {row['total_time']:6.3f}s  ({size_kb:6.1f} KB)")
    lines.append("")

    # Fastest files
    lines.append("FASTEST FILES (Top 10)")
    lines.append("-" * 80)
    fastest = valid_results.nsmallest(10, "total_time")[["file", "total_time", "file_size_bytes"]]
    for _, row in fastest.iterrows():
        size_kb = row["file_size_bytes"] / 1024
        lines.append(f"  {row['file']:50s} {row['total_time']:6.3f}s  ({size_kb:6.1f} KB)")
    lines.append("")

    lines.append("=" * 80)

    report = "\n".join(lines)

    if output_file:
        Path(output_file).write_text(report)
        print(f"Report saved to: {output_file}")

    return report
