#!/usr/bin/env python3
"""
advanced_text_extractor.py – Advanced text-based extractor for complex Itaú PDFs
Handles mixed layouts where transactions are embedded in text blocks.
"""

import argparse
import csv
import re
from pathlib import Path

import pdfplumber

# Enhanced patterns for complex text extraction
PATTERNS = {
    # Main transaction patterns
    'domestic': re.compile(r'(\d{1,2}/\d{1,2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})(?=\s|$)'),
    'payment': re.compile(r'(\d{1,2}/\d{1,2})\s+PAGAMENTO\s+EFETUADO\s+7117\s*-\s*(\d{1,3}(?:\.\d{3})*,\d{2})'),

    # FX patterns
    'fx_main': re.compile(r'(\d{2}/\d{2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2})'),
    'fx_rate': re.compile(r'Dólar de Conversão.*?R\$\s*(\d+,\d{4})'),
    'fx_city': re.compile(r'^([A-Z\s]+)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+([A-Z]{3})\s+(\d{1,3}(?:\.\d{3})*,\d{2})$'),

    # Category and city patterns
    'category_city': re.compile(r'^([A-ZÀÁÂÃÇÉÊÍÕÓÔÚÜ\s]+)\.([A-ZÀÁÂÃÇÉÊÍÕÓÔÚÜ\s]+)$'),

    # Card number
    'card': re.compile(r'Cartão\s+\d{4}\.XXXX\.XXXX\.(\d{4})'),
}

