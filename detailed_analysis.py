#!/usr/bin/env python3
"""
Detailed Analysis of Parser Performance vs Golden Files
Analyzes why parsers are missing transactions and provides detailed insights.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path


def load_csv_with_delimiter(path: Path, delimiter=','):
    """Load CSV with specified delimiter."""
    rows = []
    try:
        with open(path, encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                rows.append(row)
        return rows
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return []

def analyze_date_patterns(rows, source_name):
    """Analyze date patterns in the data."""
    print(f"\n📅 DATE ANALYSIS - {source_name}:")

    date_fields = ['post_date', 'date']
    dates_found = []

    for row in rows:
        for field in date_fields:
            if field in row and row[field].strip():
                dates_found.append(row[field].strip())
                break

    if dates_found:
        print(f"  Total dates: {len(dates_found)}")
        print(f"  First 5 dates: {dates_found[:5]}")
        print(f"  Last 5 dates: {dates_found[-5:]}")

        # Analyze date formats
        formats = defaultdict(int)
        for date in dates_found:
            if re.match(r'\d{4}-\d{2}-\d{2}', date):
                formats['YYYY-MM-DD'] += 1
            elif re.match(r'\d{2}/\d{2}', date):
                formats['DD/MM'] += 1
            elif re.match(r'\d{2}/\d{2}/\d{4}', date):
                formats['DD/MM/YYYY'] += 1
            else:
                formats['OTHER'] += 1

        print("  Date formats:")
        for fmt, count in formats.items():
            print(f"    {fmt}: {count}")
    else:
        print("  No dates found!")

def analyze_card_numbers(rows, source_name):
    """Analyze card number patterns."""
    print(f"\n💳 CARD ANALYSIS - {source_name}:")

    card_field = 'card_last4'
    cards = []

    for row in rows:
        if card_field in row and row[card_field].strip():
            cards.append(row[card_field].strip())

    if cards:
        unique_cards = set(cards)
        print(f"  Total card entries: {len(cards)}")
        print(f"  Unique cards: {list(unique_cards)}")
    else:
        print("  No card numbers found!")

def analyze_amounts(rows, source_name):
    """Analyze amount patterns."""
    print(f"\n💰 AMOUNT ANALYSIS - {source_name}:")

    amount_fields = ['amount_brl', 'valor_brl', 'amount']
    amounts = []

    for row in rows:
        for field in amount_fields:
            if field in row and row[field].strip():
                try:
                    # Try to convert to float
                    amount_str = row[field].strip()
                    if ',' in amount_str and '.' in amount_str:
                        # Brazilian format: 1.234,56
                        amount_clean = amount_str.replace('.', '').replace(',', '.')
                    else:
                        # Standard format: 1234.56 or 1234,56
                        amount_clean = amount_str.replace(',', '.')

                    amount = float(amount_clean)
                    amounts.append(amount)
                except ValueError:
                    pass
                break

    if amounts:
        print(f"  Total amounts: {len(amounts)}")
        print(f"  Range: {min(amounts):.2f} to {max(amounts):.2f}")
        print(f"  Average: {sum(amounts)/len(amounts):.2f}")
        print(f"  Positive amounts: {len([a for a in amounts if a > 0])}")
        print(f"  Negative amounts: {len([a for a in amounts if a < 0])}")
    else:
        print("  No valid amounts found!")

def analyze_descriptions(rows, source_name):
    """Analyze description patterns."""
    print(f"\n📝 DESCRIPTION ANALYSIS - {source_name}:")

    desc_fields = ['desc_raw', 'description']
    descriptions = []

    for row in rows:
        for field in desc_fields:
            if field in row and row[field].strip():
                descriptions.append(row[field].strip())
                break

    if descriptions:
        print(f"  Total descriptions: {len(descriptions)}")
        print("  Sample descriptions:")
        for i, desc in enumerate(descriptions[:5]):
            print(f"    {i+1}. {desc[:60]}...")

        # Look for common patterns
        patterns = defaultdict(int)
        for desc in descriptions:
            desc_upper = desc.upper()
            if 'FARMACIA' in desc_upper:
                patterns['FARMACIA'] += 1
            if 'RECARGAPAY' in desc_upper:
                patterns['RECARGAPAY'] += 1
            if 'APPLE' in desc_upper:
                patterns['APPLE'] += 1
            if 'PAGAMENTO' in desc_upper:
                patterns['PAGAMENTO'] += 1
            if 'IOF' in desc_upper:
                patterns['IOF'] += 1

        print("  Common patterns:")
        for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
            print(f"    {pattern}: {count}")
    else:
        print("  No descriptions found!")

def detailed_transaction_comparison(script_rows, golden_rows, script_name):
    """Detailed comparison of specific transactions."""
    print(f"\n🔍 DETAILED TRANSACTION COMPARISON - {script_name}:")

    # Look for a few specific transactions from golden that should be findable
    golden_samples = golden_rows[:5] if golden_rows else []

    for i, golden_row in enumerate(golden_samples):
        golden_desc = golden_row.get('desc_raw', '').strip()
        golden_amount = golden_row.get('amount_brl', '').strip()
        golden_date = golden_row.get('post_date', '').strip()

        print(f"\n  Golden Transaction {i+1}:")
        print(f"    Date: {golden_date}")
        print(f"    Description: {golden_desc[:50]}...")
        print(f"    Amount: {golden_amount}")

        # Look for similar transactions in script output
        found_similar = False
        for script_row in script_rows:
            script_desc = script_row.get('desc_raw', script_row.get('description', '')).strip()
            script_amount = script_row.get('valor_brl', script_row.get('amount_brl', script_row.get('amount', ''))).strip()

            # Check if descriptions have common words
            golden_words = set(golden_desc.upper().split())
            script_words = set(script_desc.upper().split())
            common_words = golden_words & script_words

            if len(common_words) >= 2 or golden_desc.upper() in script_desc.upper():
                print("    Possible match found:")
                print(f"      Script Description: {script_desc[:50]}...")
                print(f"      Script Amount: {script_amount}")
                print(f"      Common words: {list(common_words)}")
                found_similar = True
                break

        if not found_similar:
            print("    ❌ No similar transaction found in script output")

def main():
    print("🔬 DETAILED ANALYSIS OF PARSER PERFORMANCE")
    print("="*60)

    # File paths
    golden_2025 = Path("golden_2025-05.csv")
    codex_2025 = Path("test_outputs/codex_Itau_2025-05.csv")
    pdf_csv_2025 = Path("test_outputs/pdf_to_csv_Itau_2025-05.csv")

    # Load data
    golden_rows = load_csv_with_delimiter(golden_2025, ';')
    codex_rows = load_csv_with_delimiter(codex_2025, ',')
    pdf_csv_rows = load_csv_with_delimiter(pdf_csv_2025, ',')

    print("\n📊 BASIC STATS:")
    print(f"  Golden 2025-05: {len(golden_rows)} rows")
    print(f"  Codex 2025-05: {len(codex_rows)} rows")
    print(f"  PDF-to-CSV 2025-05: {len(pdf_csv_rows)} rows")

    # Analyze each dataset
    for rows, name in [(golden_rows, "GOLDEN"), (codex_rows, "CODEX"), (pdf_csv_rows, "PDF-to-CSV")]:
        if rows:
            analyze_date_patterns(rows, name)
            analyze_card_numbers(rows, name)
            analyze_amounts(rows, name)
            analyze_descriptions(rows, name)
        else:
            print(f"\n❌ No data found for {name}")

    # Detailed transaction comparison
    if golden_rows and codex_rows:
        detailed_transaction_comparison(codex_rows, golden_rows, "CODEX")

    # Field name analysis
    print("\n📋 FIELD NAME ANALYSIS:")
    for rows, name in [(golden_rows, "GOLDEN"), (codex_rows, "CODEX"), (pdf_csv_rows, "PDF-to-CSV")]:
        if rows:
            print(f"  {name} fields: {list(rows[0].keys())}")

if __name__ == "__main__":
    main()
