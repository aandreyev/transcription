#!/bin/bash

set -e

echo "Installing Transcription app on macOS..."

# Ensure Homebrew
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install Python 3.12
if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Installing python@3.12 via Homebrew..."
  brew install python@3.12
fi

APP_DIR="$HOME/Applications/Transcription"
REPO_URL="https://github.com/aandreyev/transcription.git"

mkdir -p "$HOME/Applications"
if [ -d "$APP_DIR/.git" ]; then
  echo "Updating existing repo in $APP_DIR..."
  git -C "$APP_DIR" pull --rebase
else
  echo "Cloning repo to $APP_DIR..."
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

echo "Running setup..."
chmod +x setup.sh run.sh || true
./setup.sh

echo "Creating Start Transcription.command in $APP_DIR..."
cat > "$APP_DIR/Start Transcription.command" << 'EOS'
#!/bin/bash
cd "$(cd "$(dirname "$0")" && pwd)"
./run.sh
EOS
chmod +x "$APP_DIR/Start Transcription.command"

echo "Done. Launch with: $APP_DIR/Start Transcription.command"
echo "Or open Admin: http://127.0.0.1:8005/admin"

