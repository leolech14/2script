#!/usr/bin/env python3
"""
Golden CSV Validator
===================

Precise validation against golden CSV files with detailed mismatch analysis.
Designed to achieve and verify 100% golden scores.
"""

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Comprehensive validation results."""
    total_golden_transactions: int
    total_parsed_transactions: int
    exact_matches: int
    field_matches: dict[str, int]
    missing_transactions: list[dict]
    extra_transactions: list[dict]
    field_mismatches: list[dict]
    coverage_percentage: float
    accuracy_percentage: float
    perfect_match: bool

    def __post_init__(self):
        """Calculate derived metrics."""
        self.perfect_match = (
            self.exact_matches == self.total_golden_transactions and
            len(self.missing_transactions) == 0 and
            len(self.extra_transactions) == 0
        )

class GoldenValidator:
    """Validator for achieving 100% golden CSV match."""

    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance
        self.golden_schema = [
            "card_last4", "post_date", "desc_raw", "amount_brl",
            "installment_seq", "installment_tot", "fx_rate", "iof_brl",
            "category", "merchant_city", "ledger_hash", "prev_bill_amount",
            "interest_amount", "amount_orig", "currency_orig", "amount_usd"
        ]

    def validate(self, parsed_csv: Path, golden_csv: Path) -> ValidationResult:
        """Validate parsed CSV against golden standard."""
        logger.info(f"Validating {parsed_csv} against {golden_csv}")

        # Load data
        parsed_data = self._load_parsed_csv(parsed_csv)
        golden_data = self._load_golden_csv(golden_csv)

        if not golden_data:
            raise ValueError(f"No golden data found in {golden_csv}")

        logger.info(f"Loaded {len(parsed_data)} parsed and {len(golden_data)} golden transactions")

        # Create transaction indexes for matching
        parsed_index = self._create_transaction_index(parsed_data)
        golden_index = self._create_transaction_index(golden_data)

        # Find matches and mismatches
        matches, missing, extra, field_mismatches = self._compare_transactions(
            parsed_index, golden_index, parsed_data, golden_data
        )

        # Calculate field-level statistics
        field_matches = self._calculate_field_matches(matches, golden_data)

        # Calculate percentages
        coverage = (len(matches) / len(golden_data)) * 100 if golden_data else 0
        accuracy = (len([m for m in matches if m['exact_match']]) / len(matches)) * 100 if matches else 0

        result = ValidationResult(
            total_golden_transactions=len(golden_data),
            total_parsed_transactions=len(parsed_data),
            exact_matches=len([m for m in matches if m['exact_match']]),
            field_matches=field_matches,
            missing_transactions=missing,
            extra_transactions=extra,
            field_mismatches=field_mismatches,
            coverage_percentage=coverage,
            accuracy_percentage=accuracy,
            perfect_match=False  # Will be calculated in __post_init__
        )

        self._log_validation_summary(result)
        return result

    def _load_parsed_csv(self, csv_path: Path) -> list[dict]:
        """Load parsed CSV data (comma-delimited)."""
        if not csv_path.exists():
            logger.warning(f"Parsed CSV not found: {csv_path}")
            return []

        rows = []
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        return rows

    def _load_golden_csv(self, csv_path: Path) -> list[dict]:
        """Load golden CSV data (semicolon-delimited)."""
        if not csv_path.exists():
            raise FileNotFoundError(f"Golden CSV not found: {csv_path}")

        rows = []
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                rows.append(row)

        return rows

    def _create_transaction_index(self, transactions: list[dict]) -> dict[str, dict]:
        """Create index for fast transaction lookup."""
        index = {}

        for txn in transactions:
            key = self._create_transaction_key(txn)
            if key:
                index[key] = txn

        return index

    def _create_transaction_key(self, txn: dict) -> str:
        """Create unique key for transaction matching."""
        # Use multiple fields for robust matching
        date = self._normalize_field(txn.get('post_date', ''))
        desc = self._normalize_field(txn.get('desc_raw', ''))[:50]  # Truncate for matching
        amount = self._normalize_amount(txn.get('amount_brl', ''))

        if not all([date, desc, amount]):
            return ""

        return f"{date}|{desc}|{amount}"

    def _normalize_field(self, value: str) -> str:
        """Normalize field value for comparison."""
        if not value:
            return ""
        return str(value).strip().upper()

    def _normalize_amount(self, amount_str: str) -> str:
        """Normalize amount for comparison."""
        if not amount_str:
            return "0.00"

        try:
            # Handle both comma and dot decimal separators
            clean_amount = str(amount_str).replace(',', '.')
            amount = float(clean_amount)
            return f"{amount:.2f}"
        except (ValueError, TypeError):
            return "0.00"

    def _compare_transactions(self, parsed_index: dict, golden_index: dict,
                            parsed_data: list[dict], golden_data: list[dict]) -> tuple[list, list, list, list]:
        """Compare parsed and golden transactions."""
        matches = []
        missing = []
        extra = []
        field_mismatches = []

        # Find matches and missing transactions
        for key, golden_txn in golden_index.items():
            if key in parsed_index:
                parsed_txn = parsed_index[key]
                match_result = self._compare_individual_transactions(parsed_txn, golden_txn)
                matches.append({
                    'key': key,
                    'parsed': parsed_txn,
                    'golden': golden_txn,
                    'exact_match': match_result['exact_match'],
                    'field_differences': match_result['differences']
                })

                if not match_result['exact_match']:
                    field_mismatches.extend(match_result['differences'])
            else:
                missing.append(golden_txn)

        # Find extra transactions in parsed data
        for key, parsed_txn in parsed_index.items():
            if key not in golden_index:
                extra.append(parsed_txn)

        return matches, missing, extra, field_mismatches

    def _compare_individual_transactions(self, parsed: dict, golden: dict) -> dict:
        """Compare two individual transactions field by field."""
        differences = []
        exact_match = True

        for field in self.golden_schema:
            parsed_val = parsed.get(field, "")
            golden_val = golden.get(field, "")

            if not self._fields_match(parsed_val, golden_val, field):
                exact_match = False
                differences.append({
                    'field': field,
                    'parsed': parsed_val,
                    'golden': golden_val,
                    'type': self._get_mismatch_type(parsed_val, golden_val, field)
                })

        return {
            'exact_match': exact_match,
            'differences': differences
        }

    def _fields_match(self, parsed_val: str, golden_val: str, field: str) -> bool:
        """Check if two field values match with appropriate tolerance."""
        # Monetary fields - use numerical comparison
        monetary_fields = ['amount_brl', 'fx_rate', 'iof_brl', 'prev_bill_amount',
                          'interest_amount', 'amount_orig', 'amount_usd']

        if field in monetary_fields:
            return self._amounts_match(parsed_val, golden_val)

        # Integer fields - exact match
        integer_fields = ['installment_seq', 'installment_tot']
        if field in integer_fields:
            return str(parsed_val).strip() == str(golden_val).strip()

        # String fields - normalized comparison
        return self._normalize_field(parsed_val) == self._normalize_field(golden_val)

    def _amounts_match(self, parsed_val: str, golden_val: str) -> bool:
        """Check if two monetary amounts match within tolerance."""
        try:
            parsed_amount = float(str(parsed_val).replace(',', '.')) if parsed_val else 0.0
            golden_amount = float(str(golden_val).replace(',', '.')) if golden_val else 0.0
            return abs(parsed_amount - golden_amount) <= self.tolerance
        except (ValueError, TypeError):
            return str(parsed_val).strip() == str(golden_val).strip()

    def _get_mismatch_type(self, parsed_val: str, golden_val: str, field: str) -> str:
        """Categorize the type of mismatch for analysis."""
        if not parsed_val and golden_val:
            return "missing_in_parsed"
        elif parsed_val and not golden_val:
            return "extra_in_parsed"
        elif field == 'card_last4' and parsed_val == "0000" and golden_val != "0000":
            return "card_extraction_failure"
        elif field in ['amount_brl', 'fx_rate', 'iof_brl']:
            return "amount_mismatch"
        elif field in ['category']:
            return "categorization_error"
        else:
            return "value_mismatch"

    def _calculate_field_matches(self, matches: list[dict], golden_data: list[dict]) -> dict[str, int]:
        """Calculate field-level match statistics."""
        field_matches = dict.fromkeys(self.golden_schema, 0)

        for match in matches:
            for field in self.golden_schema:
                parsed_val = match['parsed'].get(field, "")
                golden_val = match['golden'].get(field, "")

                if self._fields_match(parsed_val, golden_val, field):
                    field_matches[field] += 1

        return field_matches

    def _log_validation_summary(self, result: ValidationResult):
        """Log comprehensive validation summary."""
        logger.info("="*60)
        logger.info("GOLDEN VALIDATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Total golden transactions: {result.total_golden_transactions}")
        logger.info(f"Total parsed transactions: {result.total_parsed_transactions}")
        logger.info(f"Exact matches: {result.exact_matches}")
        logger.info(f"Coverage: {result.coverage_percentage:.1f}%")
        logger.info(f"Accuracy: {result.accuracy_percentage:.1f}%")
        logger.info(f"Missing transactions: {len(result.missing_transactions)}")
        logger.info(f"Extra transactions: {len(result.extra_transactions)}")
        logger.info(f"Perfect match: {'YES' if result.perfect_match else 'NO'}")

        # Field-level statistics
        if result.field_matches:
            logger.info("\nField-level accuracy:")
            for field, matches in result.field_matches.items():
                total = result.total_golden_transactions
                percentage = (matches / total * 100) if total > 0 else 0
                logger.info(f"  {field}: {matches}/{total} ({percentage:.1f}%)")

        # Critical issues
        if not result.perfect_match:
            logger.warning("\nCRITICAL ISSUES PREVENTING 100% MATCH:")

            if result.missing_transactions:
                logger.warning(f"- {len(result.missing_transactions)} missing transactions")

            if result.extra_transactions:
                logger.warning(f"- {len(result.extra_transactions)} extra transactions")

            # Analyze common field mismatches
            mismatch_types = {}
            for mismatch in result.field_mismatches:
                mismatch_type = mismatch.get('type', 'unknown')
                mismatch_types[mismatch_type] = mismatch_types.get(mismatch_type, 0) + 1

            if mismatch_types:
                logger.warning("- Field mismatch types:")
                for mtype, count in sorted(mismatch_types.items(), key=lambda x: x[1], reverse=True):
                    logger.warning(f"  {mtype}: {count} occurrences")

def main():
    """Command-line interface for golden validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Golden CSV Validator")
    parser.add_argument("parsed_csv", type=Path, help="Parsed CSV file to validate")
    parser.add_argument("golden_csv", type=Path, help="Golden CSV reference file")
    parser.add_argument("-o", "--output", type=Path, help="Save detailed results to JSON")
    parser.add_argument("-t", "--tolerance", type=float, default=0.01, help="Numerical tolerance")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        validator = GoldenValidator(tolerance=args.tolerance)
        result = validator.validate(args.parsed_csv, args.golden_csv)

        if result.perfect_match:
            print("🎉 PERFECT MATCH! 100% golden score achieved!")
        else:
            print(f"❌ Not perfect: {result.coverage_percentage:.1f}% coverage, {result.accuracy_percentage:.1f}% accuracy")
            print(f"Missing: {len(result.missing_transactions)}, Extra: {len(result.extra_transactions)}")

        # Save detailed results if requested
        if args.output:
            result_dict = {
                'perfect_match': result.perfect_match,
                'coverage_percentage': result.coverage_percentage,
                'accuracy_percentage': result.accuracy_percentage,
                'exact_matches': result.exact_matches,
                'total_golden': result.total_golden_transactions,
                'total_parsed': result.total_parsed_transactions,
                'missing_count': len(result.missing_transactions),
                'extra_count': len(result.extra_transactions),
                'field_matches': result.field_matches,
                'missing_transactions': result.missing_transactions[:10],  # Sample
                'extra_transactions': result.extra_transactions[:10],    # Sample
            }

            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False, default=str)

            print(f"Detailed results saved to {args.output}")

        return 0 if result.perfect_match else 1

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
