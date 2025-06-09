#!/usr/bin/env python3
"""
Comprehensive Analysis of All PDF Processing Results
===================================================

Analyzes all 14 processed PDFs and provides detailed insights
without requiring MCP servers (using pandas for analysis).
"""

import pandas as pd
import os
from pathlib import Path
import json
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_all_csvs():
    """Load all final CSV outputs"""
    results = {}
    output_dir = Path('all_pdfs_output')
    
    for pdf_dir in output_dir.iterdir():
        if pdf_dir.is_dir():
            final_csv = pdf_dir / f"{pdf_dir.name}_final.csv"
            if final_csv.exists():
                try:
                    df = pd.read_csv(final_csv, delimiter=';')
                    results[pdf_dir.name] = df
                    logger.info(f"Loaded {pdf_dir.name}: {len(df)} transactions")
                except Exception as e:
                    logger.error(f"Error loading {pdf_dir.name}: {e}")
    
    return results

def analyze_comprehensive():
    """Comprehensive analysis of all data"""
    logger.info("Starting comprehensive analysis...")
    
    # Load all data
    all_data = load_all_csvs()
    
    if not all_data:
        logger.error("No data loaded!")
        return
    
    # Combine all data for global analysis
    combined_df = pd.concat(all_data.values(), ignore_index=True)
    
    # Basic statistics
    stats = {
        'total_pdfs': len(all_data),
        'total_transactions': len(combined_df),
        'date_range': {
            'start': combined_df['post_date'].min(),
            'end': combined_df['post_date'].max()
        }
    }
    
    # Transaction count by period
    period_stats = {}
    for period, df in all_data.items():
        period_stats[period] = {
            'transaction_count': len(df),
            'unique_cards': df['card_last4'].nunique(),
            'total_amount': df['amount_brl'].sum(),
            'categories': df['category'].value_counts().to_dict(),
            'top_merchants': df['desc_raw'].str[:20].value_counts().head(5).to_dict()
        }
    
    # Global analysis
    global_analysis = {
        'unique_cards': combined_df['card_last4'].nunique(),
        'total_amount': combined_df['amount_brl'].sum(),
        'category_distribution': combined_df['category'].value_counts().to_dict(),
        'merchant_cities': combined_df['merchant_city'].value_counts().head(10).to_dict(),
        'average_transaction': combined_df['amount_brl'].mean(),
        'max_transaction': combined_df['amount_brl'].max(),
        'min_transaction': combined_df['amount_brl'].min()
    }
    
    # Monthly trends (handle date parsing issues)
    try:
        # Clean and parse dates more carefully
        combined_df['post_date_clean'] = pd.to_datetime(combined_df['post_date'], format='%Y-%m-%d', errors='coerce')
        combined_df = combined_df.dropna(subset=['post_date_clean'])
        combined_df['year_month'] = combined_df['post_date_clean'].dt.to_period('M')
        monthly_trends = combined_df.groupby('year_month').agg({
            'amount_brl': ['count', 'sum', 'mean'],
            'card_last4': 'nunique'
        }).round(2)
    except Exception as e:
        logger.warning(f"Date parsing issue: {e}")
        monthly_trends = pd.DataFrame()
    
    # Card analysis
    card_analysis = combined_df.groupby('card_last4').agg({
        'amount_brl': ['count', 'sum', 'mean'],
        'category': lambda x: x.value_counts().index[0]  # most common category
    }).round(2)
    
    # Category trends
    category_trends = combined_df.groupby(['category']).agg({
        'amount_brl': ['count', 'sum', 'mean']
    }).round(2)
    
    # FX transactions analysis
    fx_transactions = combined_df[combined_df['fx_rate'] > 0]
    fx_analysis = {
        'total_fx_transactions': len(fx_transactions),
        'fx_percentage': (len(fx_transactions) / len(combined_df) * 100),
        'average_fx_rate': fx_transactions['fx_rate'].mean(),
        'fx_currencies': fx_transactions['currency_orig'].value_counts().to_dict(),
        'fx_cities': fx_transactions['merchant_city'].value_counts().head(5).to_dict()
    }
    
    # Create comprehensive report
    report = {
        'summary': stats,
        'period_breakdown': period_stats,
        'global_analysis': global_analysis,
        'fx_analysis': fx_analysis,
        'monthly_trends': monthly_trends.to_dict(),
        'card_analysis': card_analysis.to_dict(),
        'category_trends': category_trends.to_dict()
    }
    
    return report, combined_df

