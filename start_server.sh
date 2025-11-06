#!/bin/bash
# Start the Cerebellar Extraction API Server

echo "🚀 Starting Cerebellar Extraction API Server..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY not set!"
    echo "   Run: export ANTHROPIC_API_KEY='your-key-here'"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if required packages are installed
if ! python3 -c "import flask, anthropic" 2>/dev/null; then
    echo "❌ Required packages not installed!"
    echo "   Run: pip install -r requirements.txt"
    exit 1
fi

echo "✅ Virtual environment: Active"
echo "✅ API Key: Set"
echo "✅ Dependencies: Installed"
echo ""
echo "📍 Server will run on: http://localhost:5000"
echo ""
echo "📋 Available endpoints:"
echo "   GET  /api/health        - Health check"
echo "   POST /api/upload        - Upload PDF"
echo "   POST /api/extract/field - Extract single field with citations"
echo "   POST /api/extract/all   - Extract all fields"
echo ""
echo "🎯 To stop the server: Press Ctrl+C"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# Start the server
python3 api_server.py
