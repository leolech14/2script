#!/usr/bin/env python3
"""
Test Runner for Itaú Credit Card Statement Parsers
Tests all three parsing scripts and compares outputs to golden CSVs.
"""

import argparse
import csv
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import json

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class CSVComparator:
    """Utility to compare CSV files and report differences."""
    def __init__(self):
        self.tolerance = 0.01  # For numerical comparisons

    def load_csv(self, path: Path) -> List[Dict]:
        """Load CSV file into list of dictionaries using shared utility."""
        # Use parser_utils for delimiter detection and loading
        from . import parser_utils
        delimiter = ";" if path.suffix == ".csv" else ","
        return parser_utils.load_csv(path, delimiter=delimiter)
    def compare_numeric(self, val1: str, val2: str) -> bool:
        """Compare numeric values with tolerance using shared decomma."""
        try:
            from . import parser_utils
            num1 = float(parser_utils.decomma(val1)) if val1 else 0.0
            num2 = float(parser_utils.decomma(val2)) if val2 else 0.0
            return abs(num1 - num2) <= self.tolerance
        except Exception:
            return val1 == val2
    def compare_csvs(self, actual_path: Path, golden_path: Path) -> Dict:
        """
        Compare actual CSV output with golden CSV.
        Returns comparison results with statistics.
        """
        if not actual_path.exists():
            return {"error": f"Actual file not found: {actual_path}"}
        if not golden_path.exists():
            return {"error": f"Golden file not found: {golden_path}"}
        actual_rows = self.load_csv(actual_path)
        golden_rows = self.load_csv(golden_path)
        result = {
            "actual_count": len(actual_rows),
            "golden_count": len(golden_rows),
            "matches": 0,
            "mismatches": [],
            "missing_from_actual": [],
            "extra_in_actual": [],
            "field_differences": {}
        }
        # Compare row counts
        if len(actual_rows) != len(golden_rows):
            logger.warning(f"Row count mismatch: actual={len(actual_rows)}, golden={len(golden_rows)}")
        # Create lookup dictionaries for comparison
        actual_dict = {self._row_key(row): row for row in actual_rows}
        golden_dict = {self._row_key(row): row for row in golden_rows}
        # Find matches and differences
        for key, golden_row in golden_dict.items():
            if key in actual_dict:
                actual_row = actual_dict[key]
                if self._rows_match(actual_row, golden_row):
                    result["matches"] += 1
                else:
                    result["mismatches"].append({
                        "key": key,
                        "actual": actual_row,
                        "golden": golden_row,
                        "differences": self._find_differences(actual_row, golden_row)
                    })
            else:
                result["missing_from_actual"].append(golden_row)
        # Find extra rows in actual
        for key, actual_row in actual_dict.items():
            if key not in golden_dict:
                result["extra_in_actual"].append(actual_row)
        return result

    def _row_key(self, row: Dict) -> str:
        """Generate a unique key for a row (used for matching)."""
        # Use a combination of fields that should uniquely identify a transaction
        key_fields = ['post_date', 'desc_raw', 'amount_brl']
        key_parts = []
        for field in key_fields:
            val = row.get(field, '')
            key_parts.append(str(val))
        return '|'.join(key_parts)

    def _rows_match(self, actual: Dict, golden: Dict) -> bool:
        """Check if two rows match."""
        for field in actual.keys():
            if field in golden:
                if not self._values_match(actual[field], golden[field], field):
                    return False
        return True

    def _values_match(self, actual: str, golden: str, field: str) -> bool:
        """Check if two field values match."""
        # Numeric fields that should be compared with tolerance
        numeric_fields = ['amount_brl', 'fx_rate', 'iof_brl', 'amount_orig', 'amount_usd']
        if field in numeric_fields:
            return self.compare_numeric(actual, golden)
        else:
            return (actual or "").strip() == (golden or "").strip()

    def _find_differences(self, actual: Dict, golden: Dict) -> List[Dict]:
        """Find specific field differences between two rows."""
        differences = []
        all_fields = set(actual.keys()) | set(golden.keys())
        for field in all_fields:
            actual_val = actual.get(field, '')
            golden_val = golden.get(field, '')
            if not self._values_match(actual_val, golden_val, field):
                differences.append({
                    "field": field,
                    "actual": actual_val,
                    "golden": golden_val
                })
        return differences


