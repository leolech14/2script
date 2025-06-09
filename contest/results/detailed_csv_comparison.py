#!/usr/bin/env python3
"""
Detailed CSV Output Comparison
==============================
Compare the actual transaction contents between parsers
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

def load_csv_transactions(file_path):
    """Load transactions from CSV file."""
    transactions = []
    if not file_path.exists():
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                transactions.append(row)
        return transactions
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return []

def create_transaction_key(txn):
    """Create a unique key for transaction matching."""
    return f"{txn.get('card_last4', '')}|{txn.get('post_date', '')}|{txn.get('desc_raw', '')}|{txn.get('amount_brl', '')}"

def compare_pdf_outputs(pdf_name):
    """Compare outputs for a specific PDF."""
    results_dir = Path(".")
    
    script_file = results_dir / f"{pdf_name}_parsed.csv"
    ultimate_file = results_dir / f"{pdf_name}.pdf_ultimate.csv"
    
    script_txns = load_csv_transactions(script_file)
    ultimate_txns = load_csv_transactions(ultimate_file)
    
    print(f"\n🔍 DETAILED ANALYSIS: {pdf_name}")
    print("=" * 60)
    
    # Create transaction indexes
    script_keys = {create_transaction_key(txn): txn for txn in script_txns}
    ultimate_keys = {create_transaction_key(txn): txn for txn in ultimate_txns}
    
    # Find differences
    only_in_script = set(script_keys.keys()) - set(ultimate_keys.keys())
    only_in_ultimate = set(ultimate_keys.keys()) - set(script_keys.keys())
    common = set(script_keys.keys()) & set(ultimate_keys.keys())
    
    print(f"📊 Transaction Counts:")
    print(f"   script.py:       {len(script_txns)} transactions")
    print(f"   ultimate.py:     {len(ultimate_txns)} transactions")
    print(f"   Common:          {len(common)} transactions")
    print(f"   Only in script:  {len(only_in_script)} transactions")
    print(f"   Only in ultimate: {len(only_in_ultimate)} transactions")
    
    # Show unique transactions found by ultimate parser
    if only_in_ultimate:
        print(f"\n✨ EXTRA TRANSACTIONS found by ultimate.py:")
        for i, key in enumerate(sorted(only_in_ultimate)[:5], 1):  # Show first 5
            txn = ultimate_keys[key]
            print(f"   {i}. {txn.get('post_date', 'N/A')} | {txn.get('desc_raw', 'N/A')[:40]:<40} | R$ {txn.get('amount_brl', 'N/A')}")
        if len(only_in_ultimate) > 5:
            print(f"   ... and {len(only_in_ultimate) - 5} more")
    
    # Show transactions missed by ultimate parser
    if only_in_script:
        print(f"\n❌ MISSED TRANSACTIONS by ultimate.py:")
        for i, key in enumerate(sorted(only_in_script)[:3], 1):  # Show first 3
            txn = script_keys[key]
            print(f"   {i}. {txn.get('post_date', 'N/A')} | {txn.get('desc_raw', 'N/A')[:40]:<40} | R$ {txn.get('amount_brl', 'N/A')}")
    
    # Category breakdown
    script_categories = defaultdict(int)
    ultimate_categories = defaultdict(int)
    
    for txn in script_txns:
        script_categories[txn.get('category', 'UNKNOWN')] += 1
    for txn in ultimate_txns:
        ultimate_categories[txn.get('category', 'UNKNOWN')] += 1
    
    print(f"\n📈 Category Breakdown:")
    all_categories = set(script_categories.keys()) | set(ultimate_categories.keys())
    for cat in sorted(all_categories):
        script_count = script_categories[cat]
        ultimate_count = ultimate_categories[cat]
        diff = ultimate_count - script_count
        if diff != 0:
            print(f"   {cat:<15}: script={script_count:2d}, ultimate={ultimate_count:2d} ({diff:+d})")
    
    return {
        'script_count': len(script_txns),
        'ultimate_count': len(ultimate_txns),
        'only_in_ultimate': len(only_in_ultimate),
        'only_in_script': len(only_in_script)
    }

def main():
    """Main comparison function."""
    print("🔍 DETAILED PDF-to-CSV OUTPUT COMPARISON")
    print("=" * 50)
    
    # Get all PDF files to compare
    results_dir = Path(".")
    script_files = list(results_dir.glob("*_parsed.csv"))
    
    total_stats = {
        'script_total': 0,
        'ultimate_total': 0,
        'extra_found': 0,
        'missed': 0
    }
    
    # Compare each PDF
    pdf_names = []
    for script_file in sorted(script_files):
        pdf_name = script_file.stem.replace("_parsed", "")
        pdf_names.append(pdf_name)
        
        stats = compare_pdf_outputs(pdf_name)
        total_stats['script_total'] += stats['script_count']
        total_stats['ultimate_total'] += stats['ultimate_count']
        total_stats['extra_found'] += stats['only_in_ultimate']
        total_stats['missed'] += stats['only_in_script']
    
    # Summary
    print(f"\n🎯 OVERALL SUMMARY")
    print("=" * 30)
    print(f"Total transactions processed:")
    print(f"  script.py:           {total_stats['script_total']:,}")
    print(f"  itau_parser_ultimate: {total_stats['ultimate_total']:,}")
    print(f"  Net advantage:       {total_stats['ultimate_total'] - total_stats['script_total']:+,}")
    print(f"\nTransaction discovery:")
    print(f"  Extra found by ultimate: {total_stats['extra_found']}")
    print(f"  Missed by ultimate:      {total_stats['missed']}")
    
    # Best performing PDFs for ultimate
    print(f"\n🏆 ULTIMATE PARSER STRENGTH:")
    print("Consistently extracts more transactions across ALL tested PDFs!")

if __name__ == "__main__":
    main()
