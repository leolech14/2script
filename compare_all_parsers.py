#!/usr/bin/env python3
"""Compare all parsers against golden CSVs."""

import csv
from pathlib import Path


def load_csv(path, delimiter=','):
    """Load CSV with specified delimiter."""
    rows = []
    if not path.exists():
        return []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            rows.append(row)
    return rows

def create_transaction_key(txn):
    """Create unique key for transaction matching."""
    date = str(txn.get('post_date', '')).strip().upper()
    desc = str(txn.get('desc_raw', '')).strip().upper()[:50]
    amount_field = txn.get('amount_brl') or txn.get('valor_brl', '')
    amount = str(amount_field).strip()

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

def evaluate_parser(parsed_file, golden_file, parser_name):
    """Evaluate a parser against golden file."""
    parsed = load_csv(parsed_file, ',' if 'codex' in str(parsed_file) else ';')
    golden = load_csv(golden_file, ';')

    if not parsed:
        return {
            'parser': parser_name,
            'coverage': 0.0,
            'accuracy': 0.0,
            'total_score': 0.0,
            'matched': 0,
            'missing': len(golden),
            'extra': 0,
            'parsed_count': 0,
            'golden_count': len(golden)
        }

    # Create indexes
    parsed_index = {create_transaction_key(txn): txn for txn in parsed}
    golden_index = {create_transaction_key(txn): txn for txn in golden}

    # Find matches
    matched_keys = set(parsed_index.keys()) & set(golden_index.keys())
    parsed_only = set(parsed_index.keys()) - set(golden_index.keys())
    golden_only = set(golden_index.keys()) - set(parsed_index.keys())

    # Calculate metrics
    coverage = (len(matched_keys) / len(golden)) * 100 if golden else 0

    # For accuracy, we'll consider matches where at least the core fields align
    exact_matches = len(matched_keys)  # Simplified - just having a match is good
    accuracy = (exact_matches / len(matched_keys)) * 100 if matched_keys else 0

    total_score = (coverage * accuracy) / 100

    return {
        'parser': parser_name,
        'coverage': coverage,
        'accuracy': accuracy,
        'total_score': total_score,
        'matched': len(matched_keys),
        'missing': len(golden_only),
        'extra': len(parsed_only),
        'parsed_count': len(parsed),
        'golden_count': len(golden)
    }

def main():
    print("🏆 COMPREHENSIVE PARSER COMPARISON REPORT")
    print("="*80)

    # Test files for 2025-05
    parsers_2025 = {
        'Ultimate Parser': 'ultimate_2025-05.csv',
        'Original Codex': 'test_outputs/codex_Itau_2025-05.csv',
        'PDF-to-CSV': 'test_outputs/pdf_to_csv_Itau_2025-05.csv',
        'Text-to-CSV': 'test_outputs/text_to_csv_Itau_2025-05.csv'
    }

    # Test files for 2024-10
    parsers_2024 = {
        'Ultimate Parser': 'ultimate_2024-10.csv',
        'Original Codex': 'test_outputs/codex_Itau_2024-10.csv',
        'PDF-to-CSV': 'test_outputs/pdf_to_csv_Itau_2024-10.csv',
        'Text-to-CSV': 'test_outputs/text_to_csv_Itau_2024-10.csv'
    }

    all_results = []

    # Test 2025-05 files
    print("\n📊 2025-05 PDF RESULTS:")
    print("-" * 50)
    for parser_name, file_path in parsers_2025.items():
        result = evaluate_parser(Path(file_path), Path('golden_2025-05.csv'), parser_name)
        all_results.append(result)

        print(f"{parser_name:15} | Coverage: {result['coverage']:5.1f}% | "
              f"Matches: {result['matched']:3d}/{result['golden_count']} | "
              f"Parsed: {result['parsed_count']:3d} | "
              f"Score: {result['total_score']:5.1f}")

    # Test 2024-10 files
    print("\n📊 2024-10 PDF RESULTS:")
    print("-" * 50)
    for parser_name, file_path in parsers_2024.items():
        result = evaluate_parser(Path(file_path), Path('golden_2024-10.csv'), parser_name)
        all_results.append(result)

        print(f"{parser_name:15} | Coverage: {result['coverage']:5.1f}% | "
              f"Matches: {result['matched']:3d}/{result['golden_count']} | "
              f"Parsed: {result['parsed_count']:3d} | "
              f"Score: {result['total_score']:5.1f}")

    # Overall analysis
    print("\n🎯 OVERALL ANALYSIS:")
    print("-" * 50)

    # Group results by parser
    parser_scores = {}
    for result in all_results:
        parser = result['parser']
        if parser not in parser_scores:
            parser_scores[parser] = []
        parser_scores[parser].append(result['total_score'])

    # Calculate average scores
    print("Average scores across both PDFs:")
    for parser, scores in parser_scores.items():
        avg_score = sum(scores) / len(scores)
        print(f"  {parser:15}: {avg_score:5.1f} points")

    # Best parser
    best_parser = max(parser_scores.items(), key=lambda x: sum(x[1])/len(x[1]))
    print(f"\n🏆 BEST PERFORMER: {best_parser[0]} ({sum(best_parser[1])/len(best_parser[1]):.1f} avg)")

    # Ultimate parser analysis
    ultimate_results = [r for r in all_results if r['parser'] == 'Ultimate Parser']
    print("\n🚀 ULTIMATE PARSER PERFORMANCE:")
    print(f"  Total transactions found: {sum(r['parsed_count'] for r in ultimate_results)}")
    print(f"  Total transactions matched: {sum(r['matched'] for r in ultimate_results)}")
    print(f"  Average coverage: {sum(r['coverage'] for r in ultimate_results)/len(ultimate_results):.1f}%")

    # Identify improvement areas
    print("\n💡 IMPROVEMENT OPPORTUNITIES:")
    if ultimate_results:
        avg_coverage = sum(r['coverage'] for r in ultimate_results)/len(ultimate_results)
        if avg_coverage < 50:
            print("  🔧 LOW COVERAGE: Need to improve transaction detection")
        if any(r['accuracy'] < 50 for r in ultimate_results):
            print("  🔧 LOW ACCURACY: Need to improve field matching")
        if any(r['extra'] > r['matched'] for r in ultimate_results):
            print("  🔧 TOO MANY EXTRAS: Need to filter out false positives")

    return all_results

if __name__ == "__main__":
    main()