def create_markdown_report(report):
    """Create a detailed markdown report"""
    md = "# 📊 Comprehensive Analysis: 14-Month Itaú Statement Processing\n\n"
    
    # Summary
    md += "## 🎯 **Executive Summary**\n\n"
    md += f"- **Total PDFs Processed:** {report['summary']['total_pdfs']}\n"
    md += f"- **Total Transactions:** {report['summary']['total_transactions']:,}\n"
    md += f"- **Date Range:** {report['summary']['date_range']['start']} to {report['summary']['date_range']['end']}\n"
    md += f"- **Unique Cards:** {report['global_analysis']['unique_cards']}\n"
    md += f"- **Total Amount:** R$ {report['global_analysis']['total_amount']:,.2f}\n\n"
    
    # Period breakdown
    md += "## 📈 **Transaction Volume by Period**\n\n"
    md += "| Period | Transactions | Unique Cards | Total Amount (R$) | Top Category |\n"
    md += "|--------|--------------|--------------|-------------------|-------------|\n"
    
    for period, stats in sorted(report['period_breakdown'].items()):
        top_category = max(stats['categories'], key=stats['categories'].get) if stats['categories'] else 'N/A'
        md += f"| {period} | {stats['transaction_count']:,} | {stats['unique_cards']} | {stats['total_amount']:,.2f} | {top_category} |\n"
    
    md += "\n"
    
    # Global insights
    md += "## 🔍 **Key Insights**\n\n"
    md += f"- **Average Transaction:** R$ {report['global_analysis']['average_transaction']:.2f}\n"
    md += f"- **Largest Transaction:** R$ {report['global_analysis']['max_transaction']:,.2f}\n"
    md += f"- **Smallest Transaction:** R$ {report['global_analysis']['min_transaction']:,.2f}\n\n"
    
    # Category distribution
    md += "### **Category Distribution**\n\n"
    for category, count in sorted(report['global_analysis']['category_distribution'].items(), 
                                key=lambda x: x[1], reverse=True)[:10]:
        percentage = (count / report['summary']['total_transactions']) * 100
        md += f"- **{category}**: {count:,} transactions ({percentage:.1f}%)\n"
    
    md += "\n"
    
    # FX Analysis
    if report['fx_analysis']['total_fx_transactions'] > 0:
        md += "### **International Transactions (FX)**\n\n"
        md += f"- **FX Transactions:** {report['fx_analysis']['total_fx_transactions']:,} ({report['fx_analysis']['fx_percentage']:.1f}%)\n"
        md += f"- **Average FX Rate:** {report['fx_analysis']['average_fx_rate']:.4f}\n"
        md += f"- **Top FX Currencies:** {', '.join(report['fx_analysis']['fx_currencies'].keys())}\n"
        md += f"- **Top FX Cities:** {', '.join(list(report['fx_analysis']['fx_cities'].keys())[:3])}\n\n"
    
    # Top merchant cities
    md += "### **Top Merchant Cities**\n\n"
    for city, count in list(report['global_analysis']['merchant_cities'].items())[:5]:
        if city and str(city) != 'nan':
            md += f"- **{city}**: {count:,} transactions\n"
    
    md += "\n---\n\n"
    md += f"**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    md += f"**Data Source:** All 14 processed Itaú PDF statements\n"
    
    return md

def main():
    """Main analysis function"""
    logger.info("🚀 Starting comprehensive analysis of all processed PDFs...")
    
    # Run analysis
    report, combined_df = analyze_comprehensive()
    
    # Create markdown report
    markdown_report = create_markdown_report(report)
    
    # Save results
    with open('all_pdfs_output/COMPREHENSIVE_ANALYSIS.json', 'w') as f:
        # Convert numpy types to Python types for JSON serialization
        json.dump(report, f, indent=2, default=str)
    
    with open('all_pdfs_output/COMPREHENSIVE_ANALYSIS.md', 'w') as f:
        f.write(markdown_report)
    
    # Save combined dataset
    combined_df.to_csv('all_pdfs_output/COMBINED_ALL_TRANSACTIONS.csv', index=False, sep=';')
    
    logger.info("✅ Analysis complete!")
    logger.info(f"📊 Total transactions analyzed: {len(combined_df):,}")
    logger.info(f"📁 Reports saved in all_pdfs_output/")
    
    # Print summary
    print("\n" + "="*60)
    print("📊 COMPREHENSIVE ANALYSIS SUMMARY")
    print("="*60)
    print(f"Total PDFs: {report['summary']['total_pdfs']}")
    print(f"Total Transactions: {report['summary']['total_transactions']:,}")
    print(f"Total Amount: R$ {report['global_analysis']['total_amount']:,.2f}")
    print(f"Unique Cards: {report['global_analysis']['unique_cards']}")
    print(f"Date Range: {report['summary']['date_range']['start']} to {report['summary']['date_range']['end']}")
    print("="*60)

if __name__ == '__main__':
    main()
