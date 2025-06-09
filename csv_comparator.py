#!/usr/bin/env python3
"""
CSV Comparator for Golden Testing
Compares actual CSV outputs with expected golden files.
"""

import argparse
import csv
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_csv(path: Path) -> list[dict]:
    """Load CSV file into list of dictionaries."""
    rows = []
    try:
        with open(path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows
    except Exception as e:
        logger.error(f"Error loading CSV {path}: {e}")
        return []


def normalize_value(value: str, field: str) -> str:
    """Normalize values for comparison."""
    if not value:
        return ""

    # Normalize monetary values
    monetary_fields = ['amount_brl', 'valor_brl', 'fx_rate', 'iof_brl', 'amount_orig', 'amount_usd']
    if field in monetary_fields:
        try:
            # Convert to float and back to standardize format
            num_val = float(value.replace(',', '.'))
            return f"{num_val:.2f}"
        except ValueError:
            return value.strip()

    # Normalize dates
    if 'date' in field.lower():
        return value.strip()

    # Default: just strip whitespace
    return value.strip()


def compare_csvs(actual_path: Path, golden_path: Path, tolerance: float = 0.01) -> dict:
    """Compare two CSV files and return detailed comparison results."""

    if not actual_path.exists():
        return {"error": f"Actual file not found: {actual_path}"}

    if not golden_path.exists():
        return {"error": f"Golden file not found: {golden_path}"}

    actual_rows = load_csv(actual_path)
    golden_rows = load_csv(golden_path)

    if not actual_rows and not golden_rows:
        return {"error": "Both files are empty or unreadable"}

    result = {
        "actual_file": str(actual_path),
        "golden_file": str(golden_path),
        "actual_count": len(actual_rows),
        "golden_count": len(golden_rows),
        "exact_matches": 0,
        "fuzzy_matches": 0,
        "mismatches": [],
        "missing_from_actual": [],
        "extra_in_actual": [],
        "field_stats": {},
        "summary": {}
    }

    # Get all unique field names
    all_fields = set()
    if actual_rows:
        all_fields.update(actual_rows[0].keys())
    if golden_rows:
        all_fields.update(golden_rows[0].keys())

    # Initialize field statistics
    for field in all_fields:
        result["field_stats"][field] = {
            "matches": 0,
            "mismatches": 0,
            "missing_in_actual": 0,
            "missing_in_golden": 0
        }

    # Create lookup for matching rows
    # Use multiple keys for robustness
    def create_row_key(row):
        key_fields = ['post_date', 'desc_raw', 'amount_brl', 'valor_brl']
        key_parts = []
        for field in key_fields:
            if field in row:
                val = normalize_value(row[field], field)
                if val:  # Only add non-empty values
                    key_parts.append(val)
        return '|'.join(key_parts) if key_parts else None

    actual_dict = {}
    for i, row in enumerate(actual_rows):
        key = create_row_key(row)
        if key:
            actual_dict[key] = (i, row)

    golden_dict = {}
    for i, row in enumerate(golden_rows):
        key = create_row_key(row)
        if key:
            golden_dict[key] = (i, row)

    # Compare matched rows
    matched_keys = set(actual_dict.keys()) & set(golden_dict.keys())

    for key in matched_keys:
        actual_idx, actual_row = actual_dict[key]
        golden_idx, golden_row = golden_dict[key]

        row_comparison = compare_rows(actual_row, golden_row, all_fields, tolerance)

        if row_comparison["exact_match"]:
            result["exact_matches"] += 1
        elif row_comparison["fuzzy_match"]:
            result["fuzzy_matches"] += 1
        else:
            result["mismatches"].append({
                "key": key,
                "actual_row": actual_idx,
                "golden_row": golden_idx,
                "differences": row_comparison["differences"]
            })

        # Update field statistics
        for field in all_fields:
            field_result = row_comparison["field_results"].get(field, {"match": False})
            if field_result["match"]:
                result["field_stats"][field]["matches"] += 1
            else:
                result["field_stats"][field]["mismatches"] += 1

    # Find unmatched rows
    actual_only_keys = set(actual_dict.keys()) - set(golden_dict.keys())
    golden_only_keys = set(golden_dict.keys()) - set(actual_dict.keys())

    for key in actual_only_keys:
        _, row = actual_dict[key]
        result["extra_in_actual"].append(row)

    for key in golden_only_keys:
        _, row = golden_dict[key]
        result["missing_from_actual"].append(row)

    # Calculate summary statistics
    total_compared = len(matched_keys)
    result["summary"] = {
        "total_golden_rows": len(golden_rows),
        "total_actual_rows": len(actual_rows),
        "rows_compared": total_compared,
        "exact_match_rate": result["exact_matches"] / max(total_compared, 1) * 100,
        "fuzzy_match_rate": result["fuzzy_matches"] / max(total_compared, 1) * 100,
        "total_match_rate": (result["exact_matches"] + result["fuzzy_matches"]) / max(total_compared, 1) * 100,
        "missing_rows": len(result["missing_from_actual"]),
        "extra_rows": len(result["extra_in_actual"])
    }

    return result


def compare_rows(actual: dict, golden: dict, all_fields: set, tolerance: float = 0.01) -> dict:
    """Compare two individual rows."""
    differences = []
    field_results = {}
    exact_match = True
    fuzzy_match = True

    for field in all_fields:
        actual_val = actual.get(field, "")
        golden_val = golden.get(field, "")

        actual_norm = normalize_value(actual_val, field)
        golden_norm = normalize_value(golden_val, field)

        field_match = False

        if actual_norm == golden_norm:
            field_match = True
        else:
            # Try numeric comparison for monetary fields
            monetary_fields = ['amount_brl', 'valor_brl', 'fx_rate', 'iof_brl', 'amount_orig', 'amount_usd']
            if field in monetary_fields:
                try:
                    actual_num = float(actual_norm) if actual_norm else 0.0
                    golden_num = float(golden_norm) if golden_norm else 0.0
                    if abs(actual_num - golden_num) <= tolerance:
                        field_match = True
                except ValueError:
                    pass

        field_results[field] = {
            "match": field_match,
            "actual": actual_val,
            "golden": golden_val
        }

        if not field_match:
            exact_match = False
            differences.append({
                "field": field,
                "actual": actual_val,
                "golden": golden_val
            })

            # For fuzzy matching, ignore empty vs. non-empty differences in optional fields
            optional_fields = ['installment_seq', 'installment_tot', 'merchant_city', 'currency_orig']
            if field not in optional_fields:
                fuzzy_match = False

    return {
        "exact_match": exact_match,
        "fuzzy_match": fuzzy_match,
        "differences": differences,
        "field_results": field_results
    }


def print_comparison_report(comparison: dict):
    """Print a human-readable comparison report."""
    if "error" in comparison:
        print(f"❌ Error: {comparison['error']}")
        return

    summary = comparison["summary"]

    print("\n📊 CSV Comparison Report")
    print(f"{'='*50}")
    print(f"Actual file:  {comparison['actual_file']}")
    print(f"Golden file:  {comparison['golden_file']}")
    print("")
    print("Row counts:")
    print(f"  Golden: {summary['total_golden_rows']}")
    print(f"  Actual: {summary['total_actual_rows']}")
    print(f"  Compared: {summary['rows_compared']}")
    print("")
    print("Match rates:")
    print(f"  Exact matches: {comparison['exact_matches']} ({summary['exact_match_rate']:.1f}%)")
    print(f"  Fuzzy matches: {comparison['fuzzy_matches']} ({summary['fuzzy_match_rate']:.1f}%)")
    print(f"  Total matches: {summary['total_match_rate']:.1f}%")
    print("")
    print("Differences:")
    print(f"  Missing rows: {summary['missing_rows']}")
    print(f"  Extra rows: {summary['extra_rows']}")
    print(f"  Mismatched rows: {len(comparison['mismatches'])}")

    # Field-level statistics
    if comparison["field_stats"]:
        print("\n📋 Field-level Statistics:")
        for field, stats in comparison["field_stats"].items():
            total = stats["matches"] + stats["mismatches"]
            if total > 0:
                match_rate = stats["matches"] / total * 100
                print(f"  {field}: {stats['matches']}/{total} ({match_rate:.1f}%)")

    # Show first few mismatches if any
    if comparison["mismatches"]:
        print("\n🔍 Sample Mismatches (first 3):")
        for i, mismatch in enumerate(comparison["mismatches"][:3]):
            print(f"  Row {mismatch['actual_row']} differences:")
            for diff in mismatch["differences"][:3]:  # Show first 3 field differences
                print(f"    {diff['field']}: '{diff['actual']}' vs '{diff['golden']}'")


def main():
    parser = argparse.ArgumentParser(description="Compare CSV files for golden testing")
    parser.add_argument("actual", type=Path, help="Actual CSV file")
    parser.add_argument("golden", type=Path, help="Golden CSV file")
    parser.add_argument("--tolerance", type=float, default=0.01,
                       help="Numerical comparison tolerance (default: 0.01)")
    parser.add_argument("--output", type=Path, help="Save detailed report to JSON file")
    parser.add_argument("--quiet", action="store_true", help="Only show summary")

    args = parser.parse_args()

    comparison = compare_csvs(args.actual, args.golden, args.tolerance)

    if not args.quiet:
        print_comparison_report(comparison)
    else:
        if "error" in comparison:
            print(f"Error: {comparison['error']}")
        else:
            summary = comparison["summary"]
            print(f"Match rate: {summary['total_match_rate']:.1f}% "
                  f"({comparison['exact_matches']+comparison['fuzzy_matches']}/{summary['rows_compared']} rows)")

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)
        print(f"\nDetailed report saved to: {args.output}")


if __name__ == "__main__":
    main()
