#!/usr/bin/env python3
"""
structured_csv_parser.py – Enhanced CSV parser for table-extracted Itaú data
Processes structured CSV from table extractor to final golden-compatible format.
"""

import argparse
import csv
import hashlib
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

# Golden CSV schema
GOLDEN_SCHEMA = [
    "card_last4",
    "post_date",
    "desc_raw",
    "amount_brl",
    "installment_seq",
    "installment_tot",
    "fx_rate",
    "iof_brl",
    "category",
    "merchant_city",
    "ledger_hash",
    "prev_bill_amount",
    "interest_amount",
    "amount_orig",
    "currency_orig",
    "amount_usd"
]

def normalize_amount(amount_str: str) -> Decimal:
    """Convert Brazilian amount format to Decimal"""
    if not amount_str:
        return Decimal("0.00")

    # Remove everything except digits, comma, dot, and minus
    clean = re.sub(r"[^\d,\.\-]", "", amount_str.replace(" ", ""))
    # Convert Brazilian format (1.234,56) to standard (1234.56)
    clean = clean.replace(".", "").replace(",", ".")

    try:
        return Decimal(clean).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except:
        return Decimal("0.00")

def normalize_date(date_str: str, ref_year: int = 2025) -> str:
    """Convert DD/MM or DD/MM/YYYY to YYYY-MM-DD"""
    if not date_str:
        return ""

    # Parse date pattern
    match = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", date_str)
    if not match:
        return ""

    day, month, year = match.groups()
    year = year or str(ref_year)

    try:
        day_int = int(day)
        month_int = int(month)
        year_int = int(year)

        # Validate ranges
        if month_int < 1 or month_int > 12:
            return ""
        if day_int < 1 or day_int > 31:
            return ""

        return f"{year_int:04d}-{month_int:02d}-{day_int:02d}"
    except ValueError:
        return ""

def extract_installments(description: str) -> tuple[str, str]:
    """Extract installment info from description"""
    # Pattern: XX/YY where XX is current, YY is total
    match = re.search(r"(\d{1,2})/(\d{1,2})", description)
    if match:
        return match.group(1), match.group(2)
    return "0", "0"

def classify_transaction(description: str, amount: Decimal) -> str:
    """Classify transaction based on description"""
    desc_upper = description.upper()

    # Special cases
    if "7117" in desc_upper or "PAGAMENTO" in desc_upper:
        return "PAGAMENTO"
    if "AJUSTE" in desc_upper or (abs(amount) < Decimal("0.30") and amount != 0):
        return "AJUSTE"
    if any(k in desc_upper for k in ("IOF", "JUROS", "MULTA")):
        return "ENCARGOS"

    # Category mapping
    category_map = {
        "FARMAC": "FARMÁCIA",
        "DROG": "FARMÁCIA",
        "PANVEL": "FARMÁCIA",
        "SUPERMERC": "SUPERMERCADO",
        "MERCADO": "SUPERMERCADO",
        "RESTAUR": "RESTAURANTE",
        "PIZZ": "RESTAURANTE",
        "POSTO": "POSTO",
        "COMBUST": "POSTO",
        "UBER": "TRANSPORTE",
        "TAXI": "TRANSPORTE",
        "HOTEL": "TURISMO",
        "AEROPORTO": "TURISMO",
        "APPLE": "DIVERSOS",
        "DISNEY": "DIVERSOS",
        "NETFLIX": "DIVERSOS"
    }

    for keyword, category in category_map.items():
        if keyword in desc_upper:
            return category

    # FX detection
    if any(c in desc_upper for c in ("USD", "EUR", "FX", "DOLAR")):
        return "FX"

    return "DIVERSOS"

def calculate_hash(card: str, date: str, desc: str, amount: str) -> str:
    """Calculate deterministic ledger hash"""
    key = f"{card}|{date}|{desc.lower()}|{amount}"
    return hashlib.sha1(key.encode('utf-8')).hexdigest()

