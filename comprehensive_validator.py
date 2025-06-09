#!/usr/bin/env python3
"""Comprehensive validation between parser output and golden CSV"""

import csv
from pathlib import Path
from difflib import SequenceMatcher

def load_csv(path):
    """Load CSV into list of dicts"""
    with open(path, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f, delimiter=';'))
        print(f"DEBUG: Loaded {len(rows)} rows from {path}")
        return rows

def normalize_amount(amount_str):
    """Normalize amount to float for comparison"""
    if not amount_str:
        return 0.0
    # Convert comma decimal to dot decimal
    return float(amount_str.replace(',', '.'))

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a.upper(), b.upper()).ratio()

def find_best_matches(parser_data, golden_data):
    """Find best matches between parser and golden data"""
    matches = []
    used_golden = set()
    
    for p_idx, p_row in enumerate(parser_data):
        best_match = None
        best_score = 0
        best_g_idx = -1
        
        for g_idx, g_row in enumerate(golden_data):
            if g_idx in used_golden:
                continue
                
            # Calculate match score based on multiple factors
            score = 0
            
            # Description similarity (most important)
            desc_sim = similarity(p_row['desc_raw'], g_row['desc_raw'])
            score += desc_sim * 0.5
            
            # Amount similarity
            try:
                p_amount = normalize_amount(p_row['amount_brl'])
                g_amount = normalize_amount(g_row['amount_brl'])
                if p_amount > 0 and g_amount > 0:
                    amount_diff = abs(p_amount - g_amount) / max(p_amount, g_amount)
                    amount_sim = max(0, 1 - amount_diff)
                    score += amount_sim * 0.3
            except:
                pass
            
            # Date similarity
            if p_row['post_date'] == g_row['post_date']:
                score += 0.2
            
            if score > best_score and score > 0.3:  # Minimum threshold
                best_score = score
                best_match = g_row
                best_g_idx = g_idx
        
        if best_match:
            matches.append({
                'parser_idx': p_idx,
                'golden_idx': best_g_idx,
                'parser_row': p_row,
                'golden_row': best_match,
                'score': best_score
            })
            used_golden.add(best_g_idx)
    
    return matches

def analyze_matches(matches):
    """Analyze the quality of matches"""
    if not matches:
        print("No matches found!")
        return
    
    print(f"Found {len(matches)} matches")
    print("\n=== TOP 10 MATCHES ===")
    
    # Sort by score
    matches.sort(key=lambda x: x['score'], reverse=True)
    
    field_matches = {
        'desc_raw': 0,
        'amount_brl': 0, 
        'post_date': 0,
        'card_last4': 0,
        'merchant_city': 0,
        'category': 0
    }
    
    for i, match in enumerate(matches[:10]):
        p_row = match['parser_row']
        g_row = match['golden_row']
        score = match['score']
        
        print(f"\nMatch {i+1} (Score: {score:.3f}):")
        print(f"  Parser: {p_row['desc_raw'][:60]}...")
        print(f"  Golden: {g_row['desc_raw'][:60]}...")
        
        # Check field-by-field matches
        for field in field_matches.keys():
            if field in p_row and field in g_row:
                if field == 'amount_brl':
                    # Normalize amounts for comparison
                    p_val = normalize_amount(p_row[field])
                    g_val = normalize_amount(g_row[field])
                    match_field = abs(p_val - g_val) < 0.01
                else:
                    match_field = p_row[field] == g_row[field]
                
                if match_field:
                    field_matches[field] += 1
                    print(f"    ✅ {field}: {p_row[field]}")
                else:
                    print(f"    ❌ {field}: {p_row[field]} vs {g_row[field]}")
    
    # Overall statistics
    total_matches = len(matches)
    print(f"\n=== OVERALL FIELD ACCURACY ===")
    for field, count in field_matches.items():
        accuracy = (count / total_matches) * 100 if total_matches > 0 else 0
        print(f"{field}: {count}/{total_matches} ({accuracy:.1f}%)")
    
    # Calculate overall accuracy
    total_possible = total_matches * len(field_matches)
    total_correct = sum(field_matches.values())
    overall_accuracy = (total_correct / total_possible) * 100 if total_possible > 0 else 0
    
    print(f"\nOVERALL ACCURACY: {total_correct}/{total_possible} ({overall_accuracy:.1f}%)")

def main():
    import sys
    if len(sys.argv) >= 3:
        parser_file = sys.argv[1]
        golden_file = sys.argv[2]
    else:
        parser_file = "test_output/Itau_2025-05_parsed.csv"
        golden_file = "golden_2025-05.csv"
    
    if not (Path(parser_file).exists() and Path(golden_file).exists()):
        print(f"Files not found: {parser_file} or {golden_file}")
        return
    
    parser_data = load_csv(parser_file)
    golden_data = load_csv(golden_file)
    
    print(f"Parser transactions: {len(parser_data)}")
    print(f"Golden transactions: {len(golden_data)}")
    
    matches = find_best_matches(parser_data, golden_data)
    analyze_matches(matches)
    
    # Coverage statistics
    coverage = (len(matches) / len(golden_data)) * 100 if golden_data else 0
    print(f"\nCOVERAGE: {len(matches)}/{len(golden_data)} ({coverage:.1f}%) of golden transactions matched")

if __name__ == "__main__":
    main()
