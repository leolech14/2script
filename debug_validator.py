#!/usr/bin/env python3
"""Debug validator to see why transactions aren't matching."""

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

    # Normalize amount
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
    parsed = load_csv("ultimate_2025-05.csv", ';')
    golden = load_csv("golden_2025-05.csv", ';')

    print(f"Parsed transactions: {len(parsed)}")
    print(f"Golden transactions: {len(golden)}")

    # Show first few parsed keys
    print("\nFirst 5 parsed transaction keys:")
    for i, txn in enumerate(parsed[:5]):
        key = create_transaction_key(txn)
        print(f"{i+1}. {key}")
        print(f"   Raw: date={txn.get('post_date')}, desc={txn.get('desc_raw')}, amount={txn.get('amount_brl')}")

    # Show first few golden keys
    print("\nFirst 5 golden transaction keys:")
    for i, txn in enumerate(golden[:5]):
        key = create_transaction_key(txn)
        print(f"{i+1}. {key}")
        print(f"   Raw: date={txn.get('post_date')}, desc={txn.get('desc_raw')}, amount={txn.get('amount_brl')}")

    # Check for any matches
    parsed_keys = {create_transaction_key(txn) for txn in parsed}
    golden_keys = {create_transaction_key(txn) for txn in golden}

    matches = parsed_keys & golden_keys
    print(f"\nTotal matches found: {len(matches)}")

    if matches:
        print("\nSample matches:")
        for i, match in enumerate(list(matches)[:5]):
            print(f"{i+1}. {match}")

    # Check specific transaction
    target_desc = "FARMACIA SAO JOAO 04/06"
    target_amount = "38.34"

    print(f"\nLooking for transaction with desc='{target_desc}' and amount='{target_amount}':")

    found_in_parsed = False
    for txn in parsed:
        if target_desc in str(txn.get('desc_raw', '')) and target_amount in str(txn.get('amount_brl', '')):
            print(f"Found in PARSED: {create_transaction_key(txn)}")
            found_in_parsed = True
            break

    found_in_golden = False
    for txn in golden:
        if target_desc in str(txn.get('desc_raw', '')) and target_amount in str(txn.get('amount_brl', '')):
            print(f"Found in GOLDEN: {create_transaction_key(txn)}")
            found_in_golden = True
            break

    if not found_in_parsed:
        print("Not found in parsed CSV")
    if not found_in_golden:
        print("Not found in golden CSV")

if __name__ == "__main__":
    main()
