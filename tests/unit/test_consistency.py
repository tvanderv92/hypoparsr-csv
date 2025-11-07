"""Unit tests for data consistency scoring."""

import numpy as np
import pandas as pd
import pytest

from hypoparsr.core.consistency import (
    compute_column_type_purity,
    compute_data_consistency,
    compute_row_pattern_score,
    compute_type_pattern_score,
    get_dominant_type,
)


class TestRowPatternScore:
    """Tests for row pattern consistency scoring."""

    def test_perfect_consistency(self):
        """Test row pattern score on perfectly consistent table."""
        df = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        score = compute_row_pattern_score(df)
        assert score == pytest.approx(1.0)

    def test_poor_consistency(self):
        """Test row pattern score on inconsistent table."""
        df = pd.DataFrame({0: [1, 2, 3], 1: [4, None, None], 2: [None, None, 7]})
        score = compute_row_pattern_score(df)
        assert score < 0.5

    def test_empty_dataframe(self):
        """Test row pattern score on empty DataFrame."""
        df = pd.DataFrame()
        score = compute_row_pattern_score(df)
        assert score == 0.0

    def test_single_row(self):
        """Test row pattern score on single row."""
        df = pd.DataFrame([[1, 2, 3]])
        score = compute_row_pattern_score(df)
        assert score == 1.0

    def test_all_na(self):
        """Test row pattern score when all cells are NA."""
        df = pd.DataFrame([[None, None], [None, None], [None, None]])
        score = compute_row_pattern_score(df)
        assert score == 1.0  # All rows have same length (0)

    def test_moderate_consistency(self):
        """Test row pattern score with some variation."""
        # Most rows have 3 cells, one has 2
        df = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, None], [9, 10, 11]])
        score = compute_row_pattern_score(df)
        assert 0.5 < score < 1.0


class TestTypePatternScore:
    """Tests for type pattern consistency scoring."""

    def test_high_coherence(self):
        """Test type pattern score on coherent columns."""
        df = pd.DataFrame({"age": ["25", "30", "35"], "name": ["Alice", "Bob", "Charlie"]})
        score = compute_type_pattern_score(df)
        assert score > 0.9

    def test_low_coherence(self):
        """Test type pattern score on incoherent columns (wrong delimiter)."""
        df = pd.DataFrame({"mixed": ["25,Alice", "30,Bob", "35,Charlie"]})
        score = compute_type_pattern_score(df)
        assert score < 0.5

    def test_empty_dataframe(self):
        """Test type pattern score on empty DataFrame."""
        df = pd.DataFrame()
        score = compute_type_pattern_score(df)
        assert score == 0.0

    def test_all_na(self):
        """Test type pattern score when all cells are NA."""
        df = pd.DataFrame([[None, None], [None, None]])
        score = compute_type_pattern_score(df)
        assert score == 0.0

    def test_numeric_column(self):
        """Test type pattern score with all numeric column."""
        df = pd.DataFrame({"numbers": ["123", "456", "789"]})
        score = compute_type_pattern_score(df)
        assert score == 1.0

    def test_mixed_types_column(self):
        """Test type pattern score with mixed types in one column."""
        df = pd.DataFrame({"mixed": ["123", "text", "456", "more text"]})
        score = compute_type_pattern_score(df)
        assert score == 0.5  # 50% numeric, 50% text

    def test_date_column(self):
        """Test type pattern score with date column."""
        df = pd.DataFrame({"dates": ["2023-01-01", "2023-01-02", "2023-01-03"]})
        score = compute_type_pattern_score(df)
        assert score == 1.0

    def test_logical_column(self):
        """Test type pattern score with logical/boolean column."""
        df = pd.DataFrame({"flags": ["true", "false", "true", "false"]})
        score = compute_type_pattern_score(df)
        assert score == 1.0


