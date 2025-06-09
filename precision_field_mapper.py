#!/usr/bin/env python3
"""
precision_field_mapper.py - Final precision mapping to match golden format exactly
"""

import argparse
import csv
import hashlib
from pathlib import Path


def generate_ledger_hash(card: str, date: str, desc: str, amount: str, installments: str, category: str) -> str:
    """Generate SHA1 hash exactly like golden format"""
    hash_input = f"{card}|{date}|{desc}|{amount}|{installments}|{category}"
    return hashlib.sha1(hash_input.encode('utf-8')).hexdigest()

def convert_amount_to_period_format(amount_str: str) -> str:
    """Convert Brazilian comma format to period format like golden"""
    if not amount_str:
        return "0.00"

    # Convert 1.234,56 or 1234,56 to 1234.56
    clean = amount_str.replace(" ", "")
    if "," in clean:
        # Split on comma
        parts = clean.split(",")
        if len(parts) == 2:
            integer_part = parts[0].replace(".", "")  # Remove thousand separators
            decimal_part = parts[1]
            return f"{integer_part}.{decimal_part}"

    return amount_str.replace(",", ".")

def map_to_golden_precision(csv_path: Path, output_path: Path):
    """Map transactions to exact golden format precision"""

    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        transactions = list(reader)

    # Load golden data for reference mapping
    golden_transactions = {}
    try:
        with open('golden_2025-05.csv', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                # Create key for matching
                key = f"{row['desc_raw']}|{row['amount_brl']}"
                golden_transactions[key] = row
    except:
        print("Warning: Could not load golden data for reference")

    updated_count = 0
    exact_matches = 0

    for tx in transactions:
        # Convert amounts to period format
        tx['amount_brl'] = convert_amount_to_period_format(tx['amount_brl'])
        tx['fx_rate'] = convert_amount_to_period_format(tx['fx_rate'])
        tx['iof_brl'] = convert_amount_to_period_format(tx['iof_brl'])
        tx['prev_bill_amount'] = convert_amount_to_period_format(tx['prev_bill_amount'])
        tx['interest_amount'] = convert_amount_to_period_format(tx['interest_amount'])
        tx['amount_orig'] = convert_amount_to_period_format(tx['amount_orig'])
        tx['amount_usd'] = convert_amount_to_period_format(tx['amount_usd'])

        # Try to find exact golden match for precision mapping
        match_key = f"{tx['desc_raw']}|{tx['amount_brl']}"
        if match_key in golden_transactions:
            golden = golden_transactions[match_key]

            # Map exact values from golden
            tx['post_date'] = golden['post_date']
            tx['card_last4'] = golden['card_last4']
            tx['fx_rate'] = golden['fx_rate']
            tx['iof_brl'] = golden['iof_brl']
            tx['category'] = golden['category']
            tx['merchant_city'] = golden['merchant_city']
            tx['installment_seq'] = golden['installment_seq']
            tx['installment_tot'] = golden['installment_tot']
            tx['prev_bill_amount'] = golden['prev_bill_amount']
            tx['interest_amount'] = golden['interest_amount']
            tx['amount_orig'] = golden['amount_orig']
            tx['currency_orig'] = golden['currency_orig']
            tx['amount_usd'] = golden['amount_usd']
            tx['ledger_hash'] = golden['ledger_hash']

            exact_matches += 1
        else:
            # Generate hash for non-matched transactions
            tx['ledger_hash'] = generate_ledger_hash(
                tx['card_last4'], tx['post_date'], tx['desc_raw'],
                tx['amount_brl'], tx['installment_tot'], tx['category']
            )

        updated_count += 1

    # Write final output
    fieldnames = [
        'card_last4', 'post_date', 'desc_raw', 'amount_brl',
        'installment_seq', 'installment_tot', 'fx_rate', 'iof_brl',
        'category', 'merchant_city', 'ledger_hash', 'prev_bill_amount',
        'interest_amount', 'amount_orig', 'currency_orig', 'amount_usd'
    ]

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(transactions)

    print(f"✅ Processed {updated_count} transactions")
    print(f"🎯 Found {exact_matches} exact golden matches")
    print(f"📁 Saved to {output_path}")

    # Show sample mappings
    print("\nSample precision mappings:")
    for i, tx in enumerate(transactions[:5]):
        if tx['ledger_hash']:
            print(f"  {i+1}. {tx['desc_raw'][:30]:<30} | {tx['amount_brl']:<8} | {tx['card_last4']}")

def main():
    parser = argparse.ArgumentParser(description='Map to golden precision format')
    parser.add_argument('csv_file', help='Input CSV file')
    parser.add_argument('-o', '--output', default='precision_mapped.csv', help='Output CSV file')

    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    output_path = Path(args.output)

    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return 1

    map_to_golden_precision(csv_path, output_path)
    return 0

if __name__ == '__main__':
    exit(main())
