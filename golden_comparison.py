#!/usr/bin/env python3
"""
Golden CSV Comparison Tool
Compares script outputs against the golden CSV files with proper handling
of different formats, delimiters, and field mappings.
"""

import csv
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import json

def load_golden_csv(path: Path) -> List[Dict]:
    """Load golden CSV with semicolon delimiter."""
    rows = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            # Golden CSVs use semicolon delimiter
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                rows.append(row)
        return rows
    except Exception as e:
        print(f"Error loading golden CSV {path}: {e}")
        return []

def load_script_csv(path: Path) -> List[Dict]:
    """Load script output CSV with comma delimiter."""
    rows = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows
    except Exception as e:
        print(f"Error loading script CSV {path}: {e}")
        return []

def normalize_field_names(row: Dict, is_golden: bool = False) -> Dict:
    """Normalize field names between golden and script outputs."""
    normalized = {}
    
    field_mapping = {
        # Golden -> Standard mapping
        'amount_brl': 'amount',
        'desc_raw': 'description', 
        'post_date': 'date',
        'card_last4': 'card',
        'category': 'category',
        'ledger_hash': 'hash',
        'installment_seq': 'inst_seq',
        'installment_tot': 'inst_tot',
        'fx_rate': 'fx_rate',
        'iof_brl': 'iof',
        'merchant_city': 'city',
        
        # Script field mappings
        'valor_brl': 'amount',
        'categoria_high': 'category',
    }
    
    for key, value in row.items():
        normalized_key = field_mapping.get(key, key)
        normalized[normalized_key] = value.strip() if isinstance(value, str) else value
    
    return normalized

def create_transaction_key(row: Dict) -> str:
    """Create a unique key for matching transactions."""
    date = row.get('date', '').strip()
    desc = row.get('description', '').strip()[:50]  # Truncate description for matching
    amount = row.get('amount', '').strip()
    
    # Normalize amount
    if amount:
        try:
            # Handle both comma and period decimal separators
            amount_clean = amount.replace(',', '.')
            amount_float = float(amount_clean)
            amount_str = f"{amount_float:.2f}"
        except ValueError:
            amount_str = amount
    else:
        amount_str = '0.00'
    
    return f"{date}|{desc}|{amount_str}"

