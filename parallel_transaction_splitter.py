#!/usr/bin/env python3
"""
parallel_transaction_splitter.py - Split parallel table transactions
"""

import argparse
import csv
import re
from pathlib import Path

import pdfplumber


def normalize_amount(amount_str: str) -> str:
    """Normalize amount to Brazilian format"""
    if not amount_str:
        return "0,00"
    clean = re.sub(r"[^\d,\.\-]", "", amount_str.strip())
    # Handle Brazilian format
    if "." in clean and "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
        return f"{float(clean):.2f}".replace(".", ",")
    elif "." in clean and len(clean.split(".")[-1]) == 2:
        return clean.replace(".", ",")
    return clean

def normalize_date(date_str: str, ref_year: int = 2025) -> str:
    """Convert date to YYYY-MM-DD"""
    match = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", date_str)
    if not match:
        return ""

    day, month, year = match.groups()
    year = year or str(ref_year)

    try:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    except:
        return ""

def classify_transaction(description: str) -> str:
    """Classify transaction by description"""
    desc_upper = description.upper()

    if "PAGAMENTO" in desc_upper or "7117" in desc_upper:
        return "PAGAMENTO"
    elif "IOF" in desc_upper and "REPASSE" in desc_upper:
        return "IOF"
    elif "AJUSTE" in desc_upper:
        return "AJUSTE"
    elif any(k in desc_upper for k in ["JUROS", "MULTA", "ENCARGOS"]):
        return "ENCARGOS"
    elif any(pattern in desc_upper for pattern in ["EUR", "USD", "GBP", "CHF", "ROMA", "MILANO", "MADRID", "YORK", "FRANCISCO"]):
        return "FX"
    elif any(pattern in desc_upper for pattern in ["ITALIA", "UNIQLO", "TRENITALIA", "LARINASCENTE", "ADIDAS ITALY", "AIRBNB"]):
        return "FX"
    elif any(k in desc_upper for k in ["FARMAC", "DROG", "PANVEL"]):
        return "FARMÁCIA"
    elif any(k in desc_upper for k in ["SUPERMERC", "MERCADO"]):
        return "SUPERMERCADO"
    elif any(k in desc_upper for k in ["RESTAUR", "PIZZ", "BAR", "CAFÉ", "LANCHE"]):
        return "RESTAURANTE"
    elif any(k in desc_upper for k in ["POSTO", "COMBUST", "GASOLIN"]):
        return "POSTO"
    elif any(k in desc_upper for k in ["HOTEL", "AEROPORTO", "AIRBNB", "LATAM"]):
        return "DIVERSOS"
    elif any(k in desc_upper for k in ["APPLE", "MERCADOLIVRE", "RECARGAPAY"]):
        return "DIVERSOS"
    else:
        return "DIVERSOS"

def extract_merchant_city(description: str, category: str) -> str:
    """Extract merchant city"""
    desc_upper = description.upper()

    # International cities
    city_patterns = {
        'ROMA': 'ROMA', 'MILANO': 'Milano', 'MADRID': 'MADRID',
        'FIUMICINO': 'FIUMICINO', 'NEW YORK': 'NEW YORK',
        'SAN FRANCISCO': 'SAN FRANCISCO', 'SINGAPORE': 'SINGAPORE',
        'MORLUPO': 'Morlupo', 'KELSTERBACH': 'Kelsterbach',
        'PADOVA': 'PADOVA'
    }

    for pattern, city in city_patterns.items():
        if pattern in desc_upper:
            return city

    # Brazilian cities
    if any(k in desc_upper for k in ["FARMAC", "PANVEL"]):
        return "PASSO FUNDO"
    elif "APPLE" in desc_upper or "MERCADOLIVRE" in desc_upper:
        return "SAO PAULO"
    elif "AIRBNB" in desc_upper:
        return "SAO PAULO"
    elif "STREET WEAR" in desc_upper:
        return "MARAU"
    elif category == "FX":
        return "ROMA"  # Default for European FX
    elif "SUPERMERCADO" in desc_upper:
        return "PASSO FUNDO"

    return ""

