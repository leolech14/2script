#!/usr/bin/env python3
"""
Contest Analysis Tool
===================
Compare script.py vs itau_parser_ultimate.py performance
"""

import csv
from collections import defaultdict
from pathlib import Path


def analyze_csv(file_path):
    """Analyze a CSV file and return metrics."""
    if not file_path.exists():
        return {"transactions": 0, "error": "File not found"}

    try:
        with open(file_path, encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            rows = list(reader)

            # Count transactions by category
            categories = defaultdict(int)
            card_numbers = set()
            total_amount = 0.0

            for row in rows:
                if 'category' in row:
                    categories[row['category']] += 1
                if 'card_last4' in row:
                    card_numbers.add(row['card_last4'])
                if 'amount_brl' in row:
                    try:
                        amount = float(row['amount_brl'].replace(',', '.'))
                        total_amount += amount
                    except:
                        pass

            return {
                "transactions": len(rows),
                "categories": len(categories),
                "cards": len(card_numbers),
                "total_amount": total_amount,
                "category_breakdown": dict(categories)
            }
    except Exception as e:
        return {"transactions": 0, "error": str(e)}

def main():
    results_dir = Path(".")

    # Find all parsed files
    script_files = list(results_dir.glob("*_parsed.csv"))
    ultimate_files = list(results_dir.glob("*_ultimate.csv"))

    print("🏆 PDF-to-CSV CONTEST RESULTS")
    print("=" * 50)

    total_script = 0
    total_ultimate = 0

    for script_file in sorted(script_files):
        # Find matching ultimate file
        base_name = script_file.stem.replace("_parsed", "")
        ultimate_file = results_dir / f"{base_name}.pdf_ultimate.csv"

        script_metrics = analyze_csv(script_file)
        ultimate_metrics = analyze_csv(ultimate_file)

        print(f"\n📄 {base_name}")
        print(f"   script.py:     {script_metrics['transactions']} transactions")
        print(f"   ultimate.py:   {ultimate_metrics['transactions']} transactions")

        if script_metrics['transactions'] > 0 and ultimate_metrics['transactions'] > 0:
            diff = ultimate_metrics['transactions'] - script_metrics['transactions']
            print(f"   Difference:    {diff:+d} ({'+' if diff >= 0 else ''}{diff})")

        total_script += script_metrics['transactions']
        total_ultimate += ultimate_metrics['transactions']

    print("\n🎯 FINAL SCOREBOARD")
    print("=" * 30)
    print(f"script.py total:           {total_script:,} transactions")
    print(f"itau_parser_ultimate.py:   {total_ultimate:,} transactions")
    print(f"Winner margin:             {abs(total_ultimate - total_script):+,} transactions")

    if total_ultimate > total_script:
        print("🏆 WINNER: itau_parser_ultimate.py")
        advantage = ((total_ultimate - total_script) / total_script) * 100
        print(f"   Advantage: {advantage:.1f}% more transactions extracted")
    elif total_script > total_ultimate:
        print("🏆 WINNER: script.py")
        advantage = ((total_script - total_ultimate) / total_ultimate) * 100
        print(f"   Advantage: {advantage:.1f}% more transactions extracted")
    else:
        print("🤝 TIE: Both parsers extracted the same number of transactions")

if __name__ == "__main__":
    main()
