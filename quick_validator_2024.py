#!/usr/bin/env python3
"""Quick validator for 2024-10 files."""

import csv


def load_csv(path, delimiter=','):
    """Load CSV with specified delimiter."""
    rows = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            rows.append(row)
    return rows

def create_transaction_key(txn):
    """Create unique key for transaction matching."""
    date = str(txn.get('post_date', '')).strip().upper()
    desc = str(txn.get('desc_raw', '')).strip().upper()[:50]
    amount = str(txn.get('amount_brl', '')).strip()

    if amount:
        try:
            amount_clean = amount.replace(',', '.')
            amount_float = float(amount_clean)
            amount_str = f"{amount_float:.2f}"
        except ValueError:
            amount_str = amount
    else:
        amount_str = '0.00'

    return f"{date}|{desc}|{amount_str}"

def main():
    # Load both files
    parsed = load_csv("ultimate_2024-10.csv", ';')
    golden = load_csv("golden_2024-10.csv", ';')

    print("🔬 ULTIMATE PARSER vs GOLDEN CSV ANALYSIS (2024-10)")
    print("="*60)
    print(f"Parsed transactions: {len(parsed)}")
    print(f"Golden transactions: {len(golden)}")

    # Create indexes
    parsed_index = {create_transaction_key(txn): txn for txn in parsed}
    golden_index = {create_transaction_key(txn): txn for txn in golden}

    # Find matches
    matched_keys = set(parsed_index.keys()) & set(golden_index.keys())
    parsed_only = set(parsed_index.keys()) - set(golden_index.keys())
    golden_only = set(golden_index.keys()) - set(parsed_index.keys())

    print("\n📊 MATCHING RESULTS:")
    print(f"  ✅ Matched transactions: {len(matched_keys)}")
    print(f"  ➕ Extra in parsed: {len(parsed_only)}")
    print(f"  ➖ Missing from parsed: {len(golden_only)}")

    # Calculate percentages
    coverage = (len(matched_keys) / len(golden)) * 100 if golden else 0

    # Count exact matches
    exact_matches = 0
    for key in matched_keys:
        parsed_txn = parsed_index[key]
        golden_txn = golden_index[key]

        # Check if all important fields match
        important_fields = ['post_date', 'desc_raw', 'amount_brl', 'card_last4', 'category']
        all_match = True
        for field in important_fields:
            if str(parsed_txn.get(field, '')).strip() != str(golden_txn.get(field, '')).strip():
                all_match = False
                break

        if all_match:
            exact_matches += 1

    accuracy = (exact_matches / len(matched_keys)) * 100 if matched_keys else 0
    total_score = (coverage * accuracy) / 100

    print(f"  📈 Coverage: {coverage:.1f}%")
    print(f"  🎯 Accuracy: {accuracy:.1f}% ({exact_matches}/{len(matched_keys)} exact matches)")
    print(f"\n🏆 OVERALL SCORE: {total_score:.1f}/100")

    return {
        'coverage': coverage,
        'accuracy': accuracy,
        'total_score': total_score,
        'matched': len(matched_keys),
        'missing': len(golden_only),
        'extra': len(parsed_only),
        'exact_matches': exact_matches
    }

if __name__ == "__main__":
    main()
