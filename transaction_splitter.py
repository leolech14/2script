#!/usr/bin/env python3
"""
transaction_splitter.py - Split concatenated transactions into individual ones
"""

import csv
import re
from pathlib import Path
from typing import List, Dict, Optional
import argparse

def decomma(amount_str: str) -> float:
    """Convert Brazilian amount to float"""
    if not amount_str:
        return 0.0
    clean = re.sub(r"[^\d,\.\-]", "", amount_str.replace(" ", ""))
    clean = clean.replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except:
        return 0.0

def extract_card_from_description(desc: str) -> Optional[str]:
    """Extract card number from descriptions with patterns like 'final 6853'"""
    patterns = [
        r'final (\d{4})',
        r'cart[ãa]o.*?(\d{4})',
        r'\(final (\d{4})\)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, desc, re.I)
        if match:
            return match.group(1)
    return None

def split_transaction_line(desc: str, amount: str, date: str) -> List[Dict[str, str]]:
    """Split concatenated transaction line into individual transactions"""
    transactions = []
    
    # Pattern 1: Date + Description + Amount sequences
    # Example: "RECARGAPAY *LEONA11/12 14,96 07/04 SumUp *Servizio TAXI"
    
    # Look for date patterns in the middle of description
    date_pattern = r'(\d{1,2}/\d{1,2})'
    amount_pattern = r'(\d{1,3}(?:\.\d{3})*,\d{2})'
    
    # Split by embedded dates
    parts = re.split(r'\s+(\d{1,2}/\d{1,2})\s+', desc)
    
    if len(parts) > 1:
        # First transaction (before first embedded date)
        if parts[0].strip():
            # Look for amount in the first part
            first_amount_match = re.search(amount_pattern, parts[0])
            if first_amount_match:
                first_amount = first_amount_match.group(1)
                first_desc = parts[0].replace(first_amount, '').strip()
                transactions.append({
                    'date': date,
                    'description': first_desc,
                    'amount': first_amount
                })
        
        # Process embedded transactions
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                embedded_date = parts[i]
                embedded_desc = parts[i + 1].strip()
                
                # Look for amount in description
                amount_match = re.search(amount_pattern, embedded_desc)
                if amount_match:
                    embedded_amount = amount_match.group(1)
                    clean_desc = embedded_desc.replace(embedded_amount, '').strip()
                else:
                    # Use the main amount for last transaction
                    embedded_amount = amount
                    clean_desc = embedded_desc
                
                transactions.append({
                    'date': embedded_date,
                    'description': clean_desc,
                    'amount': embedded_amount
                })
    
    # Pattern 2: Multiple amounts in description
    # Example: "APPLE.COM/BILL 99,90 22/04 FARMACIA SAO JOAO 01/06"
    elif re.search(r'\d+,\d{2}.*?\d{1,2}/\d{1,2}', desc):
        # Split by amount + date pattern
        parts = re.split(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,2}/\d{1,2})', desc)
        
        if len(parts) >= 4:
            # First transaction
            transactions.append({
                'date': date,
                'description': parts[0].strip(),
                'amount': parts[1]
            })
            
            # Second transaction  
            transactions.append({
                'date': parts[2],
                'description': parts[3].strip(),
                'amount': amount  # Use main amount
            })
    
    # If no splitting possible, return original
    if not transactions:
        transactions.append({
            'date': date,
            'description': desc,
            'amount': amount
        })
    
    return transactions

def normalize_date(date_str: str, ref_year: int = 2025) -> str:
    """Convert DD/MM to YYYY-MM-DD"""
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
    """Basic transaction classification"""
    desc_upper = description.upper()
    
    if "PAGAMENTO" in desc_upper or "7117" in desc_upper:
        return "PAGAMENTO"
    elif any(k in desc_upper for k in ["FARMAC", "DROG", "PANVEL"]):
        return "FARMÁCIA"
    elif any(k in desc_upper for k in ["APPLE", "MERCADO"]):
        return "DIVERSOS"
    elif any(k in desc_upper for k in ["SUPERMERC", "MERCADO"]):
        return "SUPERMERCADO"
    elif any(k in desc_upper for k in ["EUR", "USD"]) or any(city in desc_upper for city in ["ROMA", "MILANO", "MADRID"]):
        return "FX"
    else:
        return "DIVERSOS"

def process_csv(input_file: Path, output_file: Path):
    """Process CSV and split concatenated transactions"""
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)
    
    split_transactions = []
    
    for row in rows:
        # Split the transaction
        splits = split_transaction_line(
            row['description'], 
            row['amount'], 
            row['date']
        )
        
        for split in splits:
            # Extract card number if available
            card = extract_card_from_description(split['description']) or "0000"
            
            # Create new transaction
            new_tx = {
                'card_last4': card,
                'post_date': normalize_date(split['date']),
                'desc_raw': split['description'],
                'amount_brl': split['amount'],
                'installment_seq': '0',
                'installment_tot': '0', 
                'fx_rate': '0,00',
                'iof_brl': '0,00',
                'category': classify_transaction(split['description']),
                'merchant_city': '',
                'ledger_hash': '',
                'prev_bill_amount': '0,00',
                'interest_amount': '0,00',
                'amount_orig': '0,00',
                'currency_orig': '',
                'amount_usd': '0,00'
            }
            split_transactions.append(new_tx)
    
    # Write output
    fieldnames = [
        'card_last4', 'post_date', 'desc_raw', 'amount_brl',
        'installment_seq', 'installment_tot', 'fx_rate', 'iof_brl',
        'category', 'merchant_city', 'ledger_hash', 'prev_bill_amount',
        'interest_amount', 'amount_orig', 'currency_orig', 'amount_usd'
    ]
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(split_transactions)
    
    print(f"✅ Split {len(rows)} transactions into {len(split_transactions)} individual transactions")
    
    # Show sample splits
    print(f"\nSample splits:")
    for i, (orig, split) in enumerate(zip(rows[:3], [splits[:2] for splits in [split_transaction_line(r['description'], r['amount'], r['date']) for r in rows[:3]]])):
        print(f"{i+1}. Original: {orig['description']}")
        for j, s in enumerate(split):
            print(f"   -> {j+1}. {s['date']} {s['description']} {s['amount']}")
        print()

def main():
    parser = argparse.ArgumentParser(description='Split concatenated transactions')
    parser.add_argument('input_csv', help='Input CSV file')
    parser.add_argument('-o', '--output', default='split_transactions.csv', help='Output CSV file')
    
    args = parser.parse_args()
    
    input_path = Path(args.input_csv)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return 1
    
    process_csv(input_path, output_path)
    return 0

if __name__ == '__main__':
    exit(main())
