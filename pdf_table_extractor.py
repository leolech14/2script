#!/usr/bin/env python3
"""
pdf_table_extractor.py – Table-aware Itaú PDF extractor
Extracts postings row-by-row, preserving structure for robust downstream parsing.
Handles parallel tables and prevents mixing of postings.
"""

import argparse
import csv
import re
from pathlib import Path

import pdfplumber


def clean_cell(cell: str) -> str:
    """Clean extracted table cell"""
    if not cell:
        return ""
    # Remove extra whitespace and special characters
    cleaned = re.sub(r'\s+', ' ', cell.strip())
    # Remove Unicode private use area characters
    cleaned = re.sub(r'[\ue000-\uf8ff]', '', cleaned)
    return cleaned

def is_posting_row(row: list[str]) -> bool:
    """Check if row represents a transaction posting"""
    if len(row) < 3:
        return False

    # Look for date pattern in first column
    date_pattern = r'\d{1,2}/\d{1,2}'
    if not re.match(date_pattern, row[0]):
        return False

    # Look for amount pattern in last meaningful column
    amount_pattern = r'-?\d{1,3}(?:\.\d{3})*,\d{2}'
    for cell in reversed(row):
        if cell and re.search(amount_pattern, cell):
            return True

    return False

def extract_posting_from_row(row: list[str]) -> dict[str, str] | None:
    """Extract posting data from table row"""
    if not is_posting_row(row):
        return None

    # Clean all cells
    clean_row = [clean_cell(cell) for cell in row]

    # Basic extraction - adapt based on actual table structure
    posting = {
        'date': clean_row[0] if len(clean_row) > 0 else '',
        'description': clean_row[1] if len(clean_row) > 1 else '',
        'amount': '',
        'category': '',
        'merchant_city': ''
    }

    # Find amount (usually last meaningful cell with number pattern)
    amount_pattern = r'-?\d{1,3}(?:\.\d{3})*,\d{2}'
    for cell in reversed(clean_row):
        if cell and re.search(amount_pattern, cell):
            posting['amount'] = cell
            break

    # Look for category.city pattern (usually in a separate cell)
    for cell in clean_row[2:]:  # Skip date and description
        if cell and '.' in cell and not re.search(r'\d', cell):
            parts = cell.split('.')
            if len(parts) >= 2:
                posting['category'] = parts[0].strip()
                posting['merchant_city'] = parts[-1].strip()
            break

    return posting

def extract_tables_from_pdf(pdf_path: Path) -> list[dict[str, str]]:
    """Extract all postings from PDF using table extraction and text analysis"""
    postings = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"Processing page {page_num}...")

            # First, try table extraction
            tables = page.extract_tables()

            # Also extract text for merchant city matching
            text = page.extract_text() or ""
            text_lines = [line.strip() for line in text.splitlines() if line.strip()]

            if not tables:
                # Fallback: parse text manually
                for line in text_lines:
                    # Try to parse line as posting
                    if re.match(r'\d{1,2}/\d{1,2}', line.strip()):
                        parts = line.strip().split()
                        if len(parts) >= 3:
                            fake_row = [parts[0], ' '.join(parts[1:-1]), parts[-1]]
                            posting = extract_posting_from_row(fake_row)
                            if posting:
                                postings.append(posting)
                continue

            # Process each table on the page
            table_postings = []
            for table_num, table in enumerate(tables):
                print(f"  Table {table_num + 1}: {len(table)} rows")

                for row in table:
                    if row:  # Skip empty rows
                        posting = extract_posting_from_row(row)
                        if posting:
                            table_postings.append(posting)

            # Now try to match merchant cities from text lines
            # Look for category.city patterns in text
            category_city_lines = []
            for line in text_lines:
                # Pattern for category.city lines (all caps with dot)
                if re.match(r'^[A-ZÀÁÂÃÇÉÊÍÕÓÔÚÜ\s]+\.[A-ZÀÁÂÃÇÉÊÍÕÓÔÚÜ\s]+$', line):
                    category_city_lines.append(line)

            # Try to match postings with their category/city lines
            # This is heuristic - match by proximity or order
            for i, posting in enumerate(table_postings):
                if i < len(category_city_lines):
                    cat_city = category_city_lines[i]
                    if '.' in cat_city:
                        parts = cat_city.split('.')
                        posting['category'] = parts[0].strip()
                        posting['merchant_city'] = parts[-1].strip()

            postings.extend(table_postings)

    return postings

def save_postings(postings: list[dict[str, str]], output_path: Path, format_type: str = 'csv'):
    """Save postings to file"""
    if format_type.lower() == 'csv':
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if postings:
                writer = csv.DictWriter(f, fieldnames=postings[0].keys(), delimiter=';')
                writer.writeheader()
                writer.writerows(postings)
    else:  # txt format
        with open(output_path, 'w', encoding='utf-8') as f:
            for posting in postings:
                line = f"{posting['date']} | {posting['description']} | {posting['amount']} | {posting['category']}.{posting['merchant_city']}"
                f.write(line + '\n')

    print(f"Saved {len(postings)} postings to {output_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Extract Itaú PDF tables preserving posting structure"
    )
    parser.add_argument("pdf", type=Path, help="Input PDF file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output file")
    parser.add_argument("--format", choices=['csv', 'txt'], default='csv',
                       help="Output format (default: csv)")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Verbose output")

    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: PDF file {args.pdf} not found")
        return 1

    print(f"Extracting postings from {args.pdf}...")
    postings = extract_tables_from_pdf(args.pdf)

    if args.verbose:
        print(f"\nExtracted {len(postings)} postings:")
        for i, posting in enumerate(postings[:5], 1):
            print(f"  {i}. {posting['date']} - {posting['description'][:50]}... - {posting['amount']}")
        if len(postings) > 5:
            print(f"  ... and {len(postings) - 5} more")

    save_postings(postings, args.output, args.format)
    print("✅ Extraction completed successfully!")

    return 0

if __name__ == "__main__":
    exit(main())