def extract_card_number(text_lines: list[str]) -> str:
    """Extract card number from statement text"""
    card_pattern = re.compile(r"final (\d{4})")

    for line in text_lines:
        match = card_pattern.search(line)
        if match:
            return match.group(1)

    return "0000"  # Default fallback

def process_posting(posting: dict[str, str], card_last4: str, ref_year: int = 2025) -> dict[str, str]:
    """Convert extracted posting to golden format"""

    # Normalize fields
    amount_decimal = normalize_amount(posting.get('amount', ''))
    amount_str = f"{amount_decimal:.2f}".replace(".", ",")
    post_date = normalize_date(posting.get('date', ''), ref_year)
    description = posting.get('description', '').strip()

    # Extract additional info
    inst_seq, inst_tot = extract_installments(description)
    category = posting.get('category') or classify_transaction(description, amount_decimal)
    merchant_city = posting.get('merchant_city', '').upper()

    # Calculate hash
    ledger_hash = calculate_hash(card_last4, post_date, description, amount_str)

    # Build final record
    record = {
        "card_last4": card_last4,
        "post_date": post_date,
        "desc_raw": description,
        "amount_brl": amount_str,
        "installment_seq": inst_seq,
        "installment_tot": inst_tot,
        "fx_rate": "0,00",  # TODO: extract from FX postings
        "iof_brl": "0,00",  # TODO: extract from IOF postings
        "category": category,
        "merchant_city": merchant_city,
        "ledger_hash": ledger_hash,
        "prev_bill_amount": "0,00",
        "interest_amount": "0,00",
        "amount_orig": "0,00",  # TODO: extract from FX postings
        "currency_orig": "",     # TODO: extract from FX postings
        "amount_usd": "0,00"     # TODO: extract from FX postings
    }

    return record

def main():
    parser = argparse.ArgumentParser(
        description="Process structured Itaú CSV to golden format"
    )
    parser.add_argument("input", type=Path, help="Input CSV file from table extractor")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output CSV file")
    parser.add_argument("--card", type=str, help="Override card number (default: extract from data)")
    parser.add_argument("--year", type=int, default=2025, help="Reference year for dates")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file {args.input} not found")
        return 1

    # Load postings
    postings = []
    with open(args.input, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        postings = list(reader)

    print(f"Loaded {len(postings)} postings from {args.input}")

    # Extract or use provided card number
    card_last4 = args.card
    if not card_last4:
        # Try to extract from first posting that has card info
        for posting in postings:
            if posting.get('card_last4'):
                card_last4 = posting['card_last4']
                break
        else:
            card_last4 = "0000"

    # Process each posting
    processed_records = []
    for posting in postings:
        record = process_posting(posting, card_last4, args.year)
        processed_records.append(record)

    # Filter out invalid records and remove duplicates
    valid_records = []
    for record in processed_records:
        # Skip records with invalid dates or amounts
        if not record['post_date'] or not record['amount_brl']:
            continue
        # Skip records with clearly invalid data
        if record['amount_brl'] == "20860,60":  # This looks like a total, not a transaction
            continue
        valid_records.append(record)

    # Remove duplicates based on hash
    unique_records = {}
    for record in valid_records:
        hash_key = record['ledger_hash']
        if hash_key not in unique_records:
            unique_records[hash_key] = record

    final_records = list(unique_records.values())

    # Sort by date
    final_records.sort(key=lambda x: x['post_date'])

    # Write output
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=GOLDEN_SCHEMA, delimiter=';')
        writer.writeheader()
        writer.writerows(final_records)

    print(f"✅ Processed {len(final_records)} unique transactions to {args.output}")

    if args.verbose:
        print("\nSample transactions:")
        for i, record in enumerate(final_records[:3], 1):
            print(f"  {i}. {record['post_date']} - {record['desc_raw'][:40]}... - {record['amount_brl']}")

    return 0

if __name__ == "__main__":
    exit(main())
