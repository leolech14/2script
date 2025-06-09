#!/usr/bin/env python3
"""
parser_utils.py – Shared utilities for Itaú statement parsing

Intended for use by golden_guided_parser.py and other scripts.
"""

import re
import csv
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional

def decomma(x: str) -> Decimal:
    """Convert Brazilian number string to Decimal(2) safely."""
    if not x or not str(x).strip():
        return Decimal("0.00")
    val = re.sub(r"[^\d,\-]", "", str(x).replace(' ', '')).replace('.', '').replace(',', '.')
    try:
        return Decimal(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")

def load_csv(path, delimiter=";") -> List[Dict]:
    """Load a CSV file into a list of dicts."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return [dict(row) for row in reader]

def clean_line(txt: str) -> str:
    """Strip funky symbols / duplicate spaces."""
    txt = re.sub(r"[\ue000-\uf8ff]", "", txt)  # PUA glyphs
    txt = re.sub(r"\s{2,}", " ", txt.strip(">•*®«» @_")).strip()
    return txt

def fuzzy_match(a: str, b: str) -> float:
    """Return a fuzzy match ratio between two strings."""
    import difflib
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_fx_rate(lines: List[str], idx: int, window: int = 3) -> Optional[str]:
    """Extract FX rate from lines near idx."""
    for offset in range(window):
        i = idx + offset
        if 0 <= i < len(lines):
            m = re.search(r"(\d+,\d{4})", lines[i])
            if m and "Dólar de Conversão" in lines[i]:
                return m.group(1).replace(",", ".")
    return None

def extract_category_and_city(line: str) -> tuple[str, str]:
    """Extract category and merchant city from a line like 'SAÚDE .PASSO FUNDO'."""
    if "." in line:
        parts = line.split(".")
        return parts[0].strip(), parts[-1].strip()
    return "", ""
def find_best_line(golden_row: Dict, lines: List[str]) -> int:
    """Find the best matching line index for a golden row."""
    best_idx, best_score = None, 0.0
    target_date = golden_row.get("date", "")
    target_amt = golden_row.get("amount_brl", "").replace(",", ".")
    target_desc = golden_row.get("description", "") or golden_row.get("desc_raw", "")
    for i, line in enumerate(lines):
        score = 0.0
        if target_date in line:
            score += 0.5
        if target_amt and target_amt in line.replace(",", "."):
            score += 0.5
        if target_desc and target_desc.lower() in line.lower():
            score += 0.3
        score += 0.2 * fuzzy_match(target_desc, line)
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx

# Add more shared utilities as needed.