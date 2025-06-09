#!/usr/bin/env python3
"""
AI Environment Setup for Itaú Parser
====================================

Sets up the complete AI enhancement environment including:
- OpenAI API configuration
- ChromaDB vector database
- Learning pipelines
- Performance monitoring
"""

import json
import os
from pathlib import Path

import yaml


def setup_openai_api():
    """Setup OpenAI API configuration."""
    print("🔑 Setting up OpenAI API...")

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        api_key = input("Enter your OpenAI API key: ").strip()
        if api_key:
            # Save to .env file
            with open('.env', 'a') as f:
                f.write(f"\nOPENAI_API_KEY={api_key}\n")
            print("✅ API key saved to .env file")
        else:
            print("❌ No API key provided. AI features will be limited.")
            return False

    # Test API connection
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        # Simple test call
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Test connection"}],
            max_tokens=5
        )
        print("✅ OpenAI API connection successful")
        return True

    except Exception as e:
        print(f"❌ OpenAI API test failed: {e}")
        return False

def setup_vector_database():
    """Initialize ChromaDB vector database."""
    print("\n📊 Setting up Vector Database...")

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        # Create database directory
        db_path = Path("./chroma_db")
        db_path.mkdir(exist_ok=True)

        # Initialize ChromaDB
        client = chromadb.PersistentClient(path=str(db_path))
        collection = client.get_or_create_collection(
            name="transaction_patterns",
            metadata={"hnsw:space": "cosine"}
        )

        # Test sentence transformer
        encoder = SentenceTransformer('all-MiniLM-L6-v2')
        test_embedding = encoder.encode(["Test transaction"])

        print(f"✅ Vector database initialized at {db_path}")
        print(f"   Collection: {collection.name}")
        print("   Encoder model: all-MiniLM-L6-v2")
        return True

    except Exception as e:
        print(f"❌ Vector database setup failed: {e}")
        return False

def setup_experiment_tracking():
    """Setup MLflow for experiment tracking."""
    print("\n📈 Setting up Experiment Tracking...")

    try:
        import mlflow

        # Create MLflow tracking directory
        tracking_dir = Path("./mlruns")
        tracking_dir.mkdir(exist_ok=True)

        # Set tracking URI
        mlflow.set_tracking_uri(f"file://{tracking_dir.absolute()}")

        # Create experiment
        experiment_name = "itau_parser_ai_enhancement"
        try:
            experiment_id = mlflow.create_experiment(experiment_name)
        except:
            experiment_id = mlflow.get_experiment_by_name(experiment_name).experiment_id

        mlflow.set_experiment(experiment_name)

        print("✅ MLflow tracking initialized")
        print(f"   Tracking URI: file://{tracking_dir.absolute()}")
        print(f"   Experiment: {experiment_name}")
        return True

    except Exception as e:
        print(f"❌ Experiment tracking setup failed: {e}")
        return False

def create_ai_config():
    """Create AI-enhanced configuration file."""
    print("\n⚙️  Creating AI Configuration...")

    ai_config = {
        "ai_enhancement": {
            "enabled": True,
            "model_configs": {
                "primary_model": "gpt-4o",
                "fallback_model": "gpt-4o-mini",
                "embedding_model": "all-MiniLM-L6-v2"
            },
            "thresholds": {
                "confidence_threshold": 0.8,
                "similarity_threshold": 0.3,
                "recategorization_threshold": 0.7
            },
            "vector_db": {
                "path": "./chroma_db",
                "collection_name": "transaction_patterns",
                "max_results": 5
            },
            "learning": {
                "auto_learn": True,
                "pattern_discovery": True,
                "cross_validation": True,
                "min_pattern_frequency": 3
            }
        },
        "monitoring": {
            "mlflow_tracking": True,
            "performance_metrics": [
                "accuracy", "coverage", "processing_time",
                "ai_enhancements", "vector_matches"
            ],
            "alerts": {
                "accuracy_drop_threshold": 0.05,
                "processing_time_threshold": 300
            }
        }
    }

    # Save AI config
    with open('ai_config.yaml', 'w') as f:
        yaml.dump(ai_config, f, default_flow_style=False, allow_unicode=True)

    print("✅ AI configuration saved to ai_config.yaml")
    return True

