"""Vercel serverless function handler for Flask app."""
from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Flask app
from app import app

# Vercel expects a WSGI application
# Flask app is already WSGI compatible
handler = app
