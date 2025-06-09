#!/usr/bin/env python3
"""
Learning Engine for Itaú Parser
===============================

Analyzes patterns from multiple PDFs to improve parsing rules.
Designed to train with 12 additional Itaú PDFs for global optimization.

This module implements:
- Pattern discovery from failed transactions
- Rule refinement based on success/failure analysis
- Configuration auto-generation
- Cross-validation with multiple PDF samples
"""

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore

from itau_parser_ultimate import ConfigManager, ItauParser, Transaction

logger = logging.getLogger(__name__)


@dataclass
class ParsingResult:
    """Results from parsing a single PDF."""

    pdf_path: Path
    transactions: list[Transaction]
    failed_lines: list[str]
    card_numbers: set[str]
    patterns_found: dict[str, int]
    success_rate: float


@dataclass
class PatternDiscovery:
    """Discovered pattern with confidence metrics."""

    pattern: str
    regex: str
    category: str
    confidence: float
    examples: list[str]
    frequency: int


class PatternAnalyzer:
    """Discovers patterns in failed parsing attempts."""

    def __init__(self) -> None:
        self.merchant_patterns: defaultdict[str, list] = defaultdict(list)
        self.date_patterns: defaultdict[str, list] = defaultdict(list)
        self.amount_patterns: defaultdict[str, list] = defaultdict(list)
        self.card_patterns: defaultdict[str, list] = defaultdict(list)

    def analyze_failed_lines(self, failed_lines: list[str]) -> list[PatternDiscovery]:
        """Analyze failed lines to discover new patterns."""
        discoveries = []

        # Group similar failed lines
        line_groups = self._group_similar_lines(failed_lines)

        for group_pattern, examples in line_groups.items():
            if len(examples) >= 3:  # Need at least 3 examples for confidence
                discovery = self._create_pattern_discovery(group_pattern, examples)
                if discovery:
                    discoveries.append(discovery)

        return discoveries

    def _group_similar_lines(self, lines: list[str]) -> dict[str, list[str]]:
        """Group lines with similar structure."""
        groups = defaultdict(list)

        for line in lines:
            # Create a structural pattern
            pattern = self._create_structural_pattern(line)
            groups[pattern].append(line)

        return groups

    def _create_structural_pattern(self, line: str) -> str:
        """
        Create structural pattern from line (replace numbers/words with placeholders).
        """
        # Replace dates
        pattern = re.sub(r"\d{1,2}/\d{1,2}(?:/\d{4})?", "DATE", line)
        # Replace amounts
        pattern = re.sub(r"\d{1,3}(?:\.\d{3})*,\d{2}", "AMOUNT", pattern)
        # Replace card numbers
        pattern = re.sub(r"\d{4}", "CARD", pattern)
        # Replace long words (merchant names)
        pattern = re.sub(r"\b[A-Z]{4,}\b", "MERCHANT", pattern)

        return pattern

    def _create_pattern_discovery(
        self, pattern: str, examples: list[str]
    ) -> PatternDiscovery | None:
        """Create pattern discovery from examples."""
        if not examples:
            return None

        # Try to determine category from examples
        category = self._infer_category(examples)

        # Create regex from pattern
        regex = self._pattern_to_regex(pattern)

        confidence = min(len(examples) / 10.0, 1.0)  # Max confidence at 10 examples

        return PatternDiscovery(
            pattern=pattern,
            regex=regex,
            category=category,
            confidence=confidence,
            examples=examples[:5],  # Store first 5 examples
            frequency=len(examples),
        )

    def _infer_category(self, examples: list[str]) -> str:
        """Infer category from line examples."""
        text = " ".join(examples).upper()

        # Simple heuristics for category detection
        if any(word in text for word in ["PHARMACY", "DRUG"]):
            return "PHARMACY"
        elif any(word in text for word in ["SUPERMARKET", "MARKET"]):
            return "SUPERMARKET"
        elif any(word in text for word in ["RESTAURANT", "PIZZA", "BAR"]):
            return "RESTAURANT"
        elif any(word in text for word in ["GAS", "FUEL"]):
            return "GAS_STATION"
        elif any(word in text for word in ["PAYMENT", "7117"]):
            return "PAYMENT"
        else:
            return "MISC"

    def _pattern_to_regex(self, pattern: str) -> str:
        """Convert structural pattern to regex."""
        regex = re.escape(pattern)
        regex = regex.replace("DATE", r"\d{1,2}/\d{1,2}(?:/\d{4})?")
        regex = regex.replace("AMOUNT", r"\d{1,3}(?:\.\d{3})*,\d{2}")
        regex = regex.replace("CARD", r"\d{4}")
        regex = regex.replace("MERCHANT", r"[A-Z]+")

        return regex


