#!/usr/bin/env python3
"""Debug script to understand PDF structure better"""

import re
from pathlib import Path

import pdfplumber


def debug_pdf_structure(pdf_path: Path):
    """Debug PDF to understand table and text structure"""

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages[:2], 1):  # Just first 2 pages
            print(f"\n=== PAGE {page_num} ===")

            # Extract tables
            tables = page.extract_tables()
            print(f"Found {len(tables)} tables")

            for i, table in enumerate(tables):
                print(f"\nTable {i+1} ({len(table)} rows):")
                for j, row in enumerate(table[:5]):  # First 5 rows
                    print(f"  Row {j+1}: {row}")
                if len(table) > 5:
                    print(f"  ... and {len(table)-5} more rows")

            # Extract text
            text = page.extract_text()
            if text:
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                print(f"\nText lines ({len(lines)} total):")

                # Look for posting patterns
                posting_lines = []
                category_lines = []

                for line in lines[:20]:  # First 20 lines
                    if re.match(r'\d{1,2}/\d{1,2}', line):
                        posting_lines.append(line)
                        print(f"  POSTING: {line}")
                    elif re.match(r'^[A-ZÀÁÂÃÇÉÊÍÕÓÔÚÜ\s]+\.[A-ZÀÁÂÃÇÉÊÍÕÓÔÚÜ\s]+$', line):
                        category_lines.append(line)
                        print(f"  CATEGORY: {line}")
                    else:
                        print(f"  OTHER: {line}")

                print(f"\nFound {len(posting_lines)} posting lines, {len(category_lines)} category lines")

if __name__ == "__main__":
    debug_pdf_structure(Path("Itau_2025-05.pdf"))
