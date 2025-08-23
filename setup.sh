#!/bin/bash

# Audio Processor Setup Script
# This script sets up a virtual environment and installs all dependencies

set -e  # Exit on any error

echo "🎵 Audio Processor Setup Script"
echo "================================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

python3 -m venv venv
echo "✅ Virtual environment created"

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing requirements..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Requirements installed successfully"
else
    echo "❌ Error: requirements.txt not found"
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data
mkdir -p logs
echo "✅ Directories created"

# Check if .env file exists
echo "🔧 Checking configuration..."
if [ ! -f "config/.env" ]; then
    echo "⚠️  Environment file not found. Creating template..."
    cat > config/.env << 'EOF'
# API Keys
DEEPGRAM_API_KEY=your_deepgram_key_here
OPENAI_API_KEY=your_openai_key_here

# Folder Paths (customize for your system)
WATCH_FOLDER=/Users/yourusername/OneDrive/AudioProcessor/input
PROCESSED_FOLDER=/Users/yourusername/OneDrive/AudioProcessor/processed
ERROR_FOLDER=/Users/yourusername/OneDrive/AudioProcessor/error
OUTPUT_FOLDER=/Users/yourusername/OneDrive/AudioProcessor/output

# Database
DATABASE_URL=sqlite:///data/audio_processor.db
EOF
    echo "📝 Template .env file created at config/.env"
    echo "⚠️  Please edit config/.env with your actual API keys and folder paths"
else
    echo "✅ Environment file exists"
fi

# Create example folder structure
echo "📂 Creating example folder structure..."
EXAMPLE_BASE="$HOME/AudioProcessor"
mkdir -p "$EXAMPLE_BASE"/{input,processed,error,output}
echo "✅ Example folders created at: $EXAMPLE_BASE"

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit config/.env with your API keys and folder paths"
echo "2. Activate the virtual environment: source venv/bin/activate"
echo "3. Run the application: python main.py"
echo ""
echo "Example folder structure created at: $EXAMPLE_BASE"
echo "Web dashboard will be available at: http://127.0.0.1:8000"
echo ""
echo "For more information, see README.md"