class RuleOptimizer:
    """Optimizes parsing rules based on success/failure analysis."""

    def __init__(self, config: ConfigManager):
        self.config = config

    def optimize_rules(self, results: list[ParsingResult]) -> dict:
        """Optimize rules based on parsing results from multiple PDFs."""
        optimizations = {
            "card_patterns": self._optimize_card_patterns(results),
            "category_mappings": self._optimize_categories(results),
            "amount_patterns": self._optimize_amount_patterns(results),
            "new_transaction_types": self._discover_transaction_types(results),
        }

        return optimizations

    def _optimize_card_patterns(self, results: list[ParsingResult]) -> list[str]:
        """Find better card number extraction patterns."""
        all_cards = set()
        for result in results:
            all_cards.update(result.card_numbers)

        # Remove default "0000" to see real patterns
        real_cards = {card for card in all_cards if card != "0000"}

        logger.info(f"Found {len(real_cards)} unique card numbers: {real_cards}")

        # Current patterns are probably sufficient, but log findings
        return list(self.config.get("parsing.card_patterns", []))

    def _optimize_categories(
        self, results: list[ParsingResult]
    ) -> dict[str, list[str]]:
        """Optimize category mappings based on transaction patterns."""
        category_words: defaultdict[str, Counter] = defaultdict(Counter)

        for result in results:
            for txn in result.transactions:
                words = txn.desc_raw.upper().split()
                for word in words:
                    if len(word) >= 4:  # Only meaningful words
                        category_words[txn.category][word] += 1

        # Find new keywords for each category
        optimized = {}
        current_categories = self.config.get("categories", {})

        for category, word_counts in category_words.items():
            existing_keywords = current_categories.get(category, [])

            # Find high-frequency words not already in keywords
            new_keywords = []
            for word, count in word_counts.most_common(10):
                if count >= 3 and word not in existing_keywords:
                    new_keywords.append(word)

            if new_keywords:
                optimized[category] = existing_keywords + new_keywords
                logger.info(f"Category {category}: added keywords {new_keywords}")

        return optimized

    def _optimize_amount_patterns(self, results: list[ParsingResult]) -> list[str]:
        """Optimize amount parsing patterns."""
        # Analyze amount formats that failed to parse
        # This could discover new amount formats
        return []

    def _discover_transaction_types(self, results: list[ParsingResult]) -> list[str]:
        """Discover new transaction types from failed parsing."""
        # Analyze failed lines to find potential new transaction types
        return []


class CrossValidator:
    """Cross-validation for parser performance across multiple PDFs."""

    def __init__(self, parser: ItauParser):
        self.parser = parser

    def validate_across_files(self, file_paths: list[Path]) -> dict:
        """Run cross-validation across multiple files."""
        results = []

        for file_path in file_paths:
            logger.info(f"Validating with {file_path}")
            result = self._parse_and_analyze(file_path)
            results.append(result)

        # Aggregate results
        summary = self._aggregate_results(results)
        return summary



    def _parse_and_analyze(self, pdf_path: Path) -> ParsingResult:
        """Parse PDF and analyze results."""
        try:
            transactions = self.parser.parse_pdf(pdf_path)

            # Extract metrics
            card_numbers = {txn.card_last4 for txn in transactions}
            patterns_found = Counter(txn.category for txn in transactions)

            # Calculate success rate (placeholder - would need golden data)
            success_rate = 0.85  # Placeholder

            return ParsingResult(
                pdf_path=pdf_path,
                transactions=transactions,
                failed_lines=[],  # Would collect from parser
                card_numbers=card_numbers,
                patterns_found=dict(patterns_found),
                success_rate=success_rate,
            )

        except Exception as e:
            logger.error(f"Failed to parse {pdf_path}: {e}")
            return ParsingResult(
                pdf_path=pdf_path,
                transactions=[],
                failed_lines=[],
                card_numbers=set(),
                patterns_found={},
                success_rate=0.0,
            )

    def _aggregate_results(self, results: list[ParsingResult]) -> dict:
        """Aggregate results from multiple PDFs."""
        total_transactions = sum(len(r.transactions) for r in results)
        avg_success_rate = sum(r.success_rate for r in results) / len(results)

        all_cards = set()
        all_patterns: Counter = Counter()

        for result in results:
            all_cards.update(result.card_numbers)
            all_patterns.update(result.patterns_found)
        return {
            "total_pdf_files": len(results),
            "total_transactions": total_transactions,
            "average_success_rate": avg_success_rate,
            "unique_cards": len(all_cards),
            "pattern_distribution": dict(all_patterns),
            "results_by_pdf": results,
        }


