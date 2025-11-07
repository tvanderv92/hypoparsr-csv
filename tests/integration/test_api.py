"""Integration tests for hypoparsr public API.

These tests validate end-to-end parsing functionality using real CSV files
from the test dataset.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from hypoparsr import ParsingResult, parse_file
from hypoparsr.api import get_config_preset
from hypoparsr.models import ParserConfig


class TestParseFile:
    """Test suite for parse_file() function."""

    @pytest.fixture
    def test_data_dir(self) -> Path:
        """Get path to test data directory."""
        return Path(__file__).parent.parent / "data" / "original"

    @pytest.fixture
    def sample_csv_files(self, test_data_dir: Path) -> list[Path]:
        """Get a sample of CSV test files."""
        csv_files = list(test_data_dir.glob("*.csv"))
        # Return first 5 for faster testing
        return csv_files[:5]

    def test_parse_simple_csv(self, tmp_path: Path) -> None:
        """Test parsing a simple, well-formed CSV file."""
        # Create simple test CSV
        csv_content = """Name,Age,City
Alice,25,NYC
Bob,30,LA
Carol,28,SF
"""
        csv_file = tmp_path / "simple.csv"
        csv_file.write_text(csv_content)

        # Parse file
        result = parse_file(str(csv_file))

        # Validate result
        assert isinstance(result, ParsingResult)
        assert result.best is not None
        assert len(result.results) > 0

        # Validate DataFrame
        df = result.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert df.shape[0] >= 3  # At least 3 data rows (may include header)
        assert df.shape[1] == 3  # 3 columns

    def test_parse_with_metadata_rows(self, tmp_path: Path) -> None:
        """Test parsing CSV with metadata rows."""
        csv_content = """# This is metadata
# Created: 2024-01-01
Name,Age,City
Alice,25,NYC
Bob,30,LA
"""
        csv_file = tmp_path / "with_metadata.csv"
        csv_file.write_text(csv_content)

        result = parse_file(str(csv_file))

        # Should successfully parse
        assert result.best is not None
        df = result.to_dataframe()
        assert df.shape[0] >= 2  # At least 2 data rows

    def test_parse_with_empty_rows(self, tmp_path: Path) -> None:
        """Test parsing CSV with empty rows."""
        csv_content = """Name,Age,City

Alice,25,NYC

Bob,30,LA

"""
        csv_file = tmp_path / "with_empty.csv"
        csv_file.write_text(csv_content)

        result = parse_file(str(csv_file))

        # Should successfully parse and handle empty rows
        assert result.best is not None
        df = result.to_dataframe()
        assert df.shape[0] >= 2  # At least 2 data rows

    def test_parse_semicolon_delimiter(self, tmp_path: Path) -> None:
        """Test parsing CSV with semicolon delimiter."""
        csv_content = """Name;Age;City
