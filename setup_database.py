#!/usr/bin/env python3
"""
Database Setup for Itaú Parser Analytics
========================================

Sets up PostgreSQL database schema and imports all transaction data
for advanced analytics and gap analysis.
"""

import logging
import sys
from pathlib import Path

import pandas as pd
import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'itau_parser',
    'user': 'postgres',
    'password': 'password123'
}

def connect_db():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("✅ Connected to PostgreSQL")
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return None

def create_schema(conn):
    """Create database schema for analytics"""
    logger.info("📋 Creating database schema...")

    schema_sql = """
    -- Create main schema
    CREATE SCHEMA IF NOT EXISTS itau_parser;
    
    -- Main transactions table
    CREATE TABLE IF NOT EXISTS itau_parser.transactions (
        id SERIAL PRIMARY KEY,
        source_pdf VARCHAR(50) NOT NULL,
        card_last4 VARCHAR(4),
        post_date DATE,
        desc_raw TEXT,
        amount_brl DECIMAL(10,2),
        installment_seq INTEGER,
        installment_tot INTEGER,
        fx_rate DECIMAL(8,4),
        iof_brl DECIMAL(10,2),
        category VARCHAR(50),
        merchant_city VARCHAR(100),
        ledger_hash VARCHAR(64),
        prev_bill_amount DECIMAL(10,2),
        interest_amount DECIMAL(10,2),
        amount_orig DECIMAL(10,2),
        currency_orig VARCHAR(3),
        amount_usd DECIMAL(10,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Golden reference transactions
    CREATE TABLE IF NOT EXISTS itau_parser.golden_transactions (
        id SERIAL PRIMARY KEY,
        source_file VARCHAR(50) NOT NULL,
        card_last4 VARCHAR(4),
        post_date DATE,
        desc_raw TEXT,
        amount_brl DECIMAL(10,2),
        installment_seq INTEGER,
        installment_tot INTEGER,
        fx_rate DECIMAL(8,4),
        iof_brl DECIMAL(10,2),
        category VARCHAR(50),
        merchant_city VARCHAR(100),
        ledger_hash VARCHAR(64),
        prev_bill_amount DECIMAL(10,2),
        interest_amount DECIMAL(10,2),
        amount_orig DECIMAL(10,2),
        currency_orig VARCHAR(3),
        amount_usd DECIMAL(10,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Processing runs tracking
    CREATE TABLE IF NOT EXISTS itau_parser.parsing_runs (
        id SERIAL PRIMARY KEY,
        pdf_filename VARCHAR(255) NOT NULL,
        run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        parser_version VARCHAR(50),
        total_transactions INTEGER,
        matched_transactions INTEGER,
        accuracy_rate DECIMAL(5,2),
        config_hash VARCHAR(64)
    );
    
    -- Merchant categorization learning
    CREATE TABLE IF NOT EXISTS itau_parser.merchant_categories (
        id SERIAL PRIMARY KEY,
        merchant_name VARCHAR(255),
        learned_category VARCHAR(100),
        confidence_score DECIMAL(3,2),
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Performance metrics
    CREATE TABLE IF NOT EXISTS itau_parser.performance_metrics (
        id SERIAL PRIMARY KEY,
        metric_name VARCHAR(100),
        metric_value DECIMAL(10,2),
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_transactions_card_date ON itau_parser.transactions(card_last4, post_date);
    CREATE INDEX IF NOT EXISTS idx_transactions_category ON itau_parser.transactions(category);
    CREATE INDEX IF NOT EXISTS idx_transactions_hash ON itau_parser.transactions(ledger_hash);
    CREATE INDEX IF NOT EXISTS idx_golden_hash ON itau_parser.golden_transactions(ledger_hash);
    """

    try:
        cursor = conn.cursor()
        cursor.execute(schema_sql)
        conn.commit()
        cursor.close()
        logger.info("✅ Database schema created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Schema creation failed: {e}")
        return False