class TestDataConsistency:
    """Tests for overall data consistency scoring."""

    def test_default_weights(self):
        """Test data consistency with default weights (0.5, 0.5)."""
        df = pd.DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        score = compute_data_consistency(df)
        assert 0.0 <= score <= 1.0

    def test_custom_weights(self):
        """Test data consistency with custom weights."""
        df = pd.DataFrame([[1, 2, 3], [4, 5, 6]])
        score = compute_data_consistency(df, alpha=0.7, beta=0.3)
        assert 0.0 <= score <= 1.0

    def test_invalid_weights(self):
        """Test that invalid weights raise ValueError."""
        df = pd.DataFrame([[1, 2, 3]])
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            compute_data_consistency(df, alpha=0.6, beta=0.6)

    def test_perfect_consistency(self):
        """Test data consistency on perfect table."""
        df = pd.DataFrame({
            "id": ["1", "2", "3"],
            "name": ["Alice", "Bob", "Charlie"],
            "age": ["25", "30", "35"],
        })
        score = compute_data_consistency(df)
        assert score > 0.95

    def test_poor_consistency(self):
        """Test data consistency on poorly parsed table."""
        df = pd.DataFrame({
            0: ["1,Alice,25", "2,Bob", "3,Charlie,35,extra"]
        })
        score = compute_data_consistency(df)
        assert score < 0.5


class TestColumnTypePurity:
    """Tests for single column type purity."""

    def test_pure_numeric(self):
        """Test type purity on pure numeric column."""
        df = pd.DataFrame({"col": ["1", "2", "3", "4"]})
        purity = compute_column_type_purity(df, "col")
        assert purity == 1.0

    def test_mixed_types(self):
        """Test type purity on mixed type column."""
        df = pd.DataFrame({"col": ["1", "2", "3", "text"]})
        purity = compute_column_type_purity(df, "col")
        assert purity == 0.75  # 3/4 are numeric

    def test_column_not_found(self):
        """Test that invalid column name raises ValueError."""
        df = pd.DataFrame({"col": ["1", "2", "3"]})
        with pytest.raises(ValueError, match="Column 'invalid' not found"):
            compute_column_type_purity(df, "invalid")

    def test_all_na(self):
        """Test type purity on column with all NA values."""
        df = pd.DataFrame({"col": [None, None, None]})
        purity = compute_column_type_purity(df, "col")
        assert purity == 0.0

    def test_with_na_values(self):
        """Test type purity ignores NA values."""
        df = pd.DataFrame({"col": ["1", "2", None, "3", None]})
        purity = compute_column_type_purity(df, "col")
        assert purity == 1.0  # Only non-NA values are numeric


class TestDominantType:
    """Tests for dominant type detection."""

    def test_numeric_dominant(self):
        """Test dominant type with mostly numeric values."""
        df = pd.DataFrame({"col": ["1", "2", "3", "text"]})
        dominant = get_dominant_type(df, "col")
        assert dominant == "numeric"

    def test_text_dominant(self):
        """Test dominant type with mostly text values."""
        df = pd.DataFrame({"col": ["Alice", "Bob", "Charlie", "123"]})
        dominant = get_dominant_type(df, "col")
        assert dominant == "text"

    def test_date_dominant(self):
        """Test dominant type with date values."""
        df = pd.DataFrame({"col": ["2023-01-01", "2023-01-02", "2023-01-03"]})
        dominant = get_dominant_type(df, "col")
        assert dominant == "date"

    def test_logical_dominant(self):
        """Test dominant type with logical values."""
        df = pd.DataFrame({"col": ["true", "false", "yes", "no"]})
        dominant = get_dominant_type(df, "col")
        assert dominant == "logical"

    def test_empty_column(self):
        """Test dominant type on empty column."""
        df = pd.DataFrame({"col": [None, None, None]})
        dominant = get_dominant_type(df, "col")
        assert dominant == "empty"

    def test_column_not_found(self):
        """Test that invalid column name raises ValueError."""
        df = pd.DataFrame({"col": ["1", "2", "3"]})
        with pytest.raises(ValueError, match="Column 'invalid' not found"):
            get_dominant_type(df, "invalid")


