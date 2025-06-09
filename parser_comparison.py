#!/usr/bin/env python3
"""
Parser Comparison Tool
Compares the outputs of all three parsers and shows their differences.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import parser_utils  # NEW: for shared utilities


def load_csv_data(file_path: Path) -> list[dict]:
    """Load CSV data and normalize column names."""
    if not file_path.exists():
        print(f"Warning: File not found: {file_path}")
        return []
    # Use shared utility for loading
    rows = parser_utils.load_csv(file_path, delimiter=";" if file_path.suffix == ".csv" else ",")
    # Normalize column names as before
    normalized = []
    for row in rows:
        normalized_row = {}
        for key, value in row.items():
            key_lower = key.lower()
            if key_lower in ['amount_brl', 'valor_brl']:
                normalized_row['amount'] = value
            elif key_lower in ['desc_raw', 'description']:
                normalized_row['description'] = value
            elif key_lower in ['post_date', 'date']:
                normalized_row['date'] = value
            elif key_lower in ['card_last4']:
                normalized_row['card'] = value
            elif key_lower in ['category', 'categoria_high']:
                normalized_row['category'] = value
            else:
                normalized_row[key] = value
        normalized.append(normalized_row)
    return normalized

def create_transaction_key(row: dict) -> str:
    """Create a unique key for matching transactions across parsers."""
    date = row.get('date', '').strip()
    desc = row.get('description', '').strip()
    amount = row.get('amount', '').strip()
    # Use shared decomma utility for normalization
    if amount:
        try:
            amount_clean = str(float(parser_utils.decomma(amount)))
        except Exception:
            amount_clean = amount
    else:
        amount_clean = '0'
    return f"{date}|{desc}|{amount_clean}"

def analyze_parsers(codex_file: Path, pdf_csv_file: Path, text_csv_file: Path) -> dict:
    """Analyze differences between the three parsers."""

    # Load data from all three parsers
    codex_data = load_csv_data(codex_file)
    pdf_csv_data = load_csv_data(pdf_csv_file)
    text_csv_data = load_csv_data(text_csv_file)

    print("Loaded data:")
    print(f"  Codex: {len(codex_data)} rows")
    print(f"  PDF-to-CSV: {len(pdf_csv_data)} rows")
    print(f"  Text-to-CSV: {len(text_csv_data)} rows")

    # Create transaction indexes
    codex_index = {create_transaction_key(row): row for row in codex_data}
    pdf_csv_index = {create_transaction_key(row): row for row in pdf_csv_data}
    text_csv_index = {create_transaction_key(row): row for row in text_csv_data}

    # Find all unique transaction keys
    all_keys = set(codex_index.keys()) | set(pdf_csv_index.keys()) | set(text_csv_index.keys())

    analysis = {
        "total_unique_transactions": len(all_keys),
        "parser_coverage": {
            "codex": len(codex_index),
            "pdf_to_csv": len(pdf_csv_index),
            "text_to_csv": len(text_csv_index)
        },
        "common_transactions": {
            "all_three": 0,
            "codex_and_pdf": 0,
            "codex_and_text": 0,
            "pdf_and_text": 0,
            "codex_only": 0,
            "pdf_only": 0,
            "text_only": 0
        },
        "sample_transactions": {
            "all_three": [],
            "differences": []
        },
        "field_analysis": defaultdict(lambda: {"codex": 0, "pdf_to_csv": 0, "text_to_csv": 0})
    }

    # Analyze transaction coverage
    for key in all_keys:
        in_codex = key in codex_index
        in_pdf = key in pdf_csv_index
        in_text = key in text_csv_index

        if in_codex and in_pdf and in_text:
            analysis["common_transactions"]["all_three"] += 1
            if len(analysis["sample_transactions"]["all_three"]) < 3:
                analysis["sample_transactions"]["all_three"].append({
                    "key": key,
                    "codex": codex_index[key],
                    "pdf_to_csv": pdf_csv_index[key],
                    "text_to_csv": text_csv_index[key]
                })
        elif in_codex and in_pdf:
            analysis["common_transactions"]["codex_and_pdf"] += 1
        elif in_codex and in_text:
            analysis["common_transactions"]["codex_and_text"] += 1
        elif in_pdf and in_text:
            analysis["common_transactions"]["pdf_and_text"] += 1
        elif in_codex:
            analysis["common_transactions"]["codex_only"] += 1
        elif in_pdf:
            analysis["common_transactions"]["pdf_only"] += 1
        elif in_text:
            analysis["common_transactions"]["text_only"] += 1

    # Analyze field completeness
    for parser_name, data in [("codex", codex_data), ("pdf_to_csv", pdf_csv_data), ("text_to_csv", text_csv_data)]:
        for row in data:
            for field, value in row.items():
                if value and str(value).strip():  # Non-empty field
                    analysis["field_analysis"][field][parser_name] += 1

    return analysis

def print_analysis_report(analysis: dict):
    """Print a comprehensive analysis report."""

    print(f"\n{'='*60}")
    print("PARSER COMPARISON ANALYSIS")
    print(f"{'='*60}")

    print("\n📊 TRANSACTION COVERAGE:")
    total = analysis["total_unique_transactions"]
    coverage = analysis["common_transactions"]

    print(f"  Total unique transactions: {total}")
    print(f"  Found by all three parsers: {coverage['all_three']} ({coverage['all_three']/total*100:.1f}%)")
    print(f"  Found by codex + pdf_to_csv: {coverage['codex_and_pdf']} ({coverage['codex_and_pdf']/total*100:.1f}%)")
    print(f"  Found by codex + text_to_csv: {coverage['codex_and_text']} ({coverage['codex_and_text']/total*100:.1f}%)")
    print(f"  Found by pdf_to_csv + text_to_csv: {coverage['pdf_and_text']} ({coverage['pdf_and_text']/total*100:.1f}%)")
    print(f"  Found only by codex: {coverage['codex_only']} ({coverage['codex_only']/total*100:.1f}%)")
    print(f"  Found only by pdf_to_csv: {coverage['pdf_only']} ({coverage['pdf_only']/total*100:.1f}%)")
    print(f"  Found only by text_to_csv: {coverage['text_only']} ({coverage['text_only']/total*100:.1f}%)")

    print("\n📋 FIELD COMPLETENESS:")
    field_analysis = analysis["field_analysis"]

    all_fields = sorted(field_analysis.keys())
    for field in all_fields:
        stats = field_analysis[field]
        print(f"  {field}:")
        print(f"    Codex: {stats['codex']} rows")
        print(f"    PDF-to-CSV: {stats['pdf_to_csv']} rows")
        print(f"    Text-to-CSV: {stats['text_to_csv']} rows")

    print("\n🔍 SAMPLE COMMON TRANSACTIONS:")
    if analysis["sample_transactions"]["all_three"]:
        for i, sample in enumerate(analysis["sample_transactions"]["all_three"][:2]):
            print(f"  Sample {i+1}:")
            key_parts = sample["key"].split("|")
            print(f"    Date: {key_parts[0]}, Amount: {key_parts[2]}")
            print(f"    Description: {key_parts[1][:50]}...")
            print(f"    Categories: Codex='{sample['codex'].get('category', '')}', "
                  f"PDF='{sample['pdf_to_csv'].get('category', '')}', "
                  f"Text='{sample['text_to_csv'].get('category', '')}'")
    else:
        print("  No transactions found by all three parsers")

    print("\n📈 PARSER EFFECTIVENESS:")
    parsers = analysis["parser_coverage"]
    print(f"  Codex: {parsers['codex']} transactions ({parsers['codex']/total*100:.1f}% coverage)")
    print(f"  PDF-to-CSV: {parsers['pdf_to_csv']} transactions ({parsers['pdf_to_csv']/total*100:.1f}% coverage)")
    print(f"  Text-to-CSV: {parsers['text_to_csv']} transactions ({parsers['text_to_csv']/total*100:.1f}% coverage)")

    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    best_coverage = max(parsers.values())
    best_parser = [name for name, count in parsers.items() if count == best_coverage][0]
    print(f"  • {best_parser.upper()} has the highest coverage ({best_coverage} transactions)")
    if coverage['all_three'] / total < 0.5:
        print(f"  • Low overlap between parsers ({coverage['all_three']/total*100:.1f}%) - consider investigating parsing differences")
    if coverage['codex_only'] > 0:
        print(f"  • Codex finds {coverage['codex_only']} unique transactions - may have more sophisticated parsing")
    if parsers['pdf_to_csv'] == parsers['text_to_csv']:
        print("  • PDF-to-CSV and Text-to-CSV have identical coverage - PDF extraction may be working correctly")

def main():
    parser = argparse.ArgumentParser(description="Compare outputs from all three parsers")
    parser.add_argument("--prefix", type=str, required=True,
                       help="File prefix (e.g., 'Itau_2024-10' for Itau_2024-10.pdf)")
    parser.add_argument("--dir", type=Path, default=Path("test_outputs"),
                       help="Directory containing the CSV outputs")
    parser.add_argument("--output", type=Path, help="Save analysis to JSON file")

    args = parser.parse_args()

    # Construct file paths
    codex_file = args.dir / f"codex_{args.prefix}.csv"
    pdf_csv_file = args.dir / f"pdf_to_csv_{args.prefix}.csv"
    text_csv_file = args.dir / f"text_to_csv_{args.prefix}.csv"

    # Run analysis
    analysis = analyze_parsers(codex_file, pdf_csv_file, text_csv_file)

    # Print report
    print_analysis_report(analysis)

    # Save to file if requested
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f"\nDetailed analysis saved to: {args.output}")

if __name__ == "__main__":
    main()
