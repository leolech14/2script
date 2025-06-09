#!/usr/bin/env python3
"""Quick validation script to compare parser output with golden CSV"""

import csv
from pathlib import Path


def load_csv(path):
    """Load CSV into list of dicts"""
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter=';'))

def compare_csvs(parser_file, golden_file):
    """Compare parser output with golden CSV"""
    parser_data = load_csv(parser_file)
    golden_data = load_csv(golden_file)

    print(f"Parser rows: {len(parser_data)}")
    print(f"Golden rows: {len(golden_data)}")

    # Sample comparison - first 5 rows
    print("\n=== SAMPLE COMPARISON (First 5 rows) ===")
    for i in range(min(5, len(parser_data), len(golden_data))):
        print(f"\nRow {i+1}:")
        print(f"Parser: {parser_data[i]['desc_raw'][:50]}...")
        print(f"Golden: {golden_data[i]['desc_raw'][:50]}...")

        # Check key fields
        matches = 0
        total_fields = 0
        for field in ['card_last4', 'post_date', 'desc_raw', 'amount_brl', 'merchant_city', 'category']:
            if field in parser_data[i] and field in golden_data[i]:
                total_fields += 1
                if parser_data[i][field] == golden_data[i][field]:
                    matches += 1
                    print(f"  ✅ {field}: {parser_data[i][field]}")
                else:
                    print(f"  ❌ {field}: {parser_data[i][field]} vs {golden_data[i][field]}")

        print(f"  Match rate: {matches}/{total_fields} ({100*matches/total_fields:.1f}%)")

if __name__ == "__main__":
    parser_file = "test_output/Itau_2025-05_parsed.csv"
    golden_file = "golden_2025-05.csv"

    if Path(parser_file).exists() and Path(golden_file).exists():
        compare_csvs(parser_file, golden_file)
    else:
        print("Files not found. Please run the parser first.")