class TestCellTypeDetection:
    """Tests for individual cell type detection."""

    def test_detect_numeric_integer(self):
        """Test detection of integer numeric values."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("123") == "numeric"
        assert _detect_cell_type("-456") == "numeric"
        assert _detect_cell_type("+789") == "numeric"

    def test_detect_numeric_float(self):
        """Test detection of float numeric values."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("123.45") == "numeric"
        assert _detect_cell_type("-67.89") == "numeric"
        assert _detect_cell_type("1.23e10") == "numeric"

    def test_detect_numeric_with_separators(self):
        """Test detection of numeric values with thousand separators."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("1,000") == "numeric"
        assert _detect_cell_type("1,000,000.50") == "numeric"

    def test_detect_date(self):
        """Test detection of date values."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("2023-01-15") == "date"
        assert _detect_cell_type("15-01-2023") == "date"
        assert _detect_cell_type("01/15/2023") == "date"

    def test_detect_logical(self):
        """Test detection of logical/boolean values."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("true") == "logical"
        assert _detect_cell_type("False") == "logical"
        assert _detect_cell_type("yes") == "logical"
        assert _detect_cell_type("NO") == "logical"

    def test_detect_email(self):
        """Test detection of email addresses."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("test@example.com") == "email"
        assert _detect_cell_type("user.name@domain.co.uk") == "email"

    def test_detect_url(self):
        """Test detection of URLs."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("http://example.com") == "url"
        assert _detect_cell_type("https://www.example.org/path") == "url"

    def test_detect_empty(self):
        """Test detection of empty values."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("") == "empty"
        assert _detect_cell_type("   ") == "empty"

    def test_detect_text(self):
        """Test detection of plain text values."""
        from hypoparsr.core.consistency import _detect_cell_type

        assert _detect_cell_type("Hello World") == "text"
        assert _detect_cell_type("test123") == "text"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_cell_dataframe(self):
        """Test consistency scores on single cell DataFrame."""
        df = pd.DataFrame([[1]])
        row_score = compute_row_pattern_score(df)
        type_score = compute_type_pattern_score(df)
        assert row_score == 1.0
        assert type_score == 1.0

    def test_very_large_dataframe(self):
        """Test consistency scores on large DataFrame."""
        # Create 1000x100 DataFrame
        data = np.random.randint(0, 100, size=(1000, 100))
        df = pd.DataFrame(data).astype(str)
        score = compute_data_consistency(df)
        assert 0.0 <= score <= 1.0

    def test_unicode_content(self):
        """Test consistency scores with unicode content."""
        df = pd.DataFrame({
            "text": ["Hello", "Привет", "你好", "مرحبا"],
            "numbers": ["1", "2", "3", "4"],
        })
        score = compute_type_pattern_score(df)
        assert score > 0.9  # Should recognize consistent types despite unicode

    def test_missing_values_pattern(self):
        """Test row pattern score with systematic missing values."""
        # Alternating pattern of missing values
        df = pd.DataFrame({
            0: [1, 2, 3, 4],
            1: [5, None, 7, None],
            2: [9, None, 11, None],
        })
        score = compute_row_pattern_score(df)
        # Should detect two patterns: rows with 3 cells and rows with 2 cells
        assert 0.3 < score < 0.9


class TestIntegration:
    """Integration tests with realistic CSV parsing scenarios."""

    def test_correct_dialect_high_score(self):
        """Test that correctly parsed CSV has high consistency."""
        # Simulate correctly parsed CSV
        df = pd.DataFrame({
            "id": ["1", "2", "3", "4"],
            "name": ["Alice", "Bob", "Charlie", "David"],
            "age": ["25", "30", "35", "40"],
            "email": ["alice@example.com", "bob@example.com", "charlie@example.com", "david@example.com"],
        })
        score = compute_data_consistency(df)
        assert score > 0.95

    def test_wrong_delimiter_low_score(self):
        """Test that incorrectly parsed CSV has low consistency."""
        # Simulate wrong delimiter: comma-separated data parsed as single column
        df = pd.DataFrame({
            0: ["1,Alice,25,alice@example.com", "2,Bob,30,bob@example.com", "3,Charlie,35,charlie@example.com"]
        })
        score = compute_data_consistency(df)
        assert score < 0.5

    def test_messy_csv_moderate_score(self):
        """Test consistency on messy but parseable CSV."""
        # Simulate CSV with some irregularities
        df = pd.DataFrame({
            "id": ["1", "2", "3", None],
            "value": ["100", "200", "text", "400"],
            "flag": ["yes", "no", "yes", "no"],
        })
        score = compute_data_consistency(df)
        assert 0.4 < score < 0.9