def clean_text(text: str) -> str:
    """Clean extracted text"""
    # Remove Unicode PUA characters
    text = re.sub(r'[\ue000-\uf8ff]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_card_number(text: str) -> str:
    """Extract card number from text"""
    match = PATTERNS['card'].search(text)
    return match.group(1) if match else "0000"

def find_transaction_blocks(lines: list[str]) -> list[dict[str, str]]:
    """Find and extract transaction blocks from text lines"""
    transactions = []
    i = 0

    while i < len(lines):
        line = clean_text(lines[i])

        # Look for payment transactions
        payment_match = PATTERNS['payment'].search(line)
        if payment_match:
            date, amount = payment_match.groups()
            transactions.append({
                'type': 'payment',
                'date': date,
                'description': 'PAGAMENTO',
                'amount': amount,
                'category': 'PAGAMENTO',
                'merchant_city': '',
                'original_line': line
            })
            i += 1
            continue

        # Look for domestic transactions
        domestic_match = PATTERNS['domestic'].search(line)
        if domestic_match:
            date, desc, amount = domestic_match.groups()

            # Clean description
            desc = clean_text(desc)

            # Look for category.city in nearby lines
            category, city = '', ''
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = clean_text(lines[j])
                cat_city_match = PATTERNS['category_city'].match(next_line)
                if cat_city_match:
                    category = cat_city_match.group(1).strip()
                    city = cat_city_match.group(2).strip()
                    break

            transactions.append({
                'type': 'domestic',
                'date': date,
                'description': desc,
                'amount': amount,
                'category': category,
                'merchant_city': city,
                'original_line': line
            })
            i += 1
            continue

        # Look for FX transactions (more complex)
        fx_match = PATTERNS['fx_main'].search(line)
        if fx_match:
            date, desc, orig_amount, brl_amount = fx_match.groups()

            # Look for FX details in following lines
            fx_rate, iof, currency, usd_amount = '', '', 'USD', ''
            city = ''

            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = clean_text(lines[j])

                # Look for city and currency info
                city_match = PATTERNS['fx_city'].match(next_line)
                if city_match:
                    city = city_match.group(1).strip()
                    currency = city_match.group(3)
                    usd_amount = city_match.group(4)

                # Look for FX rate
                rate_match = PATTERNS['fx_rate'].search(next_line)
                if rate_match:
                    fx_rate = rate_match.group(1)

            transactions.append({
                'type': 'fx',
                'date': date,
                'description': desc,
                'amount': brl_amount,
                'category': 'FX',
                'merchant_city': city,
                'fx_rate': fx_rate,
                'amount_orig': orig_amount,
                'currency_orig': currency,
                'amount_usd': usd_amount,
                'original_line': line
            })
            i += 1
            continue

        i += 1

    return transactions

def extract_from_text_blocks(text: str) -> list[dict[str, str]]:
    """Extract transactions from complex text blocks"""
    transactions = []

    # Split text into paragraphs and process each
    paragraphs = text.split('\n\n')

    for paragraph in paragraphs:
        lines = [line.strip() for line in paragraph.split('\n') if line.strip()]
        if not lines:
            continue

        # Extract transactions from this block
        block_transactions = find_transaction_blocks(lines)
        transactions.extend(block_transactions)

    return transactions

def extract_advanced_text(pdf_path: Path) -> list[dict[str, str]]:
    """Advanced text extraction for complex Itaú PDFs"""
    all_transactions = []
    card_number = "0000"

    with pdfplumber.open(str(pdf_path)) as pdf:
        # First pass: extract card number
        for page in pdf.pages:
            text = page.extract_text() or ""
            card_match = PATTERNS['card'].search(text)
            if card_match:
                card_number = card_match.group(1)
                break

        print(f"Extracted card number: {card_number}")

        # Second pass: extract transactions
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"Processing page {page_num}...")

            text = page.extract_text() or ""

            # Method 1: Try table extraction first
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        if row and len(row) >= 3:
                            # Try to parse as transaction
                            if re.match(r'\d{1,2}/\d{1,2}', str(row[0] or '')):
                                date = str(row[0] or '')
                                desc = str(row[1] or '')
                                amount = str(row[2] or '')

                                if re.search(r'\d{1,3}(?:\.\d{3})*,\d{2}', amount):
                                    all_transactions.append({
                                        'type': 'table',
                                        'date': date,
                                        'description': desc,
                                        'amount': amount,
                                        'category': '',
                                        'merchant_city': '',
                                        'card_last4': card_number
                                    })

            # Method 2: Advanced text extraction
            text_transactions = extract_from_text_blocks(text)
            for tx in text_transactions:
                tx['card_last4'] = card_number
            all_transactions.extend(text_transactions)

    # Deduplicate transactions
    unique_transactions = []
    seen_signatures = set()

    for tx in all_transactions:
        # Create signature for deduplication
        signature = f"{tx['date']}|{tx['description'][:20]}|{tx['amount']}"
        if signature not in seen_signatures:
            seen_signatures.add(signature)
            unique_transactions.append(tx)

    print(f"Found {len(all_transactions)} total, {len(unique_transactions)} unique transactions")

    return unique_transactions

def main():
    parser = argparse.ArgumentParser(
        description="Advanced text extraction for complex Itaú PDFs"
    )
    parser.add_argument("pdf", type=Path, help="Input PDF file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output CSV file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: PDF file {args.pdf} not found")
        return 1

    print(f"Processing {args.pdf} with advanced text extraction...")

    transactions = extract_advanced_text(args.pdf)

    if args.verbose:
        print("\nExtracted transactions:")
        for i, tx in enumerate(transactions[:10], 1):
            print(f"  {i}. {tx['date']} - {tx['description'][:40]}... - {tx['amount']} ({tx.get('merchant_city', 'no city')})")
        if len(transactions) > 10:
            print(f"  ... and {len(transactions) - 10} more")

    # Save to CSV
    if transactions:
        fieldnames = ['date', 'description', 'amount', 'category', 'merchant_city', 'type', 'card_last4']
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            for tx in transactions:
                writer.writerow({k: tx.get(k, '') for k in fieldnames})

    print(f"✅ Saved {len(transactions)} transactions to {args.output}")

    return 0

if __name__ == "__main__":
    exit(main())