def compare_with_golden(script_path: Path, golden_path: Path, script_name: str) -> Dict:
    """Compare script output with golden CSV."""
    
    if not script_path.exists():
        return {"error": f"Script output not found: {script_path}"}
    
    if not golden_path.exists():
        return {"error": f"Golden file not found: {golden_path}"}
    
    script_rows = load_script_csv(script_path)
    golden_rows = load_golden_csv(golden_path)
    
    if not script_rows and not golden_rows:
        return {"error": "Both files are empty"}
    
    print(f"\n{'='*60}")
    print(f"COMPARING {script_name.upper()} OUTPUT")
    print(f"{'='*60}")
    print(f"Script: {script_path.name} ({len(script_rows)} rows)")
    print(f"Golden: {golden_path.name} ({len(golden_rows)} rows)")
    
    # Normalize field names
    script_normalized = [normalize_field_names(row) for row in script_rows]
    golden_normalized = [normalize_field_names(row, is_golden=True) for row in golden_rows]
    
    # Create transaction indexes
    script_index = {}
    for i, row in enumerate(script_normalized):
        key = create_transaction_key(row)
        if key:
            script_index[key] = (i, row)
    
    golden_index = {}
    for i, row in enumerate(golden_normalized):
        key = create_transaction_key(row)
        if key:
            golden_index[key] = (i, row)
    
    # Compare transactions
    matched_keys = set(script_index.keys()) & set(golden_index.keys())
    script_only = set(script_index.keys()) - set(golden_index.keys())
    golden_only = set(golden_index.keys()) - set(script_index.keys())
    
    exact_matches = 0
    field_differences = []
    
    # Analyze matched transactions
    for key in matched_keys:
        script_idx, script_row = script_index[key]
        golden_idx, golden_row = golden_index[key]
        
        row_diffs = []
        is_exact_match = True
        
        # Compare important fields
        important_fields = ['amount', 'description', 'date', 'card', 'category']
        for field in important_fields:
            script_val = script_row.get(field, '').strip()
            golden_val = golden_row.get(field, '').strip()
            
            if field == 'amount':
                # Numerical comparison
                try:
                    script_num = float(script_val.replace(',', '.')) if script_val else 0.0
                    golden_num = float(golden_val.replace(',', '.')) if golden_val else 0.0
                    if abs(script_num - golden_num) > 0.01:
                        row_diffs.append(f"{field}: {script_val} vs {golden_val}")
                        is_exact_match = False
                except ValueError:
                    if script_val != golden_val:
                        row_diffs.append(f"{field}: {script_val} vs {golden_val}")
                        is_exact_match = False
            else:
                if script_val.lower() != golden_val.lower():
                    row_diffs.append(f"{field}: {script_val} vs {golden_val}")
                    is_exact_match = False
        
        if is_exact_match:
            exact_matches += 1
        elif row_diffs:
            field_differences.append({
                "key": key,
                "script_row": script_idx,
                "golden_row": golden_idx,
                "differences": row_diffs
            })
    
    # Calculate statistics
    total_golden = len(golden_rows)
    total_script = len(script_rows)
    coverage = len(matched_keys) / max(total_golden, 1) * 100
    accuracy = exact_matches / max(len(matched_keys), 1) * 100
    
    result = {
        "script_name": script_name,
        "script_file": str(script_path),
        "golden_file": str(golden_path),
        "total_script_rows": total_script,
        "total_golden_rows": total_golden,
        "matched_transactions": len(matched_keys),
        "exact_matches": exact_matches,
        "coverage_percent": coverage,
        "accuracy_percent": accuracy,
        "script_only_count": len(script_only),
        "golden_only_count": len(golden_only),
        "field_differences_count": len(field_differences),
        "field_differences": field_differences[:5],  # Show first 5 differences
        "script_only_samples": list(script_only)[:3],
        "golden_only_samples": list(golden_only)[:3]
    }
    
    # Print summary
    print(f"\n📊 COMPARISON RESULTS:")
    print(f"  Coverage: {coverage:.1f}% ({len(matched_keys)}/{total_golden} golden transactions found)")
    print(f"  Accuracy: {accuracy:.1f}% ({exact_matches}/{len(matched_keys)} matches are exact)")
    print(f"  Missing: {len(golden_only)} transactions not found by script")
    print(f"  Extra: {len(script_only)} transactions found only by script")
    print(f"  Field differences: {len(field_differences)} matched transactions with differences")
    
    # Show sample differences
    if field_differences:
        print(f"\n🔍 SAMPLE FIELD DIFFERENCES:")
        for i, diff in enumerate(field_differences[:3]):
            print(f"  {i+1}. Row {diff['script_row']} differences:")
            for field_diff in diff['differences'][:2]:
                print(f"     {field_diff}")
    
    # Show missing transactions
    if golden_only:
        print(f"\n❌ SAMPLE MISSING TRANSACTIONS:")
        for i, key in enumerate(list(golden_only)[:3]):
            parts = key.split('|')
            print(f"  {i+1}. {parts[0]} - {parts[1][:30]}... - {parts[2]}")
    
    return result

def main():
    parser = argparse.ArgumentParser(description="Compare script outputs with golden CSV files")
    parser.add_argument("--pdf-name", required=True, 
                       help="PDF name prefix (e.g., '2024-10' for Itau_2024-10.pdf)")
    parser.add_argument("--output-dir", type=Path, default=Path("test_outputs"),
                       help="Directory containing script outputs")
    parser.add_argument("--save-report", type=Path, help="Save detailed report to JSON file")
    
    args = parser.parse_args()
    
    # Define file paths
    golden_file = Path(f"golden_{args.pdf_name}.csv")
    
    script_files = {
        "codex": args.output_dir / f"codex_Itau_{args.pdf_name}.csv",
        "pdf_to_csv": args.output_dir / f"pdf_to_csv_Itau_{args.pdf_name}.csv", 
        "text_to_csv": args.output_dir / f"text_to_csv_Itau_{args.pdf_name}.csv"
    }
    
    results = {}
    
    # Compare each script output
    for script_name, script_path in script_files.items():
        try:
            result = compare_with_golden(script_path, golden_file, script_name)
            results[script_name] = result
        except Exception as e:
            print(f"Error comparing {script_name}: {e}")
            results[script_name] = {"error": str(e)}
    
    # Overall summary
    print(f"\n{'='*60}")
    print("OVERALL SUMMARY")
    print(f"{'='*60}")
    
    for script_name, result in results.items():
        if "error" not in result:
            print(f"{script_name.upper()}:")
            print(f"  Coverage: {result['coverage_percent']:.1f}%")
            print(f"  Accuracy: {result['accuracy_percent']:.1f}%")
            print(f"  Total Score: {result['coverage_percent'] * result['accuracy_percent'] / 100:.1f}")
        else:
            print(f"{script_name.upper()}: ERROR - {result['error']}")
    
    # Save detailed report
    if args.save_report:
        with open(args.save_report, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nDetailed report saved to: {args.save_report}")

if __name__ == "__main__":
    main()
