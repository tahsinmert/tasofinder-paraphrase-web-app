"""Vercel serverless function handler for Flask app."""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

# Set working directory to parent
os.chdir(str(parent_dir))

# Import Flask app
try:
    from app import app
except ImportError as e:
    # Print detailed error for debugging
    import traceback
    print(f"Import error: {e}")
    print(f"Python path: {sys.path}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Files in parent: {list(parent_dir.iterdir())}")
    traceback.print_exc()
    raise

# Vercel expects handler to be the WSGI application
# Flask app is already WSGI compatible
handler = app
