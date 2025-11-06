#!/bin/bash
# Quick Start Script for Cerebellar SDC Extraction System
# Run this script to start the complete system

echo "🧠 Cerebellar SDC Extraction System - Quick Start"
echo "=" | awk '{printf "%s%60s\n", $0, ""}'
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION found"

# Check if in virtual environment
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Not in virtual environment"
    echo "   Recommended: python3 -m venv venv && source venv/bin/activate"
    echo ""
fi

# Check if dependencies are installed
echo "📦 Checking dependencies..."
if ! python3 -c "import flask" &> /dev/null; then
    echo "❌ Dependencies not installed"
    echo "Installing dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo "⚠️  ANTHROPIC_API_KEY not set"
    echo ""
    echo "Please set your API key:"
    echo "  export ANTHROPIC_API_KEY='your-key-here'"
    echo ""
    echo "Or create a .env file:"
    echo "  echo 'ANTHROPIC_API_KEY=your-key-here' > .env"
    echo ""
    read -p "Continue anyway? (Mock data only) [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ API key found"
fi

echo ""
echo "🚀 Starting system..."
echo ""

# Function to open browser after delay
open_browser() {
    sleep 3
    echo "🌐 Opening browser..."
    
    if command -v open &> /dev/null; then
        open "file://$(pwd)/cerebellar_extraction_pro.html"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "file://$(pwd)/cerebellar_extraction_pro.html"
    elif command -v start &> /dev/null; then
        start "file://$(pwd)/cerebellar_extraction_pro.html"
    else
        echo "ℹ️  Please open cerebellar_extraction_pro.html manually"
    fi
}

# Start browser opener in background
open_browser &

# Start API server
echo "📡 Starting API server on http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=" | awk '{printf "%s%60s\n", $0, ""}'
echo ""

python3 api_server.py

# Cleanup on exit
trap "echo ''; echo '👋 Shutting down...'; exit" INT TERM
