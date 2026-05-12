#!/bin/bash
# Hotmail Live Check - Quick start
cd "$(dirname "$0")"

# Install deps
pip install -r requirements.txt -q
playwright install chromium 2>/dev/null

# Run
echo "🔥 Hotmail Live Check starting..."
echo "Open: http://localhost:5000"
python app.py
