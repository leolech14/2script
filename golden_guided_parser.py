#!/usr/bin/env python3
"""
golden_guided_parser.py – Golden-guided Itaú statement parser

This script:
- Loads a golden CSV (reference, 100%-correct output)
- Loads the raw TXT (or PDF-extracted lines) for the same statement
- Matches each golden posting to its best candidate in the text
- Learns the pattern/rule for each posting (explainable parsing)
- Builds a CSV skeleton, then enriches with metadata from the text
- Outputs a CSV matching the golden, with all available metadata

Usage:
    python golden_guided_parser.py --golden golden.csv --txt statement.txt --out output.csv
"""

import argparse
import csv
import difflib
import re
from pathlib import Path


def load_golden_csv(path: Path) -> list[dict]:
    """Load golden CSV into a list of dicts."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        return [dict(row) for row in reader]

def load_txt_lines(path: Path) -> list[str]:
    """Load and clean TXT lines."""
    with open(path, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]

def find_best_text_match(golden_row: dict, lines: list[str]) -> tuple[int | None, float]:
    """
    For a golden posting, find the best matching line index in the TXT.
    Returns (index, score).
    """
    target = f"{golden_row.get('date','')} {golden_row.get('amount_brl','')}".replace(",", ".")
    best_idx, best_score = None, 0.0
    for i, line in enumerate(lines):
        # Simple heuristic: match date and amount
        score = 0.0
        if golden_row.get("date", "") in line:
            score += 0.5
        amt = golden_row.get("amount_brl", "").replace(",", ".")
        if amt and amt in line.replace(",", "."):
            score += 0.5
        # Fuzzy description match
        desc = golden_row.get("description", "") or golden_row.get("desc_raw", "")
        if desc and desc.lower() in line.lower():
            score += 0.3
        # Use difflib for fuzzy matching
        ratio = difflib.SequenceMatcher(None, desc.lower(), line.lower()).ratio() if desc else 0
        score += 0.2 * ratio
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx, best_score

def extract_pattern_rule(golden_row: dict, matched_line: str, lines: list[str]) -> dict:
    """
    Analyze how the golden posting appears in the text.
    Returns a dict describing the pattern/rule.
    """
    rule = {
        "date_in_line": golden_row.get("date", "") in matched_line,
        "amount_in_line": golden_row.get("amount_brl", "").replace(",", ".") in matched_line.replace(",", "."),
        "desc_in_line": (golden_row.get("description", "") or golden_row.get("desc_raw", "")).lower() in matched_line.lower(),
        "line_text": matched_line,
    }
    # Optionally, add neighbor lines
    idx = lines.index(matched_line) if matched_line in lines else -1
    rule["prev_line"] = lines[idx-1] if idx > 0 else ""
    rule["next_line"] = lines[idx+1] if 0 <= idx < len(lines)-1 else ""
    return rule

def enrich_metadata(row: dict, matched_line: str, lines: list[str]) -> None:
    """
    Fill in additional metadata fields for the CSV row,
    using the matched line and its neighbors.
    """
    # Example: extract category and merchant city from next line if present
    idx = lines.index(matched_line) if matched_line in lines else -1
    next_line = lines[idx+1] if 0 <= idx < len(lines)-1 else ""
    # If next line is all caps and has a dot, treat as category.city
    if re.match(r"^[A-ZÇÃÕÉÍÚÊÂÔÀÜÖÄ .]+$", next_line) and "." in next_line:
        parts = next_line.split(".")
        row["category"] = parts[0].strip()
        row["merchant_city"] = parts[-1].strip()
    # FX rate extraction example
    fx_line = next((l for l in lines[idx:idx+3] if "Dólar de Conversão" in l), "")
    if fx_line:
        m = re.search(r"(\d+,\d{4})", fx_line)
        if m:
            row["fx_rate"] = m.group(1).replace(",", ".")
    # Add more enrichment as needed

def write_csv(rows: list[dict], out_path: Path, schema: list[str]):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=schema, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description="Golden-guided Itaú parser")
    parser.add_argument("--golden", type=Path, required=True, help="Golden CSV file")
    parser.add_argument("--txt", type=Path, required=True, help="Raw TXT file")
    parser.add_argument("--out", type=Path, required=True, help="Output CSV file")
    args = parser.parse_args()

    golden_rows = load_golden_csv(args.golden)
    txt_lines = load_txt_lines(args.txt)
    print(f"Loaded {len(golden_rows)} golden rows, {len(txt_lines)} text lines.")

    # 1. Match each golden posting to a text line
    matches = []
    used_lines = set()
    for g in golden_rows:
        idx, score = find_best_text_match(g, txt_lines)
        matched_line = txt_lines[idx] if idx is not None else ""
        matches.append((g, matched_line))
        if idx is not None:
            used_lines.add(idx)

    # 2. Analyze patterns/rules
    golden_rules = []
    for g, matched_line in matches:
        rule = extract_pattern_rule(g, matched_line, txt_lines)
        golden_rules.append(rule)

    # 3. Build CSV skeleton and enrich metadata
    schema = list(golden_rows[0].keys())  # Use golden schema exactly
    csv_rows = []
    for (g, matched_line) in matches:
        row = dict(g)
        enrich_metadata(row, matched_line, txt_lines)
        csv_rows.append(row)

    # 4. Write output
    write_csv(csv_rows, args.out, schema)
    print(f"Wrote {len(csv_rows)} rows to {args.out}")

    # 5. Optionally, write golden rules for review
    rules_out = args.out.with_suffix(".rules.json")
    import json
    with open(rules_out, "w", encoding="utf-8") as f:
        json.dump(golden_rules, f, indent=2, ensure_ascii=False)
    print(f"Wrote pattern rules to {rules_out}")

if __name__ == "__main__":
    main()
