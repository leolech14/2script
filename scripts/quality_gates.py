#!/usr/bin/env python3
"""Quality gates for financial CSV validation."""

import csv
import re
from decimal import Decimal
from pathlib import Path
from typing import Any


class FinancialQualityGates:
    """Quality validation for financial CSV data."""

    def __init__(self, csv_file: Path):
        self.csv_file = csv_file
        self.errors: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []

    def validate_all(self) -> dict[str, Any]:
        """Run all quality checks."""
        self.validate_schema()
        self.validate_data_types()
        self.validate_business_rules()
        self.validate_completeness()

        return {
            "file": str(self.csv_file),
            "passed": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": {
                "error_count": len(self.errors),
                "warning_count": len(self.warnings)
            }
        }

    def validate_schema(self):
        """Validate CSV schema matches expected format."""
        expected_columns = {
            'Data', 'Valor', 'Descrição', 'Cartao', 'Categoria'
        }

        try:
            with open(self.csv_file, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                actual_columns = set(reader.fieldnames or [])

                missing = expected_columns - actual_columns
                if missing:
                    self.errors.append({
                        "type": "schema_error",
                        "message": f"Missing columns: {missing}"
                    })

                extra = actual_columns - expected_columns
                if extra:
                    self.warnings.append({
                        "type": "schema_warning",
                        "message": f"Extra columns: {extra}"
                    })
        except Exception as e:
            self.errors.append({
                "type": "file_error",
                "message": f"Cannot read CSV: {e}"
            })

    def validate_data_types(self):
        """Validate data types in each column."""
        try:
            with open(self.csv_file, encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row_num, row in enumerate(reader, 2):  # Start from 2 (header is 1)
                    # Validate date format
                    if 'Data' in row:
                        self._validate_date(row['Data'], row_num)

                    # Validate amount format
                    if 'Valor' in row:
                        self._validate_amount(row['Valor'], row_num)

                    # Validate card number format
                    if 'Cartao' in row:
                        self._validate_card(row['Cartao'], row_num)

        except Exception as e:
            self.errors.append({
                "type": "validation_error",
                "message": f"Data validation failed: {e}"
            })

    def validate_business_rules(self):
        """Validate business-specific rules."""
        try:
            with open(self.csv_file, encoding='utf-8') as f:
                reader = csv.DictReader(f)

                total_amount = Decimal('0')
                transaction_count = 0

                for row_num, row in enumerate(reader, 2):
                    transaction_count += 1

                    # Check for reasonable transaction amounts
                    if 'Valor' in row:
                        try:
                            amount = self._parse_amount(row['Valor'])
                            total_amount += amount

                            # Flag extremely large transactions
                            if abs(amount) > 10000:
                                self.warnings.append({
                                    "type": "business_warning",
                                    "row": row_num,
                                    "message": f"Large transaction: R$ {amount}"
                                })
                        except:
                            pass  # Already handled in data type validation

                # Validate reasonable total and count
                if transaction_count == 0:
                    self.errors.append({
                        "type": "business_error",
                        "message": "No transactions found"
                    })
                elif transaction_count > 1000:
                    self.warnings.append({
                        "type": "business_warning",
                        "message": f"High transaction count: {transaction_count}"
                    })

        except Exception as e:
            self.errors.append({
                "type": "business_error",
                "message": f"Business rule validation failed: {e}"
            })

    def validate_completeness(self):
        """Check for missing or empty required fields."""
        try:
            with open(self.csv_file, encoding='utf-8') as f:
                reader = csv.DictReader(f)

                required_fields = ['Data', 'Valor', 'Descrição']

                for row_num, row in enumerate(reader, 2):
                    for field in required_fields:
                        if field not in row or not row[field].strip():
                            self.errors.append({
                                "type": "completeness_error",
                                "row": row_num,
                                "field": field,
                                "message": f"Missing required field: {field}"
                            })

        except Exception as e:
            self.errors.append({
                "type": "completeness_error",
                "message": f"Completeness check failed: {e}"
            })

    def _validate_date(self, date_str: str, row_num: int):
        """Validate date format."""
        date_patterns = [
            r'^\d{2}/\d{2}/\d{4}$',  # DD/MM/YYYY
            r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
        ]

        if not any(re.match(pattern, date_str) for pattern in date_patterns):
            self.errors.append({
                "type": "date_error",
                "row": row_num,
                "value": date_str,
                "message": "Invalid date format"
            })

    def _validate_amount(self, amount_str: str, row_num: int):
        """Validate amount format."""
        try:
            self._parse_amount(amount_str)
        except:
            self.errors.append({
                "type": "amount_error",
                "row": row_num,
                "value": amount_str,
                "message": "Invalid amount format"
            })

    def _validate_card(self, card_str: str, row_num: int):
        """Validate card format."""
        if card_str and not re.match(r'^\*{4}\d{4}$', card_str):
            self.warnings.append({
                "type": "card_warning",
                "row": row_num,
                "value": card_str,
                "message": "Unusual card format"
            })

    def _parse_amount(self, amount_str: str) -> Decimal:
        """Parse amount string to Decimal."""
        # Handle Brazilian format: R$ -1.234,56
        cleaned = re.sub(r'[^\d,.-]', '', amount_str)
        cleaned = cleaned.replace('.', '').replace(',', '.')
        return Decimal(cleaned)


def main():
    """Run quality gates on all CSV files."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python quality_gates.py <csv_file> [csv_file2...]")
        sys.exit(1)

    all_passed = True

    for csv_file in sys.argv[1:]:
        path = Path(csv_file)
        if not path.exists():
            print(f"❌ File not found: {csv_file}")
            all_passed = False
            continue

        gates = FinancialQualityGates(path)
        result = gates.validate_all()

        if result["passed"]:
            print(f"✅ {csv_file} - All quality gates passed")
        else:
            print(f"❌ {csv_file} - {result['summary']['error_count']} errors, "
                  f"{result['summary']['warning_count']} warnings")
            all_passed = False

            for error in result["errors"]:
                print(f"   ERROR: {error['message']}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
