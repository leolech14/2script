#!/usr/bin/env python3
"""
AI-Enhanced Itaú Parser System
==============================

Next-generation parser using GPT-4o, ChromaDB, and machine learning
to achieve 99%+ accuracy through intelligent pattern recognition.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import chromadb

# AI/ML imports
import openai
from sentence_transformers import SentenceTransformer

from golden_validator import GoldenValidator

# Core parser imports
from itau_parser_ultimate import ConfigManager, ItauParser, Transaction

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AIEnhancement:
    """AI enhancement results for parser optimization."""
    suggested_categories: dict[str, list[str]]
    confidence_scores: dict[str, float]
    new_patterns: list[str]
    optimization_notes: str

class VectorDatabase:
    """Vector database for semantic pattern matching."""

    def __init__(self, db_path: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="transaction_patterns",
            metadata={"hnsw:space": "cosine"}
        )
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info(f"Vector database initialized at {db_path}")

    def add_patterns(self, patterns: list[str], metadata: list[dict]):
        """Add transaction patterns to vector database."""
        embeddings = self.encoder.encode(patterns)

        self.collection.add(
            embeddings=embeddings.tolist(),
            documents=patterns,
            metadatas=metadata,
            ids=[f"pattern_{i}" for i in range(len(patterns))]
        )
        logger.info(f"Added {len(patterns)} patterns to vector database")

    def find_similar_patterns(self, query: str, n_results: int = 5) -> list[dict]:
        """Find similar transaction patterns using semantic search."""
        query_embedding = self.encoder.encode([query])

        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=n_results
        )

        return [
            {
                "pattern": doc,
                "metadata": meta,
                "distance": dist
            }
            for doc, meta, dist in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0], strict=False
            )
        ]

class GPTIntelligenceEngine:
    """GPT-4o powered intelligence for transaction analysis."""

    def __init__(self, api_key: str | None = None):
        self.client = openai.OpenAI(
            api_key=api_key or os.getenv('OPENAI_API_KEY')
        )
        logger.info("GPT Intelligence Engine initialized")

    async def analyze_failed_transactions(self, failed_lines: list[str]) -> AIEnhancement:
        """Use GPT-4o to analyze failed transaction patterns."""

        prompt = f"""
        Analyze these failed Itaú credit card transaction lines and provide intelligence:

        Failed Lines:
        {chr(10).join(failed_lines[:10])}  # Limit to first 10 for token efficiency

        Please provide:
        1. Suggested merchant categories based on patterns
        2. Confidence scores for each suggestion (0-1)
        3. New regex patterns that could capture these transactions
        4. Optimization notes for the parser

        Return a JSON response with this structure:
        {{
            "suggested_categories": {{"MERCHANT_NAME": ["CATEGORY1", "CATEGORY2"]}},
            "confidence_scores": {{"MERCHANT_NAME": 0.95}},
            "new_patterns": ["regex1", "regex2"],
            "optimization_notes": "Detailed analysis and recommendations"
        }}
        """

        try:
            response = await self.client.chat.completions.acreate(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert in financial transaction parsing and pattern recognition for Brazilian credit card statements."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=2000
            )

            analysis = json.loads(response.choices[0].message.content)

            return AIEnhancement(
                suggested_categories=analysis.get("suggested_categories", {}),
                confidence_scores=analysis.get("confidence_scores", {}),
                new_patterns=analysis.get("new_patterns", []),
                optimization_notes=analysis.get("optimization_notes", "")
            )

        except Exception as e:
            logger.error(f"GPT analysis failed: {e}")
            return AIEnhancement({}, {}, [], f"Analysis failed: {e}")

    async def categorize_transaction(self, description: str, amount: float) -> tuple[str, float]:
        """Use GPT-4o to categorize a single transaction."""

        categories = [
            "FARMÁCIA", "SUPERMERCADO", "RESTAURANTE", "POSTO", "TRANSPORTE",
            "TURISMO", "SAÚDE", "VESTUÁRIO", "EDUCAÇÃO", "SERVIÇOS",
            "PAGAMENTO", "ENCARGOS", "AJUSTE", "FX", "IOF", "DIVERSOS"
        ]

        prompt = f"""
        Categorize this Brazilian credit card transaction:
        
        Description: "{description}"
        Amount: R$ {amount:.2f}
        
        Available categories: {', '.join(categories)}
        
        Return JSON: {{"category": "CHOSEN_CATEGORY", "confidence": 0.95}}
        
        Consider:
        - Brazilian merchant naming conventions
        - Common abbreviations (SUPERMERC, FARMAC, etc.)
        - Transaction amount context
        - Special markers (7117 = PAGAMENTO, IOF keywords = ENCARGOS)
        """

        try:
            response = await self.client.chat.completions.acreate(
                model="gpt-4o-mini",  # Use mini for faster single classifications
                messages=[
                    {"role": "system", "content": "You are an expert in Brazilian financial transaction categorization."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )

            result = json.loads(response.choices[0].message.content)
            return result.get("category", "DIVERSOS"), result.get("confidence", 0.0)

        except Exception as e:
            logger.error(f"GPT categorization failed: {e}")
            return "DIVERSOS", 0.0

class AIEnhancedParser:
    """Main AI-enhanced parser orchestrating all components."""

    def __init__(self, config_file: str = "itau_parser_config.yaml"):
        self.base_parser = ItauParser(config_file)
        self.config = ConfigManager(config_file)
        self.vector_db = VectorDatabase()
        self.gpt_engine = GPTIntelligenceEngine()
        self.validator = GoldenValidator()

        logger.info("AI-Enhanced Parser initialized")

    async def parse_with_ai_enhancement(self, pdf_path: Path, output_path: Path | None = None) -> dict:
        """Parse PDF with AI enhancements for maximum accuracy."""

        logger.info(f"Starting AI-enhanced parsing of {pdf_path}")

        # 1. Initial parsing with base parser
        transactions = self.base_parser.parse_pdf(pdf_path)
        initial_count = len(transactions)

        # 2. Identify failed patterns (mock for now - would need actual failed lines)
        failed_lines = []  # TODO: Collect actual failed lines from parser

        # 3. AI analysis of failures
        if failed_lines:
            ai_enhancement = await self.gpt_engine.analyze_failed_transactions(failed_lines)
            logger.info(f"AI suggested {len(ai_enhancement.suggested_categories)} category improvements")

        # 4. AI-powered re-categorization of low-confidence transactions
        enhanced_transactions = []
        for txn in transactions:
            if self._needs_ai_categorization(txn):
                ai_category, confidence = await self.gpt_engine.categorize_transaction(
                    txn.desc_raw, float(txn.amount_brl)
                )
                if confidence > 0.8:  # High confidence threshold
                    txn.category = ai_category
                    logger.debug(f"AI re-categorized: {txn.desc_raw} → {ai_category} (conf: {confidence:.2f})")

            enhanced_transactions.append(txn)

        # 5. Vector database pattern matching for similar transactions
        for txn in enhanced_transactions:
            similar_patterns = self.vector_db.find_similar_patterns(txn.desc_raw, n_results=3)
            if similar_patterns and similar_patterns[0]['distance'] < 0.3:  # High similarity
                suggested_category = similar_patterns[0]['metadata'].get('category')
                if suggested_category and suggested_category != txn.category:
                    logger.debug(f"Vector DB suggests: {txn.desc_raw} → {suggested_category}")

        # 6. Save enhanced results
        if output_path:
            self.base_parser.csv_writer.write_csv(enhanced_transactions, output_path)

        # 7. Performance metrics
        enhancement_results = {
            "initial_transactions": initial_count,
            "enhanced_transactions": len(enhanced_transactions),
            "ai_recategorizations": sum(1 for t in enhanced_transactions if hasattr(t, '_ai_enhanced')),
            "vector_db_matches": len([t for t in enhanced_transactions if hasattr(t, '_vector_matched')]),
            "processing_time": 0.0  # TODO: Add actual timing
        }

        logger.info(f"AI enhancement complete: {enhancement_results}")
        return enhancement_results

    def _needs_ai_categorization(self, transaction: Transaction) -> bool:
        """Determine if transaction needs AI re-categorization."""
        # Simple heuristics - could be made more sophisticated
        return (
            transaction.category == "DIVERSOS" or
            len(transaction.desc_raw.split()) <= 2 or
            any(char.isdigit() for char in transaction.desc_raw[:5])
        )

    async def validate_against_golden(self, parsed_csv: Path, golden_csv: Path) -> dict:
        """Enhanced validation with AI insights."""

        # Standard validation
        validation_result = self.validator.validate(parsed_csv, golden_csv)

        # AI analysis of mismatches
        if not validation_result.perfect_match:
            mismatch_descriptions = [
                txn.get('desc_raw', '') for txn in validation_result.missing_transactions[:5]
            ]

            if mismatch_descriptions:
                ai_insights = await self.gpt_engine.analyze_failed_transactions(mismatch_descriptions)
                validation_result.ai_insights = ai_insights

        return validation_result

    def add_successful_patterns_to_vector_db(self, transactions: list[Transaction]):
        """Add successful transaction patterns to vector database for future learning."""

        patterns = []
        metadata = []

        for txn in transactions:
            patterns.append(txn.desc_raw)
            metadata.append({
                "category": txn.category,
                "amount_range": self._get_amount_range(float(txn.amount_brl)),
                "card_last4": txn.card_last4,
                "success": True
            })

        self.vector_db.add_patterns(patterns, metadata)
        logger.info(f"Added {len(patterns)} successful patterns to vector database")

    def _get_amount_range(self, amount: float) -> str:
        """Categorize amount into ranges for metadata."""
        if amount < 10:
            return "micro"
        elif amount < 100:
            return "small"
        elif amount < 1000:
            return "medium"
        else:
            return "large"

async def main():
    """Demo the AI-enhanced parser system."""

    # Setup API key
    api_key = input("Enter your OpenAI API key (or set OPENAI_API_KEY env var): ").strip()
    if api_key:
        os.environ['OPENAI_API_KEY'] = api_key

    # Initialize AI parser
    ai_parser = AIEnhancedParser()

    # Test with a sample PDF
    pdf_path = Path("Itau_2025-05.pdf")
    if pdf_path.exists():
        print(f"🚀 Testing AI-enhanced parsing on {pdf_path}")

        # AI-enhanced parsing
        results = await ai_parser.parse_with_ai_enhancement(
            pdf_path,
            output_path=Path("ai_enhanced_output.csv")
        )

        print("📊 AI Enhancement Results:")
        for key, value in results.items():
            print(f"  {key}: {value}")

        # Golden validation if available
        golden_path = Path("golden_2025-05.csv")
        if golden_path.exists():
            print("\n🎯 Validating against golden CSV...")
            validation = await ai_parser.validate_against_golden(
                Path("ai_enhanced_output.csv"),
                golden_path
            )

            print(f"Accuracy: {validation.accuracy_percentage:.1f}%")
            print(f"Coverage: {validation.coverage_percentage:.1f}%")
            print(f"Perfect match: {'YES' if validation.perfect_match else 'NO'}")

    else:
        print(f"❌ PDF file {pdf_path} not found")
        print("Available PDFs:")
        for pdf in Path(".").glob("*.pdf"):
            print(f"  - {pdf}")

if __name__ == "__main__":
    asyncio.run(main())