def setup_jupyter_environment():
    """Setup Jupyter for interactive development."""
    print("\n📓 Setting up Jupyter Environment...")

    try:
        # Create Jupyter config directory
        jupyter_dir = Path("./notebooks")
        jupyter_dir.mkdir(exist_ok=True)

        # Create starter notebook
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "# AI-Enhanced Itaú Parser Analysis\n",
                        "\n",
                        "This notebook provides interactive analysis of the AI-enhanced parser system."
                    ]
                },
                {
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "source": [
                        "import sys\n",
                        "sys.path.append('..')\n",
                        "\n",
                        "from ai_enhanced_parser import AIEnhancedParser\n",
                        "import pandas as pd\n",
                        "import matplotlib.pyplot as plt\n",
                        "\n",
                        "# Initialize AI parser\n",
                        "ai_parser = AIEnhancedParser()\n",
                        "print('AI Parser ready for analysis!')"
                    ]
                }
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }

        # Save notebook
        notebook_path = jupyter_dir / "ai_parser_analysis.ipynb"
        with open(notebook_path, 'w') as f:
            json.dump(notebook_content, f, indent=2)

        print(f"✅ Jupyter notebook created: {notebook_path}")
        print("   Run: jupyter lab notebooks/ai_parser_analysis.ipynb")
        return True

    except Exception as e:
        print(f"❌ Jupyter setup failed: {e}")
        return False

def validate_environment():
    """Validate that all components are working."""
    print("\n🔍 Validating Environment...")

    checks = []

    # Check imports
    try:
        import openai
        checks.append("✅ OpenAI")
    except ImportError:
        checks.append("❌ OpenAI")

    try:
        import chromadb
        checks.append("✅ ChromaDB")
    except ImportError:
        checks.append("❌ ChromaDB")

    try:
        import sentence_transformers
        checks.append("✅ Sentence Transformers")
    except ImportError:
        checks.append("❌ Sentence Transformers")

    try:
        import mlflow
        checks.append("✅ MLflow")
    except ImportError:
        checks.append("❌ MLflow")

    try:
        import pandas as pd
        checks.append("✅ Pandas")
    except ImportError:
        checks.append("❌ Pandas")

    # Check files
    if Path("ai_enhanced_parser.py").exists():
        checks.append("✅ AI Enhanced Parser")
    else:
        checks.append("❌ AI Enhanced Parser")

    if Path("ai_config.yaml").exists():
        checks.append("✅ AI Configuration")
    else:
        checks.append("❌ AI Configuration")

    print("\nEnvironment Status:")
    for check in checks:
        print(f"  {check}")

    success_count = sum(1 for check in checks if check.startswith("✅"))
    total_checks = len(checks)

    print(f"\n📊 Environment Score: {success_count}/{total_checks} ({success_count/total_checks*100:.1f}%)")

    if success_count == total_checks:
        print("🎉 Environment setup complete! Ready for AI-enhanced parsing.")
    else:
        print("⚠️  Some components need attention. Check the failed items above.")

    return success_count == total_checks

def main():
    """Main setup routine."""
    print("🚀 AI-Enhanced Itaú Parser Environment Setup")
    print("=" * 50)

    success = True

    # Setup components
    success &= setup_openai_api()
    success &= setup_vector_database()
    success &= setup_experiment_tracking()
    success &= create_ai_config()
    success &= setup_jupyter_environment()

    # Final validation
    print("\n" + "=" * 50)
    validate_environment()

    if success:
        print("\n🎯 Next Steps:")
        print("1. Run: python ai_enhanced_parser.py")
        print("2. Or: jupyter lab notebooks/ai_parser_analysis.ipynb")
        print("3. Test with: python -c 'from ai_enhanced_parser import AIEnhancedParser; print(\"AI Parser ready!\")'")

    return success

if __name__ == "__main__":
    main()