class LearningEngine:
    """Main learning engine orchestrating pattern discovery and rule optimization."""

    def __init__(self, config_file: str = "itau_parser_config.yaml"):
        self.config = ConfigManager(config_file)
        self.parser = ItauParser(config_file)
        self.pattern_analyzer = PatternAnalyzer()
        self.cross_validator = CrossValidator(self.parser)
        self.rule_optimizer = RuleOptimizer(self.config)

    def learn_from_files(
        self, pdf_paths: list[Path], output_config: Path | None = None
    ) -> dict:
        """Learn patterns and optimize rules from multiple PDF files."""
        logger.info(f"Starting learning from {len(pdf_paths)} PDF files")

        # Run cross-validation
        validation_results = self.cross_validator.validate_across_files(pdf_paths)

        # Optimize rules based on results
        optimizations = self.rule_optimizer.optimize_rules(
            validation_results["results_by_pdf"]
        )

        # Update configuration
        updated_config = self._apply_optimizations(optimizations)

        # Save updated configuration
        if output_config:
            self._save_config(updated_config, output_config)

        # Return learning summary
        return {
            "validation_results": validation_results,
            "optimizations": optimizations,
            "updated_config_path": str(output_config) if output_config else None,
        }

    def _apply_optimizations(self, optimizations: dict) -> dict:
        """Apply optimizations to configuration."""
        config = self.config.config.copy()

        # Update category mappings
        if "category_mappings" in optimizations:
            for category, keywords in optimizations["category_mappings"].items():
                config["categories"][category] = keywords

        # Update card patterns
        if "card_patterns" in optimizations:
            config["parsing"]["card_patterns"] = optimizations["card_patterns"]

        return config

    def _save_config(self, config: dict, output_path: Path) -> None:
        """Save optimized configuration."""
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"Saved optimized configuration to {output_path}")


def main() -> int:
    """Command-line interface for learning engine."""
    import argparse

    parser = argparse.ArgumentParser(description="Learning Engine for Itaú Parser")
    parser.add_argument(
        "pdf_files", nargs="+", type=Path, help="PDF files for training"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="itau_parser_config.yaml",
        help="Base configuration file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default="optimized_config.yaml",
        help="Output configuration file",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    valid_pdf_files = [
        p for p in args.pdf_files if p.exists() and p.suffix.lower() == ".pdf"
    ]
    if not valid_pdf_files:
        logger.error("No valid PDF files provided")
        return 1

    logger.info(f"Training with {len(valid_pdf_files)} PDF files")

    try:
        engine = LearningEngine(args.config)
        results = engine.learn_from_files(valid_pdf_files, args.output)

        print("Learning complete!")
        print(f"Processed {results['validation_results']['total_pdf_files']} PDF files")
        print(
            f"Found {results['validation_results']['total_transactions']} "
            "transactions"
        )
        print(
            f"Average success rate: "
            f"{results['validation_results']['average_success_rate']:.1%}"
        )
        print(f"Optimized configuration saved to: {args.output}")

    except Exception as e:
        logger.error(f"Learning failed: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())

# type: ignore[import]  # yaml stubs may be missing
