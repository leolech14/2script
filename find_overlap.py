#!/usr/bin/env python3
"""Find overlapping transactions between parser and golden CSV"""

import csv
from pathlib import Path

def load_csv(path):
    """Load CSV into list of dicts"""
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter=';'))

def find_overlaps(parser_file, golden_file):
    """Find transactions that appear in both files"""
    parser_data = load_csv(parser_file)
    golden_data = load_csv(golden_file)
    
    print(f"Parser transactions: {len(parser_data)}")
    print(f"Golden transactions: {len(golden_data)}")
    
    # Extract key identifiers from each transaction
    parser_keys = set()
    for row in parser_data:
        # Use a simplified key for matching
        desc = row['desc_raw'].upper()
        if ' ' in desc:
            # Take the merchant name part
            key_parts = desc.split()
            if len(key_parts) >= 2:
                key = key_parts[1]  # Second word often contains merchant
                parser_keys.add(key)
    
    golden_keys = set()
    for row in golden_data:
        desc = row['desc_raw'].upper()
        if ' ' in desc:
            key_parts = desc.split()
            if len(key_parts) >= 1:
                key = key_parts[0]  # First word
                golden_keys.add(key)
    
    overlaps = parser_keys & golden_keys
    print(f"\nPossible overlapping merchants: {len(overlaps)}")
    for overlap in sorted(overlaps):
        print(f"  - {overlap}")
    
    # Try to find exact transaction matches
    print(f"\n=== EXACT MATCHES ===")
    exact_matches = 0
    for p_row in parser_data[:10]:  # Check first 10
        for g_row in golden_data:
            # Check if descriptions contain similar elements
            p_desc = p_row['desc_raw'].upper()
            g_desc = g_row['desc_raw'].upper()
            
            # Look for common words
            p_words = set(p_desc.split())
            g_words = set(g_desc.split())
            common_words = p_words & g_words
            
            if len(common_words) >= 2:  # At least 2 words in common
                print(f"Potential match:")
                print(f"  Parser: {p_row['desc_raw']} | {p_row['amount_brl']} | {p_row['post_date']}")
                print(f"  Golden: {g_row['desc_raw']} | {g_row['amount_brl']} | {g_row['post_date']}")
                print(f"  Common: {common_words}")
                exact_matches += 1
                break
    
    print(f"\nFound {exact_matches} potential matches")

if __name__ == "__main__":
    parser_file = "test_output/Itau_2025-05_parsed.csv"
    golden_file = "golden_2025-05.csv"
    
    if Path(parser_file).exists() and Path(golden_file).exists():
        find_overlaps(parser_file, golden_file)
    else:
        print("Files not found. Please run the parser first.")
