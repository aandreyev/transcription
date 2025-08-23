#!/bin/bash

# Audio Processor Run Script
# This script activates the virtual environment and runs the application

set -e  # Exit on any error

echo "🎵 Starting Audio Processor..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import yaml" 2>/dev/null; then
    echo "❌ Dependencies not installed. Installing now..."
    pip install -r requirements.txt
fi

# Run the application
echo "🚀 Starting Audio Processor..."
echo "💡 Available options:"
echo "   --port XXXX        Use specific port"
echo "   --host 0.0.0.0     Allow external connections"
echo "   --no-auto-port     Don't auto-find available port"
echo ""
python main.py "$@"