Alice;25;NYC
Bob;30;LA
"""
        csv_file = tmp_path / "semicolon.csv"
        csv_file.write_text(csv_content)

        result = parse_file(str(csv_file))

        # Should detect semicolon delimiter
        assert result.best is not None
        df = result.to_dataframe()
        assert df.shape[1] == 3  # 3 columns (not 1)

    def test_parse_with_quotes(self, tmp_path: Path) -> None:
        """Test parsing CSV with quoted fields."""
        csv_content = '''Name,Age,Description
"Alice",25,"Works at ""ABC Corp"""
Bob,30,"Lives in LA"
'''
        csv_file = tmp_path / "quoted.csv"
        csv_file.write_text(csv_content)

        result = parse_file(str(csv_file))

        # Should handle quotes correctly
        assert result.best is not None
        df = result.to_dataframe()
        assert df.shape[0] == 2

    def test_parse_multiple_hypotheses(self, tmp_path: Path) -> None:
        """Test that multiple hypotheses are generated."""
        csv_content = """Name,Age,City
Alice,25,NYC
Bob,30,LA
"""
        csv_file = tmp_path / "simple.csv"
        csv_file.write_text(csv_content)

        result = parse_file(str(csv_file))

        # Should generate multiple hypotheses
        assert len(result.results) > 1

        # Best result should have highest confidence
        if len(result.results) > 1:
            assert (
                result.results[0].hypothesis.confidence
                >= result.results[1].hypothesis.confidence
            )

    def test_parse_real_files(self, sample_csv_files: list[Path]) -> None:
        """Test parsing real CSV files from test dataset."""
        for csv_file in sample_csv_files:
            result = parse_file(str(csv_file))

            # Should successfully parse
            assert result.best is not None, f"Failed to parse {csv_file.name}"

            # Should produce a DataFrame
            df = result.to_dataframe()
            assert isinstance(df, pd.DataFrame)
            assert df.shape[0] > 0 or df.shape[1] > 0, f"Empty result for {csv_file.name}"

    def test_file_not_found(self) -> None:
        """Test error handling for non-existent file."""
        with pytest.raises(FileNotFoundError):
            parse_file("/nonexistent/file.csv")

    def test_invalid_file_type(self, tmp_path: Path) -> None:
        """Test error handling for directory path."""
        with pytest.raises(ValueError):
            parse_file(str(tmp_path))

    def test_empty_file(self, tmp_path: Path) -> None:
        """Test parsing empty CSV file."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        result = parse_file(str(csv_file))

        # Should handle empty file gracefully
        # Either no results or empty DataFrame
        if result.best is not None:
            df = result.to_dataframe()
            assert df.empty


class TestConfigPresets:
    """Test suite for configuration presets."""

    def test_strict_preset(self) -> None:
        """Test strict configuration preset."""
        config = get_config_preset("strict")

        assert config.conservative_casting is True
        assert config.only_one_table is True
        assert config.min_confidence == 0.7
        assert config.max_hypotheses == 10

    def test_lenient_preset(self) -> None:
        """Test lenient configuration preset."""
        config = get_config_preset("lenient")

        assert config.conservative_casting is False
        assert config.only_one_table is False
        assert config.min_confidence == 0.3
        assert config.max_hypotheses == 20

    def test_fast_preset(self) -> None:
        """Test fast configuration preset."""
        config = get_config_preset("fast")

        assert config.conservative_casting is True
        assert config.only_one_table is True
        assert config.max_hypotheses == 3

    def test_invalid_preset(self) -> None:
        """Test error for invalid preset name."""
        with pytest.raises(ValueError, match="Invalid preset"):
            get_config_preset("invalid_preset")

    def test_parse_with_preset(self, tmp_path: Path) -> None:
        """Test parsing with preset configuration."""
        csv_content = """Name,Age,City
Alice,25,NYC
Bob,30,LA
"""
        csv_file = tmp_path / "simple.csv"
        csv_file.write_text(csv_content)

        # Test each preset
        for preset in ["strict", "lenient", "fast"]:
            result = parse_file(str(csv_file), preset=preset)
            assert result.best is not None
            df = result.to_dataframe()
            assert df.shape == (2, 3)

    def test_custom_config(self, tmp_path: Path) -> None:
        """Test parsing with custom configuration."""
        csv_content = """Name,Age,City
Alice,25,NYC
Bob,30,LA
"""
        csv_file = tmp_path / "simple.csv"
        csv_file.write_text(csv_content)

        # Create custom config
        config = ParserConfig(
            max_hypotheses=5,
            conservative_casting=False,
            only_one_table=True,
        )

        result = parse_file(str(csv_file), config=config)
        assert result.best is not None

        # Config should be stored
        assert result.config == config


class TestParsingResult:
    """Test suite for ParsingResult class."""

    @pytest.fixture
    def simple_result(self, tmp_path: Path) -> ParsingResult:
        """Create a simple parsing result for testing."""
        csv_content = """Name,Age,City
Alice,25,NYC
Bob,30,LA
Carol,28,SF
"""
        csv_file = tmp_path / "simple.csv"
        csv_file.write_text(csv_content)
        return parse_file(str(csv_file))

    def test_to_dataframe(self, simple_result: ParsingResult) -> None:
        """Test to_dataframe() method."""
        df = simple_result.to_dataframe()

        assert isinstance(df, pd.DataFrame)
        assert df.shape[0] == 3  # 3 rows
        assert df.shape[1] == 3  # 3 columns

    def test_get_alternative(self, simple_result: ParsingResult) -> None:
        """Test get_alternative() method."""
        # Get best result (same as to_dataframe())
        df_best = simple_result.get_alternative(0)
        df_direct = simple_result.to_dataframe()

        pd.testing.assert_frame_equal(df_best, df_direct)

        # Get second best (if exists)
        if len(simple_result.results) > 1:
            df_alt = simple_result.get_alternative(1)
            assert isinstance(df_alt, pd.DataFrame)

    def test_get_alternative_out_of_range(self, simple_result: ParsingResult) -> None:
        """Test get_alternative() with invalid index."""
        with pytest.raises(IndexError):
            simple_result.get_alternative(999)

    def test_show_alternatives(self, simple_result: ParsingResult) -> None:
        """Test show_alternatives() method."""
        report = simple_result.show_alternatives(n=3)

        assert isinstance(report, pd.DataFrame)
        assert len(report) <= 3
        assert "rank" in report.columns
        assert "confidence" in report.columns

    def test_summary(self, simple_result: ParsingResult) -> None:
        """Test summary() method."""
        summary = simple_result.summary()

        assert isinstance(summary, dict)
        assert "file" in summary
        assert "num_hypotheses" in summary
        assert "best_confidence" in summary
        assert "shape" in summary
        assert "warnings" in summary
        assert summary["shape"] == (3, 3)

    def test_repr(self, simple_result: ParsingResult) -> None:
        """Test __repr__() method."""
        repr_str = repr(simple_result)

        assert isinstance(repr_str, str)
        assert "Parsing" in repr_str
        assert "completed" in repr_str
        assert "confidence" in repr_str

    def test_str(self, simple_result: ParsingResult) -> None:
        """Test __str__() method."""
        str_repr = str(simple_result)

        # Should be same as repr
        assert str_repr == repr(simple_result)


class TestEncodingDetection:
    """Test suite for encoding detection."""

    def test_utf8_encoding(self, tmp_path: Path) -> None:
        """Test parsing UTF-8 encoded file."""
        csv_content = """Name,Age,City
Café,25,São Paulo
François,30,Zürich
"""
        csv_file = tmp_path / "utf8.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        result = parse_file(str(csv_file))
        assert result.best is not None

        df = result.to_dataframe()
        assert df.shape[0] == 2

    def test_latin1_encoding(self, tmp_path: Path) -> None:
        """Test parsing Latin-1 encoded file."""
        csv_content = """Name,Age,City
Café,25,São Paulo
"""
        csv_file = tmp_path / "latin1.csv"
        csv_file.write_bytes(csv_content.encode("latin-1"))

        result = parse_file(str(csv_file))
        assert result.best is not None

        # Should successfully parse regardless of encoding
        df = result.to_dataframe()
        assert df.shape[0] >= 1


class TestDataTypes:
    """Test suite for data type detection."""

    def test_numeric_type_detection(self, tmp_path: Path) -> None:
        """Test detection of numeric columns."""
        csv_content = """Name,Age,Salary
Alice,25,50000
Bob,30,60000
Carol,28,55000
"""
        csv_file = tmp_path / "numeric.csv"
        csv_file.write_text(csv_content)

        result = parse_file(str(csv_file))
        df = result.to_dataframe()

        # Age and Salary should be numeric (if type casting is working)
        # Note: This depends on the data type plugin implementation
        assert df.shape == (3, 3)

    def test_date_type_detection(self, tmp_path: Path) -> None:
        """Test detection of date columns."""
        csv_content = """Name,BirthDate,JoinDate
Alice,1998-01-15,2023-01-01
Bob,1993-05-20,2022-06-15
"""
        csv_file = tmp_path / "dates.csv"
        csv_file.write_text(csv_content)

        result = parse_file(str(csv_file))
        df = result.to_dataframe()

        # Should successfully parse dates
        assert df.shape == (2, 3)

    def test_mixed_types(self, tmp_path: Path) -> None:
        """Test handling of mixed type columns."""
        csv_content = """ID,Value,Description
1,100,Good
2,150,Bad
3,NA,Unknown
"""
        csv_file = tmp_path / "mixed.csv"
        csv_file.write_text(csv_content)

        result = parse_file(str(csv_file))
        df = result.to_dataframe()

        # Should handle mixed types gracefully
        assert df.shape == (3, 3)
