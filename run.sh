#!/usr/bin/env bash
# run.sh — one-click launcher for VocaBox
# This script sets up a Python virtual environment, installs dependencies, and runs the Flask app.
# Usage: double-click (on macOS/Linux with execute permissions) or run `bash run.sh`

set -e

# Determine project directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

# Create virtual environment if not exists
if [ ! -d ".venv" ]; then
  echo "[INFO] Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate virtual environment
if [[ "$OSTYPE" == "darwin"* || "$OSTYPE" == "linux"* ]]; then
  source .venv/bin/activate
else
  source .venv/Scripts/activate
fi

# Install dependencies if not already installed
echo "[INFO] Installing dependencies (Flask)..."
pip install --upgrade pip >/dev/null
pip install flask >/dev/null

# Run the app
echo "[INFO] Launching VocaBox..."
python app.py

echo "[INFO] VocaBox stopped."