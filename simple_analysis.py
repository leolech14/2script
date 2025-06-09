#!/usr/bin/env python3
"""
Simple Analysis of All PDF Results
==================================
"""

import pandas as pd
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Simple comprehensive analysis"""
    logger.info("📊 Starting simple analysis...")
    
    # Load all data
    all_data = {}
    output_dir = Path('all_pdfs_output')
    
    for pdf_dir in output_dir.iterdir():
        if pdf_dir.is_dir():
            final_csv = pdf_dir / f"{pdf_dir.name}_final.csv"
            if final_csv.exists():
                try:
                    df = pd.read_csv(final_csv, delimiter=';')
                    all_data[pdf_dir.name] = df
                    logger.info(f"✅ {pdf_dir.name}: {len(df)} transactions")
                except Exception as e:
                    logger.error(f"❌ {pdf_dir.name}: {e}")
    
    if not all_data:
        logger.error("No data found!")
        return
    
    # Combine all data
    combined_df = pd.concat(all_data.values(), ignore_index=True)
    logger.info(f"📊 Total combined: {len(combined_df)} transactions")
    
    # Basic statistics
    total_amount = combined_df['amount_brl'].sum()
    unique_cards = combined_df['card_last4'].nunique()
    categories = combined_df['category'].value_counts()
    
    # Create summary report
    report = f"""# 📊 14-Month Itaú Statement Analysis Summary

## 🎯 **Overview**
- **Total PDFs:** {len(all_data)}
- **Total Transactions:** {len(combined_df):,}
- **Total Amount:** R$ {total_amount:,.2f}
- **Unique Cards:** {unique_cards}

## 📈 **Transaction Counts by Period**

| Period | Transactions |
|--------|--------------|
"""
    
    for period in sorted(all_data.keys()):
        count = len(all_data[period])
        report += f"| {period} | {count:,} |\n"
    
    report += f"""
## 🏷️ **Top Categories**

"""
    
    for category, count in categories.head(10).items():
        percentage = (count / len(combined_df)) * 100
        report += f"- **{category}**: {count:,} ({percentage:.1f}%)\n"
    
    # Card analysis
    card_stats = combined_df.groupby('card_last4').agg({
        'amount_brl': ['count', 'sum']
    }).round(2)
    
    report += f"""
## 💳 **Card Usage**

"""
    
    for card in combined_df['card_last4'].unique():
        if pd.notna(card):
            card_df = combined_df[combined_df['card_last4'] == card]
            count = len(card_df)
            total = card_df['amount_brl'].sum()
            report += f"- **Card {card}**: {count:,} transactions, R$ {total:,.2f}\n"
    
    # FX analysis
    fx_df = combined_df[combined_df['fx_rate'] > 0]
    if len(fx_df) > 0:
        report += f"""
## 🌍 **International Transactions**

- **FX Transactions:** {len(fx_df):,} ({len(fx_df)/len(combined_df)*100:.1f}%)
- **Average FX Rate:** {fx_df['fx_rate'].mean():.4f}
- **FX Currencies:** {', '.join(fx_df['currency_orig'].dropna().unique())}
"""
    
    report += f"""
---
**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    # Save files
    with open('all_pdfs_output/SIMPLE_ANALYSIS.md', 'w') as f:
        f.write(report)
    
    combined_df.to_csv('all_pdfs_output/ALL_TRANSACTIONS_COMBINED.csv', index=False, sep=';')
    
    # Print summary
    print("\n" + "="*60)
    print("📊 ANALYSIS COMPLETE")
    print("="*60)
    print(f"📁 Processed: {len(all_data)} PDF periods")
    print(f"📈 Total transactions: {len(combined_df):,}")
    print(f"💰 Total amount: R$ {total_amount:,.2f}")
    print(f"💳 Unique cards: {unique_cards}")
    print(f"🏷️ Top category: {categories.index[0]} ({categories.iloc[0]:,} transactions)")
    print("="*60)
    print("📁 Files created:")
    print("  - all_pdfs_output/SIMPLE_ANALYSIS.md")
    print("  - all_pdfs_output/ALL_TRANSACTIONS_COMBINED.csv")
    print("="*60)

if __name__ == '__main__':
    main()
