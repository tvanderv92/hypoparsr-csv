"""Performance benchmark tests using pytest-benchmark.

These tests measure parsing performance and can be used to track
performance regressions over time.

Run with: pytest tests/benchmark/ -v --benchmark-only
"""

from pathlib import Path

import pandas as pd
import pytest

from hypoparsr import parse_file
from hypoparsr.api import get_config_preset
from hypoparsr.utils.benchmark import PerformanceBenchmark


class TestParsingPerformance:
    """Benchmark tests for parsing performance."""

    @pytest.fixture
    def sample_csv(self, tmp_path: Path) -> Path:
        """Create a sample CSV for benchmarking."""
        csv_content = """Name,Age,City,Salary,Department
Alice,25,NYC,50000,Engineering
Bob,30,LA,60000,Sales
Carol,28,SF,55000,Engineering
Dave,35,Boston,70000,Management
Eve,27,Seattle,58000,Engineering
Frank,32,Austin,62000,Sales
Grace,29,Denver,56000,Engineering
Hank,33,Portland,64000,Sales
"""
        csv_file = tmp_path / "benchmark.csv"
        csv_file.write_text(csv_content)
        return csv_file

    @pytest.fixture
    def test_data_dir(self) -> Path:
        """Get path to test data directory."""
        return Path(__file__).parent.parent / "data" / "original"

    @pytest.fixture
    def sample_real_files(self, test_data_dir: Path) -> list[Path]:
        """Get sample of real CSV files for benchmarking."""
        csv_files = list(test_data_dir.glob("*.csv"))
        return csv_files[:5]  # First 5 files

    def test_parse_simple_csv(self, benchmark, sample_csv: Path) -> None:
        """Benchmark parsing a simple CSV file."""
        result = benchmark(parse_file, str(sample_csv))

        # Basic assertion
        assert result.best is not None

    def test_parse_with_strict_preset(self, benchmark, sample_csv: Path) -> None:
        """Benchmark parsing with strict preset."""
        config = get_config_preset("strict")
        result = benchmark(parse_file, str(sample_csv), config=config)

        assert result.best is not None

    def test_parse_with_lenient_preset(self, benchmark, sample_csv: Path) -> None:
        """Benchmark parsing with lenient preset."""
        config = get_config_preset("lenient")
        result = benchmark(parse_file, str(sample_csv), config=config)

        assert result.best is not None

    def test_parse_with_fast_preset(self, benchmark, sample_csv: Path) -> None:
        """Benchmark parsing with fast preset."""
        config = get_config_preset("fast")
        result = benchmark(parse_file, str(sample_csv), config=config)

        assert result.best is not None

    @pytest.mark.parametrize("file_index", [0, 1, 2])
    def test_parse_real_files(
        self, benchmark, sample_real_files: list[Path], file_index: int
    ) -> None:
        """Benchmark parsing real CSV files."""
        if file_index >= len(sample_real_files):
            pytest.skip(f"Not enough real files (have {len(sample_real_files)})")

        csv_file = sample_real_files[file_index]
        result = benchmark(parse_file, str(csv_file))

        # Basic assertion
        assert result.best is not None


class TestBenchmarkUtilities:
    """Test benchmark utility functions."""

    @pytest.fixture
    def benchmark_tool(self) -> PerformanceBenchmark:
        """Get benchmark tool instance."""
        return PerformanceBenchmark()

    @pytest.fixture
    def sample_csv(self, tmp_path: Path) -> Path:
        """Create a sample CSV for testing."""
        csv_content = """A,B,C
1,2,3
4,5,6
"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content)
        return csv_file

    def test_benchmark_file(
        self, benchmark_tool: PerformanceBenchmark, sample_csv: Path
    ) -> None:
        """Test benchmark_file function."""
        results = benchmark_tool.benchmark_file(str(sample_csv), iterations=2)

        # Validate results structure
        assert "file" in results
        assert "total_time" in results
        assert "peak_memory_mb" in results
        assert "num_hypotheses" in results
        assert "throughput_mb_per_sec" in results

        # Validate values
        assert results["total_time"] > 0
        assert results["num_hypotheses"] > 0
        assert results["iterations"] == 2

    def test_profile_phases(
        self, benchmark_tool: PerformanceBenchmark, sample_csv: Path
    ) -> None:
        """Test profile_phases function."""
        timings = benchmark_tool.profile_phases(str(sample_csv))

        assert "total" in timings
        assert "num_hypotheses" in timings
        assert "best_confidence" in timings

        assert timings["total"] > 0
        assert timings["num_hypotheses"] > 0

    def test_benchmark_directory(
        self, benchmark_tool: PerformanceBenchmark, tmp_path: Path
    ) -> None:
        """Test benchmark_directory function."""
        # Create multiple test files
        for i in range(3):
            csv_file = tmp_path / f"test{i}.csv"
            csv_file.write_text(f"A,B\n{i},{i+1}\n")

        results_df = benchmark_tool.benchmark_directory(str(tmp_path), max_files=3)

        # Validate results
        assert len(results_df) == 3
        assert "file" in results_df.columns
        assert "total_time" in results_df.columns


class TestConfigComparison:
    """Benchmark comparison across different configurations."""

    @pytest.fixture
    def sample_csv(self, tmp_path: Path) -> Path:
        """Create a sample CSV."""
        csv_content = """Name,Value,Category
A,100,X
B,200,Y
C,300,X
"""
        csv_file = tmp_path / "config_test.csv"
        csv_file.write_text(csv_content)
        return csv_file

    def test_compare_presets(self, sample_csv: Path) -> None:
        """Compare performance across presets."""
        from hypoparsr.utils.benchmark import compare_configs

        configs = {
            "strict": get_config_preset("strict"),
            "lenient": get_config_preset("lenient"),
            "fast": get_config_preset("fast"),
        }

        comparison_df = compare_configs(str(sample_csv), configs, iterations=2)

        # Validate results
        assert len(comparison_df) == 3
        assert "config" in comparison_df.columns
        assert "total_time" in comparison_df.columns
        assert "num_hypotheses" in comparison_df.columns

        # All configs should complete
        assert (comparison_df["total_time"] > 0).all()


@pytest.mark.slow
class TestFullBenchmarkSuite:
    """Full benchmark suite (marked as slow)."""

    @pytest.fixture
    def test_data_dir(self) -> Path:
        """Get path to test data directory."""
        return Path(__file__).parent.parent / "data" / "original"

    def test_benchmark_all_files(self, test_data_dir: Path) -> None:
        """Benchmark all CSV files and generate report.

        Run with: pytest tests/benchmark/ -m slow -v
        """
        from hypoparsr.utils.benchmark import generate_benchmark_report

        benchmark = PerformanceBenchmark()

        # Benchmark first 10 files for faster testing
        results_df = benchmark.benchmark_directory(str(test_data_dir), max_files=10)

        # Generate report
        report = generate_benchmark_report(results_df)

        # Validate report
        assert "BENCHMARK REPORT" in report
        assert "TIMING STATISTICS" in report

        # Print report
        print("\n" + report)

        # Save to file
        report_file = Path(__file__).parent.parent / "benchmark_report.txt"
        report_file.write_text(report)
        print(f"\nReport saved to: {report_file}")

        # Basic assertions
        valid_results = results_df[~results_df.get("error", pd.Series(dtype=bool)).notna()]
        if len(valid_results) > 0:
            assert valid_results["total_time"].mean() > 0
            print(f"\nAverage parsing time: {valid_results['total_time'].mean():.3f}s")