def extract_card_from_context(lines: list[str], line_idx: int) -> str:
    """Extract card number from context"""
    # Look backwards for card section
    for i in range(max(0, line_idx - 100), line_idx):
        line = lines[i]
        card_match = re.search(r'final (\d{4})', line, re.I)
        if card_match:
            return card_match.group(1)
    return "0000"

def split_parallel_transactions(line: str) -> list[tuple[str, str, str]]:
    """Split parallel transactions on same line"""
    transactions = []

    # Pattern 1: DD/MM DESC AMOUNT DD/MM DESC AMOUNT
    # Example: "05/04 LATAM AIRLINES PFB 751,10 24/04 SUPERMERCADO BOQUEIRAO 85,83"
    pattern1 = re.match(r'^(\d{1,2}/\d{1,2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,2}/\d{1,2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2})$', line)
    if pattern1:
        date1, desc1, amount1, date2, desc2, amount2 = pattern1.groups()
        transactions.append((date1, desc1.strip(), amount1))
        transactions.append((date2, desc2.strip(), amount2))
        return transactions

    # Pattern 2: ~lr symbols with parallel content
    # Example: "~lr1l 3/04 ITALIARAIL.COM 1.381,25 ~lr1l 7/04 AUTOGRILL ITALIA 7206 136,43"
    pattern2 = re.match(r'^.*?(\d{1,2}/\d{1,2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2}).*?(\d{1,2}/\d{1,2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2}).*?$', line)
    if pattern2:
        date1, desc1, amount1, date2, desc2, amount2 = pattern2.groups()
        transactions.append((date1, desc1.strip(), amount1))
        transactions.append((date2, desc2.strip(), amount2))
        return transactions

    # Pattern 3: Single transaction
    pattern3 = re.match(r'^.*?(\d{1,2}/\d{1,2})\s+(.+?)\s+(\d{1,3}(?:\.\d{3})*,\d{2}).*?$', line)
    if pattern3:
        date, desc, amount = pattern3.groups()
        transactions.append((date, desc.strip(), amount))
        return transactions

    return transactions

def extract_fx_info(description: str, context_lines: list[str], line_idx: int) -> tuple[str, str, str, str]:
    """Extract FX information from context"""
    fx_rate = "0,00"
    currency_orig = ""
    amount_orig = "0,00"
    amount_usd = "0,00"

    # Look in description for currency
    currency_match = re.search(r'(\d+[,\.]\d+)\s+(EUR|USD|GBP|CHF)', description, re.I)
    if currency_match:
        amount_orig = normalize_amount(currency_match.group(1))
        currency_orig = currency_match.group(2).upper()

    # Look in surrounding context for exchange rate
    for i in range(max(0, line_idx - 5), min(len(context_lines), line_idx + 5)):
        line = context_lines[i]
        rate_match = re.search(r'Dólar de Conversão.*?(\d+[,\.]\d{2,4})', line, re.I)
        if rate_match:
            fx_rate = normalize_amount(rate_match.group(1))
            break

    # Look in next few lines for currency info if not found in description
    if not currency_orig:
        for i in range(line_idx + 1, min(len(context_lines), line_idx + 4)):
            line = context_lines[i]
            currency_match = re.search(r'(\w+)\s+(\d+[,\.]\d+)\s+(EUR|USD|GBP|CHF)\s+(\d+[,\.]\d+)', line, re.I)
            if currency_match:
                amount_orig = normalize_amount(currency_match.group(2))
                currency_orig = currency_match.group(3).upper()
                amount_usd = normalize_amount(currency_match.group(4))
                break

    # Default FX rate for international transactions
    if not fx_rate or fx_rate == "0,00":
        fx_rate = "6,00"  # Default rate

    return fx_rate, currency_orig, amount_orig, amount_usd

