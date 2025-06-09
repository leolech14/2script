#!/usr/bin/env python3
"""
flat_txt_repair.py – Heuristic repair for mixed Itaú TXT postings
Use this ONLY when table extraction fails and you must work with flat text.
Attempts to pair main posting lines with their category/city lines.
"""

import argparse
import csv
import re
from pathlib import Path

# Patterns for identifying different line types
PATTERNS = {
    'main_posting': re.compile(r'^\d{1,2}/\d{1,2}\s+.+?\s+\d{1,3}(?:\.\d{3})*,\d{2}$'),
    'category_city': re.compile(r'^[A-ZÀÁÂÃÇÉÊÍÕÓÔÚÜ\s\.]+$'),
    'fx_line': re.compile(r'^\d{2}/\d{2}\s+.+?\s+\d{1,3}(?:\.\d{3})*,\d{2}\s+\d{1,3}(?:\.\d{3})*,\d{2}$'),
    'fx_detail': re.compile(r'^[A-Z\s]+\s+\d{1,3}(?:\.\d{3})*,\d{2}\s+[A-Z]{3}\s+\d{1,3}(?:\.\d{3})*,\d{2}$'),
    'fx_rate': re.compile(r'Dólar de Conversão.*?(\d+,\d{4})'),
    'payment': re.compile(r'^\d{1,2}/\d{1,2}\s+PAGAMENTO.*?7117.*?(-?\d{1,3}(?:\.\d{3})*,\d{2})$'),
    'card_header': re.compile(r'final (\d{4})'),
    'iof': re.compile(r'Repasse de IOF')
}

def classify_line(line: str) -> str:
    """Classify a line by type"""
    line = line.strip()
    if not line:
        return 'empty'

    for pattern_name, pattern in PATTERNS.items():
        if pattern.search(line):
            return pattern_name

    return 'unknown'

def parse_main_posting(line: str) -> dict[str, str]:
    """Parse main posting line: date + description + amount"""
    match = PATTERNS['main_posting'].match(line)
    if not match:
        return {}

    parts = line.split()
    date = parts[0]
    amount = parts[-1]
    description = ' '.join(parts[1:-1])

    return {
        'date': date,
        'description': description,
        'amount': amount,
        'category': '',
        'merchant_city': '',
        'original_line': line
    }

def parse_category_city(line: str) -> tuple[str, str]:
    """Parse category.city line"""
    if '.' in line:
        parts = line.split('.')
        category = parts[0].strip()
        city = parts[-1].strip() if len(parts) > 1 else ''
        return category, city
    return '', ''

def group_posting_lines(lines: list[str]) -> list[dict[str, str]]:
    """Group lines into complete postings using heuristics"""
    postings = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        line_type = classify_line(line)

        if line_type == 'main_posting':
            # Found main posting line
            posting = parse_main_posting(line)

            # Look for corresponding category/city line
            # Check next few lines for category info
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j].strip()
                next_type = classify_line(next_line)

                if next_type == 'category_city':
                    category, city = parse_category_city(next_line)
                    posting['category'] = category
                    posting['merchant_city'] = city
                    break
                elif next_type == 'main_posting':
                    # Hit another main posting, stop looking
                    break

            postings.append(posting)
            i += 1

        elif line_type == 'payment':
            # Handle payment line
            match = PATTERNS['payment'].search(line)
            if match:
                parts = line.split()
                date = parts[0]
                amount = match.group(1)
                posting = {
                    'date': date,
                    'description': 'PAGAMENTO',
                    'amount': amount,
                    'category': 'PAGAMENTO',
                    'merchant_city': '',
                    'original_line': line
                }
                postings.append(posting)
            i += 1

        elif line_type == 'fx_line':
            # Handle FX posting (simplified)
            parts = line.split()
            if len(parts) >= 4:
                date = parts[0]
                amount_brl = parts[-1]
                description = ' '.join(parts[1:-2])
                posting = {
                    'date': date,
                    'description': description,
                    'amount': amount_brl,
                    'category': 'FX',
                    'merchant_city': '',
                    'original_line': line
                }
                postings.append(posting)
            i += 1

        else:
            i += 1

    return postings

def repair_flat_txt(input_path: Path) -> list[dict[str, str]]:
    """Main repair function"""
    with open(input_path, encoding='utf-8') as f:
        lines = f.readlines()

    # Clean lines
    cleaned_lines = []
    for line in lines:
        cleaned = line.strip()
        if cleaned:
            # Remove special characters and normalize
            cleaned = re.sub(r'[\ue000-\uf8ff]', '', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            cleaned_lines.append(cleaned)

    print(f"Loaded {len(cleaned_lines)} non-empty lines")

    # Classify lines for debugging
    line_types = {}
    for line in cleaned_lines:
        line_type = classify_line(line)
        line_types[line_type] = line_types.get(line_type, 0) + 1

    print("Line classification:")
    for line_type, count in sorted(line_types.items()):
        print(f"  {line_type}: {count}")

    # Group into postings
    postings = group_posting_lines(cleaned_lines)

    return postings

def main():
    parser = argparse.ArgumentParser(
        description="Repair flat/mixed Itaú TXT to structured CSV"
    )
    parser.add_argument("input", type=Path, help="Input TXT file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output CSV file")
    parser.add_argument("--debug", action="store_true", help="Save debug info")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file {args.input} not found")
        return 1

    print(f"Repairing flat text from {args.input}...")
    postings = repair_flat_txt(args.input)

    print(f"Extracted {len(postings)} postings")

    # Save main output
    if postings:
        fieldnames = ['date', 'description', 'amount', 'category', 'merchant_city']
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            for posting in postings:
                # Only write fields that are in schema
                row = {k: posting.get(k, '') for k in fieldnames}
                writer.writerow(row)

    # Save debug output if requested
    if args.debug:
        debug_path = args.output.with_suffix('.debug.csv')
        fieldnames_debug = ['date', 'description', 'amount', 'category', 'merchant_city', 'original_line']
        with open(debug_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames_debug, delimiter=';')
            writer.writeheader()
            writer.writerows(postings)
        print(f"Debug info saved to {debug_path}")

    if args.verbose and postings:
        print("\nSample repaired postings:")
        for i, posting in enumerate(postings[:5], 1):
            print(f"  {i}. {posting['date']} - {posting['description'][:40]}... - {posting['amount']}")

    print(f"✅ Repair completed. Saved to {args.output}")

    return 0

if __name__ == "__main__":
    exit(main())
