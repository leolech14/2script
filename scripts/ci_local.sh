#!/bin/bash
# Local CI script - runs same checks as GitHub Actions

set -e

echo "🧹 Running Ruff linter..."
ruff check . --fix

echo "🎨 Running Black formatter..."
black --check .

echo "🔍 Running MyPy type checker..."
mypy --install-types --non-interactive .

echo "🧪 Running pytest with coverage..."
pytest --cov=. --cov-report=term-missing

echo "📊 Validating golden CSVs..."
if [ -f "golden_validator.py" ]; then
    python golden_validator.py
fi

echo "✅ All local CI checks passed!"
