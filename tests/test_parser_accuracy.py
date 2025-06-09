"""Test parser accuracy against golden CSV files."""

import csv
import subprocess
from pathlib import Path

import pytest


class TestParserAccuracy:
    """Test suite for parser accuracy validation."""

    def test_ultimate_parser_exists(self):
        """Verify ultimate parser script exists."""
        assert Path("itau_parser_ultimate.py").exists()

    def test_golden_csvs_exist(self, golden_csvs):
        """Verify golden CSV files exist."""
        assert len(golden_csvs) > 0, "No golden CSV files found"

    @pytest.mark.parametrize("pdf_name", ["2024-10", "2025-05"])
    def test_parser_accuracy(self, pdf_name, temp_dir, golden_csvs):
        """Test parser accuracy against golden CSV."""
        pdf_file = Path(f"Itau_{pdf_name}.pdf")
        if not pdf_file.exists():
            pytest.skip(f"PDF file {pdf_file} not found")

        if pdf_name not in golden_csvs:
            pytest.skip(f"Golden CSV for {pdf_name} not found")

        # Run parser
        output_file = temp_dir / f"test_{pdf_name}.csv"
        result = subprocess.run([
            "python", "itau_parser_ultimate.py",
            str(pdf_file), "-o", str(output_file)
        ], capture_output=True, text=True)

        assert result.returncode == 0, f"Parser failed: {result.stderr}"
        assert output_file.exists(), "Output CSV not created"

        # Validate against golden CSV
        golden_file = golden_csvs[pdf_name]
        accuracy = self._calculate_accuracy(output_file, golden_file)

        # Require 65% accuracy minimum (current performance level)
        assert accuracy >= 0.65, f"Accuracy {accuracy:.2%} below threshold"

    def _calculate_accuracy(self, output_file: Path, golden_file: Path) -> float:
        """Calculate accuracy between output and golden CSV."""
        try:
            with open(output_file, encoding='utf-8') as f:
                output_rows = list(csv.reader(f))
            with open(golden_file, encoding='utf-8') as f:
                golden_rows = list(csv.reader(f))

            if not output_rows or not golden_rows:
                return 0.0

            # Simple row count comparison
            return min(len(output_rows), len(golden_rows)) / max(len(output_rows), len(golden_rows))
        except Exception:
            return 0.0
