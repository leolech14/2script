#!/usr/bin/env python3
"""
test_table_extraction.py – Test script for table extraction system
Validates that table extraction produces better results than flat text.
"""

import argparse
import csv
import subprocess
import tempfile
from pathlib import Path


def run_extraction_method(pdf_path: Path, method: str) -> tuple[Path, int]:
    """Run extraction method and return output path and transaction count"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        temp_output = Path(f.name)

    try:
        if method == 'table':
            # Use table extraction
            result = subprocess.run([
                'python', 'pdf_table_extractor.py', str(pdf_path),
                '-o', str(temp_output)
            ], capture_output=True, text=True)
        elif method == 'flat':
            # Use flat text (simulate with current script.py)
            result = subprocess.run([
                'python', 'script.py', str(pdf_path),
                '-o', str(temp_output.parent)
            ], capture_output=True, text=True)
            # Rename output to expected name
            expected_output = temp_output.parent / f"{pdf_path.stem}_parsed.csv"
            if expected_output.exists():
                expected_output.rename(temp_output)
        else:
            raise ValueError(f"Unknown method: {method}")

        if result.returncode != 0:
            print(f"Error running {method} extraction:")
            print(result.stderr)
            return temp_output, 0

        # Count transactions
        if temp_output.exists():
            with open(temp_output, encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # Skip header
                count = sum(1 for row in reader)
            return temp_output, count
        else:
            return temp_output, 0

    except Exception as e:
        print(f"Error in {method} extraction: {e}")
        return temp_output, 0

def analyze_merchant_cities(csv_path: Path) -> dict[str, int]:
    """Analyze merchant city extraction quality"""
    stats = {
        'total_transactions': 0,
        'has_merchant_city': 0,
        'empty_merchant_city': 0,
        'valid_cities': []
    }

    if not csv_path.exists():
        return stats

    try:
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                stats['total_transactions'] += 1

                # Check merchant city field (different field names possible)
                city = row.get('merchant_city', '') or row.get('cidade', '') or row.get('city', '')

                if city and city.strip():
                    stats['has_merchant_city'] += 1
                    stats['valid_cities'].append(city.strip())
                else:
                    stats['empty_merchant_city'] += 1

    except Exception as e:
        print(f"Error analyzing {csv_path}: {e}")

    return stats

def compare_extractions(pdf_path: Path) -> dict[str, any]:
    """Compare table vs flat extraction methods"""
    print(f"\n🔍 Testing extraction methods on {pdf_path.name}")
    print("=" * 60)

    results = {}

    # Test table extraction
    print("Testing table extraction...")
    table_output, table_count = run_extraction_method(pdf_path, 'table')
    table_stats = analyze_merchant_cities(table_output)

    results['table'] = {
        'transaction_count': table_count,
        'output_path': table_output,
        'merchant_city_stats': table_stats
    }

    # Test flat extraction
    print("Testing flat extraction...")
    flat_output, flat_count = run_extraction_method(pdf_path, 'flat')
    flat_stats = analyze_merchant_cities(flat_output)

    results['flat'] = {
        'transaction_count': flat_count,
        'output_path': flat_output,
        'merchant_city_stats': flat_stats
    }

    return results

def print_comparison_results(results: dict[str, any], pdf_name: str):
    """Print detailed comparison results"""
    table_data = results['table']
    flat_data = results['flat']

    print(f"\n📊 COMPARISON RESULTS: {pdf_name}")
    print("=" * 60)

    # Transaction counts
    print("📈 Transaction Extraction:")
    print(f"  Table method: {table_data['transaction_count']} transactions")
    print(f"  Flat method:  {flat_data['transaction_count']} transactions")

    count_diff = table_data['transaction_count'] - flat_data['transaction_count']
    if count_diff > 0:
        print(f"  ✅ Table extracted {count_diff} more transactions")
    elif count_diff < 0:
        print(f"  ⚠️ Flat extracted {abs(count_diff)} more transactions")
    else:
        print("  ➡️ Same number of transactions")

    # Merchant city analysis
    print("\n🏙️ Merchant City Extraction:")

    table_stats = table_data['merchant_city_stats']
    flat_stats = flat_data['merchant_city_stats']

    if table_stats['total_transactions'] > 0:
        table_city_rate = (table_stats['has_merchant_city'] / table_stats['total_transactions']) * 100
        print(f"  Table method: {table_stats['has_merchant_city']}/{table_stats['total_transactions']} ({table_city_rate:.1f}%) with cities")

    if flat_stats['total_transactions'] > 0:
        flat_city_rate = (flat_stats['has_merchant_city'] / flat_stats['total_transactions']) * 100
        print(f"  Flat method:  {flat_stats['has_merchant_city']}/{flat_stats['total_transactions']} ({flat_city_rate:.1f}%) with cities")

    # Sample cities
    if table_stats['valid_cities']:
        unique_table_cities = list(set(table_stats['valid_cities'][:10]))
        print(f"  Table cities sample: {', '.join(unique_table_cities[:5])}")

    if flat_stats['valid_cities']:
        unique_flat_cities = list(set(flat_stats['valid_cities'][:10]))
        print(f"  Flat cities sample:  {', '.join(unique_flat_cities[:5])}")

    # Overall assessment
    print("\n🏆 ASSESSMENT:")

    table_score = 0
    flat_score = 0

    # Score by transaction count
    if table_data['transaction_count'] > flat_data['transaction_count']:
        table_score += 1
        print("  ✅ Table method extracts more transactions")
    elif flat_data['transaction_count'] > table_data['transaction_count']:
        flat_score += 1
        print("  ✅ Flat method extracts more transactions")

    # Score by merchant city extraction
    if (table_stats['total_transactions'] > 0 and flat_stats['total_transactions'] > 0):
        table_city_rate = table_stats['has_merchant_city'] / table_stats['total_transactions']
        flat_city_rate = flat_stats['has_merchant_city'] / flat_stats['total_transactions']

        if table_city_rate > flat_city_rate:
            table_score += 1
            print("  ✅ Table method extracts more merchant cities")
        elif flat_city_rate > table_city_rate:
            flat_score += 1
            print("  ✅ Flat method extracts more merchant cities")

    # Final recommendation
    if table_score > flat_score:
        print("  🥇 RECOMMENDATION: Use table extraction method")
    elif flat_score > table_score:
        print("  🥇 RECOMMENDATION: Use flat extraction method")
    else:
        print("  🤝 RECOMMENDATION: Both methods perform similarly")

def main():
    parser = argparse.ArgumentParser(
        description="Test and compare PDF extraction methods"
    )
    parser.add_argument("pdf", type=Path, help="PDF file to test")
    parser.add_argument("--keep-outputs", action="store_true",
                       help="Keep extraction output files for manual review")

    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: PDF file {args.pdf} not found")
        return 1

    # Run comparison
    results = compare_extractions(args.pdf)

    # Print results
    print_comparison_results(results, args.pdf.name)

    # Cleanup or keep outputs
    if args.keep_outputs:
        print("\n📁 Output files saved:")
        print(f"  Table: {results['table']['output_path']}")
        print(f"  Flat:  {results['flat']['output_path']}")
    else:
        # Clean up temp files
        for method in ['table', 'flat']:
            output_path = results[method]['output_path']
            if output_path.exists():
                output_path.unlink()

    return 0

if __name__ == "__main__":
    exit(main())