class TestRunner:
    """Main test runner for all parsing scripts."""
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("test_outputs")
        self.output_dir.mkdir(exist_ok=True)
        self.comparator = CSVComparator()
    
    def extract_pdf_to_text(self, pdf_path: Path) -> Path:
        """Extract PDF to text using pdf_extractor.py."""
        txt_path = self.output_dir / f"{pdf_path.stem}.txt"
        
        logger.info(f"Extracting {pdf_path} to {txt_path}")
        
        try:
            subprocess.run([
                sys.executable, "pdf_extractor.py", 
                str(pdf_path), "-o", str(txt_path)
            ], check=True, capture_output=True, text=True)
            
            logger.info(f"Successfully extracted to {txt_path}")
            return txt_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"PDF extraction failed: {e}")
            logger.error(f"stderr: {e.stderr}")
            raise
    
    def run_codex_script(self, input_path: Path) -> Path:
        """Run codex.py script."""
        logger.info(f"Running codex.py on {input_path}")
        
        try:
            # codex.py outputs to {stem}_done.csv
            result = subprocess.run([
                sys.executable, "codex.py", str(input_path)
            ], check=True, capture_output=True, text=True)
            
            output_path = input_path.parent / f"{input_path.stem}_done.csv"
            
            if output_path.exists():
                # Move to our test output directory
                final_path = self.output_dir / f"codex_{input_path.stem}.csv"
                output_path.rename(final_path)
                logger.info(f"Codex output: {final_path}")
                return final_path
            else:
                raise FileNotFoundError(f"Expected output file not found: {output_path}")
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Codex script failed: {e}")
            logger.error(f"stderr: {e.stderr}")
            raise
    
    def run_pdf_to_csv_script(self, pdf_path: Path) -> Path:
        """Run pdf_to_csv.py script."""
        output_path = self.output_dir / f"pdf_to_csv_{pdf_path.stem}.csv"
        
        logger.info(f"Running pdf_to_csv.py on {pdf_path}")
        
        try:
            subprocess.run([
                sys.executable, "pdf_to_csv.py", 
                str(pdf_path), "--out", str(output_path)
            ], check=True, capture_output=True, text=True)
            
            logger.info(f"PDF to CSV output: {output_path}")
            return output_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"PDF to CSV script failed: {e}")
            logger.error(f"stderr: {e.stderr}")
            raise
    
    def run_text_to_csv_script(self, txt_path: Path) -> Path:
        """Run text_to_csv.py script (need to create a CLI wrapper)."""
        output_path = self.output_dir / f"text_to_csv_{txt_path.stem}.csv"
        
        logger.info(f"Running text_to_csv.py on {txt_path}")
        
        # text_to_csv.py doesn't have a CLI, so we'll create a simple one
        try:
            import text_to_csv as t2c
            
            rows = []
            with open(txt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        row = t2c.parse_statement_line(line)
                        if row:
                            rows.append(row)
            
            # Write CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                if rows:
                    fieldnames = rows[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
            
            logger.info(f"Text to CSV output: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Text to CSV processing failed: {e}")
            raise
    
    def run_all_tests(self, pdf_files: List[Path], golden_dir: Path = None) -> Dict:
        """Run all three scripts on provided PDF files."""
        results = {}
        
        for pdf_path in pdf_files:
            logger.info(f"\n{'='*60}")
            logger.info(f"Testing with: {pdf_path.name}")
            logger.info(f"{'='*60}")
            
            file_results = {}
            
            try:
                # Extract PDF to text first
                txt_path = self.extract_pdf_to_text(pdf_path)
                
                # Run all three scripts
                codex_output = self.run_codex_script(pdf_path)  # Can handle PDFs directly
                pdf_csv_output = self.run_pdf_to_csv_script(pdf_path)
                text_csv_output = self.run_text_to_csv_script(txt_path)
                
                file_results = {
                    "pdf_path": str(pdf_path),
                    "txt_path": str(txt_path),
                    "outputs": {
                        "codex": str(codex_output),
                        "pdf_to_csv": str(pdf_csv_output),
                        "text_to_csv": str(text_csv_output)
                    },
                    "success": True
                }
                
                # Compare with golden files if provided
                if golden_dir and golden_dir.exists():
                    file_results["comparisons"] = {}
                    
                    for script_name, output_path in file_results["outputs"].items():
                        golden_file = golden_dir / f"{script_name}_{pdf_path.stem}.csv"
                        if golden_file.exists():
                            comparison = self.comparator.compare_csvs(
                                Path(output_path), golden_file
                            )
                            file_results["comparisons"][script_name] = comparison
                            
                            # Log comparison summary
                            if "error" not in comparison:
                                match_rate = comparison["matches"] / max(comparison["golden_count"], 1) * 100
                                logger.info(f"{script_name}: {comparison['matches']}/{comparison['golden_count']} matches ({match_rate:.1f}%)")
                        else:
                            logger.warning(f"Golden file not found: {golden_file}")
                
            except Exception as e:
                logger.error(f"Failed processing {pdf_path.name}: {e}")
                file_results = {
                    "pdf_path": str(pdf_path),
                    "success": False,
                    "error": str(e)
                }
            
            results[pdf_path.name] = file_results
        
        return results
    
    def generate_report(self, results: Dict, output_file: Path = None):
        """Generate a comprehensive test report."""
        if output_file is None:
            output_file = self.output_dir / "test_report.json"
        
        # Save detailed results as JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Print summary to console
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        
        total_files = len(results)
        successful_files = sum(1 for r in results.values() if r.get("success", False))
        
        print(f"Files processed: {successful_files}/{total_files}")
        print(f"Output directory: {self.output_dir}")
        print(f"Detailed report: {output_file}")
        
        # Summary by script
        if successful_files > 0:
            print(f"\nScript outputs generated:")
            for file_name, file_result in results.items():
                if file_result.get("success", False):
                    print(f"  {file_name}:")
                    for script, output_path in file_result["outputs"].items():
                        print(f"    {script}: {Path(output_path).name}")
        
        logger.info(f"Test report saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Test all Itaú statement parsing scripts"
    )
    parser.add_argument("pdfs", nargs="+", type=Path, help="PDF files to test")
    parser.add_argument("--golden-dir", type=Path, help="Directory with golden CSV files")
    parser.add_argument("--output-dir", type=Path, default=Path("test_outputs"), 
                       help="Output directory for test results")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate input files
    pdf_files = []
    for pdf_path in args.pdfs:
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            continue
        if pdf_path.suffix.lower() != '.pdf':
            logger.error(f"Not a PDF file: {pdf_path}")
            continue
        pdf_files.append(pdf_path)
    
    if not pdf_files:
        logger.error("No valid PDF files provided")
        sys.exit(1)
    
    # Run tests
    runner = TestRunner(args.output_dir)
    results = runner.run_all_tests(pdf_files, args.golden_dir)
    runner.generate_report(results)


if __name__ == "__main__":
    main()