def import_transactions(conn):
    """Import all transactions from CSV files"""
    logger.info("📊 Importing transaction data...")

    # Load combined transactions
    combined_csv = Path('all_pdfs_output/ALL_TRANSACTIONS_COMBINED.csv')
    if not combined_csv.exists():
        logger.error("❌ Combined CSV file not found")
        return False

    try:
        df = pd.read_csv(combined_csv, delimiter=';')
        logger.info(f"📁 Loaded {len(df)} transactions from combined CSV")

        # Add source PDF info (extract from directory structure)
        df['source_pdf'] = 'combined'  # We'll update this with actual sources

        # Clean data
        df['post_date'] = pd.to_datetime(df['post_date'], format='%Y-%m-%d', errors='coerce')
        df = df.dropna(subset=['post_date'])  # Remove invalid dates

        # Convert to database format
        df = df.where(pd.notnull(df), None)  # Replace NaN with None for PostgreSQL

        # Insert data
        cursor = conn.cursor()

        insert_sql = """
        INSERT INTO itau_parser.transactions 
        (source_pdf, card_last4, post_date, desc_raw, amount_brl, installment_seq, 
         installment_tot, fx_rate, iof_brl, category, merchant_city, ledger_hash,
         prev_bill_amount, interest_amount, amount_orig, currency_orig, amount_usd)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Prepare data for insertion
        records = []
        for _, row in df.iterrows():
            record = (
                row.get('source_pdf', 'combined'),
                row.get('card_last4'),
                row.get('post_date'),
                row.get('desc_raw'),
                row.get('amount_brl'),
                row.get('installment_seq'),
                row.get('installment_tot'),
                row.get('fx_rate'),
                row.get('iof_brl'),
                row.get('category'),
                row.get('merchant_city'),
                row.get('ledger_hash'),
                row.get('prev_bill_amount'),
                row.get('interest_amount'),
                row.get('amount_orig'),
                row.get('currency_orig'),
                row.get('amount_usd')
            )
            records.append(record)

        cursor.executemany(insert_sql, records)
        conn.commit()
        cursor.close()

        logger.info(f"✅ Imported {len(records)} transactions successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Transaction import failed: {e}")
        return False

def import_golden_data(conn):
    """Import golden reference data"""
    logger.info("🏆 Importing golden reference data...")

    golden_files = ['golden_2025-05.csv', 'golden_2024-10.csv']
    total_imported = 0

    for golden_file in golden_files:
        if Path(golden_file).exists():
            try:
                df = pd.read_csv(golden_file, delimiter=';')
                df['source_file'] = golden_file
                df['post_date'] = pd.to_datetime(df['post_date'], format='%Y-%m-%d', errors='coerce')
                df = df.dropna(subset=['post_date'])
                df = df.where(pd.notnull(df), None)

                cursor = conn.cursor()
                insert_sql = """
                INSERT INTO itau_parser.golden_transactions 
                (source_file, card_last4, post_date, desc_raw, amount_brl, installment_seq, 
                 installment_tot, fx_rate, iof_brl, category, merchant_city, ledger_hash,
                 prev_bill_amount, interest_amount, amount_orig, currency_orig, amount_usd)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                records = []
                for _, row in df.iterrows():
                    record = (
                        golden_file,
                        row.get('card_last4'),
                        row.get('post_date'),
                        row.get('desc_raw'),
                        row.get('amount_brl'),
                        row.get('installment_seq'),
                        row.get('installment_tot'),
                        row.get('fx_rate'),
                        row.get('iof_brl'),
                        row.get('category'),
                        row.get('merchant_city'),
                        row.get('ledger_hash'),
                        row.get('prev_bill_amount'),
                        row.get('interest_amount'),
                        row.get('amount_orig'),
                        row.get('currency_orig'),
                        row.get('amount_usd')
                    )
                    records.append(record)

                cursor.executemany(insert_sql, records)
                conn.commit()
                cursor.close()

                total_imported += len(records)
                logger.info(f"✅ Imported {len(records)} golden transactions from {golden_file}")

            except Exception as e:
                logger.error(f"❌ Failed to import {golden_file}: {e}")

    logger.info(f"🏆 Total golden transactions imported: {total_imported}")
    return total_imported > 0

def verify_setup(conn):
    """Verify database setup"""
    logger.info("🔍 Verifying database setup...")

    try:
        cursor = conn.cursor()

        # Check transaction count
        cursor.execute("SELECT COUNT(*) FROM itau_parser.transactions")
        transaction_count = cursor.fetchone()[0]

        # Check golden count
        cursor.execute("SELECT COUNT(*) FROM itau_parser.golden_transactions")
        golden_count = cursor.fetchone()[0]

        # Check unique cards
        cursor.execute("SELECT COUNT(DISTINCT card_last4) FROM itau_parser.transactions WHERE card_last4 IS NOT NULL")
        unique_cards = cursor.fetchone()[0]

        cursor.close()

        logger.info("📊 Database verification:")
        logger.info(f"  - Transactions: {transaction_count:,}")
        logger.info(f"  - Golden references: {golden_count:,}")
        logger.info(f"  - Unique cards: {unique_cards}")

        return transaction_count > 0

    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False

def main():
    """Main setup function"""
    logger.info("🚀 Setting up Itaú Parser Analytics Database")
    logger.info("="*60)

    # Connect to database
    conn = connect_db()
    if not conn:
        sys.exit(1)

    try:
        # Create schema
        if not create_schema(conn):
            sys.exit(1)

        # Import transaction data
        if not import_transactions(conn):
            sys.exit(1)

        # Import golden data
        import_golden_data(conn)

        # Verify setup
        if verify_setup(conn):
            logger.info("✅ Database setup completed successfully!")
            logger.info("🎯 Ready for advanced analytics and gap analysis")
        else:
            logger.error("❌ Database verification failed")
            sys.exit(1)

    finally:
        conn.close()
        logger.info("🔌 Database connection closed")

if __name__ == '__main__':
    main()