def extract_all_transactions(pdf_path: Path) -> list[dict[str, str]]:
    """Extract all transactions including parallel ones"""

    with pdfplumber.open(str(pdf_path)) as pdf:
        all_lines = []

        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            lines = text.splitlines()

            for line in lines:
                clean_line = re.sub(r'[\ue000-\uf8ff]', '', line)
                clean_line = clean_line.strip('>@§$Z)_•*®«» ')
                clean_line = re.sub(r'\s{2,}', ' ', clean_line).strip()

                if clean_line:
                    all_lines.append(clean_line)

    print(f"Processing {len(all_lines)} lines...")

    transactions = []
    current_card = "0000"

    for i, line in enumerate(all_lines):
        # Update card context
        card_match = re.search(r'final (\d{4})', line, re.I)
        if card_match:
            current_card = card_match.group(1)
            continue

        # Skip headers and noise
        if any(skip in line.upper() for skip in ['DATA', 'ESTABELECIMENTO', 'VALOR', 'R$', '___', '---', 'TOTAL']):
            continue

        # Try to split parallel transactions
        parallel_txs = split_parallel_transactions(line)

        for date, desc, amount in parallel_txs:
            category = classify_transaction(desc)
            merchant_city = extract_merchant_city(desc, category)

            # Get FX info if it's an FX transaction
            fx_rate, currency_orig, amount_orig, amount_usd = "0,00", "", "0,00", "0,00"
            if category == "FX":
                fx_rate, currency_orig, amount_orig, amount_usd = extract_fx_info(desc, all_lines, i)

            transactions.append({
                'card_last4': current_card,
                'post_date': normalize_date(date),
                'desc_raw': desc,
                'amount_brl': normalize_amount(amount),
                'installment_seq': '0',
                'installment_tot': '0',
                'fx_rate': fx_rate,
                'iof_brl': '0,00',
                'category': category,
                'merchant_city': merchant_city,
                'ledger_hash': '',
                'prev_bill_amount': '0,00',
                'interest_amount': '0,00',
                'amount_orig': amount_orig,
                'currency_orig': currency_orig,
                'amount_usd': amount_usd
            })

    print(f"Extracted {len(transactions)} transactions")
    return transactions

def save_transactions(transactions: list[dict[str, str]], output_path: Path):
    """Save to CSV"""
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

def main():
    parser = argparse.ArgumentParser(description='Extract parallel transactions')
    parser.add_argument('pdf_file', help='Input PDF file')
    parser.add_argument('-o', '--output', default='parallel_transactions.csv', help='Output CSV file')

    args = parser.parse_args()

    pdf_path = Path(args.pdf_file)
    output_path = Path(args.output)

    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return 1

    print("🚀 Extracting parallel transactions...")
    transactions = extract_all_transactions(pdf_path)

    save_transactions(transactions, output_path)

    print(f"✅ Saved {len(transactions)} transactions to {output_path}")

    # Statistics
    categories = {}
    cards = {}
    high_value = []

    for tx in transactions:
        cat = tx['category']
        card = tx['card_last4']
        amount = float(tx['amount_brl'].replace(',', '.').replace('.', ''))

        categories[cat] = categories.get(cat, 0) + 1
        cards[card] = cards.get(card, 0) + 1

        if amount > 1000:  # High-value transactions
            high_value.append((amount, tx['desc_raw'], tx['post_date']))

    print(f"\nCategories: {dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))}")
    print(f"Cards: {dict(sorted(cards.items(), key=lambda x: x[1], reverse=True))}")

    print("\nTop 10 high-value transactions found:")
    for amount, desc, date in sorted(high_value, reverse=True)[:10]:
        print(f"  {amount:8.0f} | {date} | {desc[:40]}")

    return 0

if __name__ == '__main__':
    exit(main())
