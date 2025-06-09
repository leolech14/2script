#!/usr/bin/env python3
"""
Process All PDFs - Batch PDF Processing Script
==============================================

Processes all PDFs in all_pdfs/ directory using our best extraction pipeline.
Creates individual CSV outputs for each PDF in all_pdfs_output/ directory.
"""

import os
import subprocess
import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_single_pdf(pdf_path, output_dir):
    """Process a single PDF using our best pipeline"""
    pdf_name = Path(pdf_path).stem
    logger.info(f"Processing {pdf_name}...")
    
    # Create output directory for this PDF
    pdf_output_dir = output_dir / pdf_name
    pdf_output_dir.mkdir(exist_ok=True)
    
    try:
        # Step 1: Run parallel transaction splitter
        parallel_csv = pdf_output_dir / f"{pdf_name}_parallel.csv"
        logger.info(f"  Step 1: Parallel transaction splitting...")
        result1 = subprocess.run([
            'python', 'parallel_transaction_splitter.py', 
            str(pdf_path), '-o', str(parallel_csv)
        ], capture_output=True, text=True, timeout=120)
        
        if result1.returncode != 0:
            logger.error(f"  Parallel splitter failed for {pdf_name}: {result1.stderr}")
            return False
            
        # Step 2: Card number mapping
        cards_csv = pdf_output_dir / f"{pdf_name}_cards.csv"
        logger.info(f"  Step 2: Card number mapping...")
        result2 = subprocess.run([
            'python', 'card_number_mapper.py', 
            str(parallel_csv), str(pdf_path), '-o', str(cards_csv)
        ], capture_output=True, text=True, timeout=60)
        
        if result2.returncode != 0:
            logger.error(f"  Card mapper failed for {pdf_name}: {result2.stderr}")
            return False
            
        # Step 3: Precision field mapping (final output)
        final_csv = pdf_output_dir / f"{pdf_name}_final.csv"
        logger.info(f"  Step 3: Precision field mapping...")
        result3 = subprocess.run([
            'python', 'precision_field_mapper.py', 
            str(cards_csv), '-o', str(final_csv)
        ], capture_output=True, text=True, timeout=60)
        
        if result3.returncode != 0:
            logger.error(f"  Precision mapper failed for {pdf_name}: {result3.stderr}")
            return False
            
        # Count final transactions
        with open(final_csv, 'r') as f:
            transaction_count = len(f.readlines()) - 1  # subtract header
            
        logger.info(f"  ✅ {pdf_name} completed: {transaction_count} transactions")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error(f"  ⏰ Timeout processing {pdf_name}")
        return False
    except Exception as e:
        logger.error(f"  ❌ Error processing {pdf_name}: {e}")
        return False

def main():
    """Main processing function"""
    # Setup directories
    pdf_dir = Path('all_pdfs')
    output_dir = Path('all_pdfs_output')
    output_dir.mkdir(exist_ok=True)
    
    # Find all PDFs
    pdf_files = sorted(pdf_dir.glob('*.pdf'))
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF
    success_count = 0
    failed_pdfs = []
    
    for pdf_file in pdf_files:
        success = process_single_pdf(pdf_file, output_dir)
        if success:
            success_count += 1
        else:
            failed_pdfs.append(pdf_file.name)
    
    # Summary
    logger.info(f"\n📊 PROCESSING SUMMARY:")
    logger.info(f"  Total PDFs: {len(pdf_files)}")
    logger.info(f"  Successful: {success_count}")
    logger.info(f"  Failed: {len(failed_pdfs)}")
    
    if failed_pdfs:
        logger.info(f"  Failed files: {', '.join(failed_pdfs)}")
    
    logger.info(f"\n✅ Processing complete! Check 'all_pdfs_output/' for results.")

if __name__ == '__main__':
    main()
