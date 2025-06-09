#!/usr/bin/env python3
"""
PDF to Text Extractor for Itaú Credit Card Statements
Provides reliable PDF-to-text conversion for use with text parsing scripts.
"""

import argparse
import logging
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Please install pdfplumber: pip install pdfplumber")
    exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_pdf_to_text(pdf_path: Path, output_path: Path | None = None) -> str:
    """
    Extract text from PDF file and optionally save to text file.
    
    Args:
        pdf_path: Path to input PDF file
        output_path: Optional path to save extracted text
        
    Returns:
        Extracted text as string
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    logger.info(f"Extracting text from {pdf_path}")

    text_lines = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        logger.info(f"PDF has {len(pdf.pages)} pages")

        for page_num, page in enumerate(pdf.pages, 1):
            logger.debug(f"Processing page {page_num}")

            text = page.extract_text()
            if text is None:
                logger.warning(f"Page {page_num} has no extractable text")
                continue

            # Clean and split into lines
            for line in text.splitlines():
                line = line.strip()
                if line:  # Only keep non-empty lines
                    text_lines.append(line)

    full_text = '\n'.join(text_lines)
    logger.info(f"Extracted {len(text_lines)} non-empty lines")

    # Save to file if output path provided
    if output_path:
        output_path.write_text(full_text, encoding='utf-8')
        logger.info(f"Text saved to {output_path}")

    return full_text


def main():
    parser = argparse.ArgumentParser(
        description="Extract text from Itaú PDF credit card statements"
    )
    parser.add_argument("pdf", type=Path, help="Input PDF file")
    parser.add_argument("-o", "--output", type=Path, help="Output text file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Generate default output filename if not provided
        output_path = args.output
        if not output_path:
            output_path = args.pdf.with_suffix('.txt')

        extract_pdf_to_text(args.pdf, output_path)
        print(f"Successfully extracted text to {output_path}")

    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        exit(1)


if __name__ == "__main__":
    main()
