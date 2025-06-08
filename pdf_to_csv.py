"""
PDF → CSV extractor for Itaú credit-card statements.

Reuses the business rules already in text_to_csv.py.
CLI
---
python -m statement_refinery.pdf_to_csv input.pdf [--out output.csv]
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Iterator, List

import pdfplumber                               # pip install pdfplumber
from pathlib import Path as PathLib
import re
from decimal import Decimal
import hashlib

CSV_HEADER = [
    "card_last4",
    "post_date",
    "desc_raw",
    "amount_brl",
    "installment_seq",
    "installment_tot",
    "fx_rate",
    "iof_brl",
    "category",
    "merchant_city",
    "ledger_hash",
    "prev_bill_amount",
    "interest_amount",
    "amount_orig",
    "currency_orig",
    "amount_usd",
]

_LOGGER = logging.getLogger("pdf_to_csv")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ───────────────────────── helpers ──────────────────────────
def iter_pdf_lines(pdf_path: Path) -> Iterator[str]:
    """Yield each non-empty line of the PDF."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        for idx, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text is None:
                _LOGGER.warning("Page %d has no extractable text – skipped", idx)
                continue
            for line in text.splitlines():
                line = line.rstrip()
                if line:
                    yield line


def parse_statement_line(line: str) -> dict:
    """Parse a single statement line using basic patterns."""
    # Basic patterns
    date_pattern = r'(\d{2}/\d{2})'
    amount_pattern = r'([\d.,]+)'
    card_pattern = r'final (\d{4})'
    
    # Try to match a transaction line
    transaction = re.match(f'{date_pattern}\s+(.+?)\s+{amount_pattern}$', line)
    if transaction:
        date, description, amount = transaction.groups()
        amount = Decimal(amount.replace('.', '').replace(',', '.'))
        
        # Try to find card number
        card_match = re.search(card_pattern, description)
        card_last4 = card_match.group(1) if card_match else '0000'
        
        # Simple categorization
        desc_upper = description.upper()
        if 'PAGAMENTO' in desc_upper:
            category = 'PAGAMENTO'
        elif 'IOF' in desc_upper:
            category = 'IOF'
        elif any(x in desc_upper for x in ['RESTAUR', 'LANCHE', 'CAFE']):
            category = 'RESTAURANTE'
        elif any(x in desc_upper for x in ['SUPERMERC', 'MERCADO']):
            category = 'SUPERMERCADO'
        else:
            category = 'DIVERSOS'
        
        # Generate simple hash
        hash_input = f"{card_last4}|{date}|{description}|{amount}"
        ledger_hash = hashlib.sha1(hash_input.encode()).hexdigest()
        
        return {
            'card_last4': card_last4,
            'post_date': date,
            'desc_raw': description,
            'amount_brl': str(amount),
            'installment_seq': '',
            'installment_tot': '',
            'fx_rate': '',
            'iof_brl': '',
            'category': category,
            'merchant_city': '',
            'ledger_hash': ledger_hash,
            'prev_bill_amount': '',
            'interest_amount': '',
            'amount_orig': '',
            'currency_orig': '',
            'amount_usd': '',
        }
    
    return None


def parse_lines(lines: Iterator[str]) -> List[dict]:
    """Convert raw lines into row-dicts via the basic parser."""
    rows: List[dict] = []
    for line in lines:
        try:
            row = parse_statement_line(line)
            if row:
                rows.append(row)
        except Exception as exc:                 # pragma: no cover
            _LOGGER.warning("Skip line '%s': %s", line, exc)
    return rows


def write_csv(rows: List[dict], out_fh) -> None:
    writer = csv.DictWriter(out_fh, fieldnames=CSV_HEADER, dialect="unix")
    writer.writeheader()
    writer.writerows(rows)


# ───────────────────────── CLI ──────────────────────────────
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pdf_to_csv", description="Convert Itaú PDF statement to CSV"
    )
    parser.add_argument("pdf", type=Path, help="Input PDF")
    parser.add_argument("--out", type=Path, default=None, help="Output CSV path")
    args = parser.parse_args(argv)

    rows = parse_lines(iter_pdf_lines(args.pdf))
    _LOGGER.info("Parsed %d transactions", len(rows))

    if args.out:
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            write_csv(rows, fh)
        _LOGGER.info("CSV written → %s", args.out)
    else:
        write_csv(rows, sys.stdout)


if __name__ == "__main__":  # pragma: no cover
    main()