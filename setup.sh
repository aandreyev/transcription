#!/bin/bash

# Audio Processor Setup Script
# This script sets up a virtual environment and installs all dependencies

set -e  # Exit on any error

echo "🎵 Audio Processor Setup Script"
echo "================================"

# Resolve a Python 3.12 interpreter
PYTHON_BIN=""

if command -v python3.12 &> /dev/null; then
    PYTHON_BIN="python3.12"
elif command -v python3 &> /dev/null; then
    PY3_VER=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [ "$PY3_VER" = "3.12" ]; then
        PYTHON_BIN="python3"
    fi
fi

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Error: Python 3.12 is required for this project, but was not found."
    echo ""
    echo "Install options:"
    echo "- Homebrew (Apple Silicon): brew install python@3.12 && export PATH=\"/opt/homebrew/opt/python@3.12/bin:$PATH\""
    echo "- Homebrew (Intel):        brew install python@3.12 && export PATH=\"/usr/local/opt/python@3.12/bin:$PATH\""
    echo "- pyenv:                   brew install pyenv && pyenv install 3.12.5 && pyenv local 3.12.5"
    echo ""
    echo "After installing, re-run: ./setup.sh"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_BIN -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
echo "✅ Using $PYTHON_BIN ($PYTHON_VERSION)"

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

$PYTHON_BIN -m venv venv
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
