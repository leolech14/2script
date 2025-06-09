"""Pytest configuration and fixtures for PDF parsing tests."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)

@pytest.fixture
def sample_pdfs() -> list[Path]:
    """Return list of available sample PDFs for testing."""
    pdf_dir = Path("all_pdfs")
    if pdf_dir.exists():
        return list(pdf_dir.glob("*.pdf"))
    return []

@pytest.fixture
def golden_csvs() -> dict[str, Path]:
    """Return mapping of golden CSV files."""
    golden_files = {}
    for csv_file in Path(".").glob("golden_*.csv"):
        key = csv_file.stem.replace("golden_", "")
        golden_files[key] = csv_file
    return golden_files
