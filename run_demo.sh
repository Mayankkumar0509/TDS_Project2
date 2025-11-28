#!/bin/bash
set -e

echo "🚀 Starting LLM Quiz Solver Demo"

# Load env
if [ ! -f .env ]; then
    echo "❌ .env not found. Creating from .env.example..."
    cp .env.example .env
    echo "⚠️  Edit .env to set QUIZ_SECRET, then run again."
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python version: $python_version"

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt
playwright install chromium 2>/dev/null || true

# Run tests
echo "🧪 Running tests..."
pytest tests/test_demo.py -v --tb=short

# Optional: start server
read -p "Start server on http://localhost:8000? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting server (Ctrl+C to stop)..."
    python main.py
fi