#!/bin/bash
# Build script for Vercel to reduce package sizes

# Install packages without binary wheels where possible to reduce size
pip install --no-cache-dir Flask==3.0.0 Werkzeug==3.0.1 Flask-Login==0.6.3
pip install --no-cache-dir python-dotenv==1.2.1
pip install --no-cache-dir supabase==2.27.1
pip install --no-cache-dir reportlab==4.0.7

# Install pandas and yfinance - these are the heavy ones
# Try installing with minimal dependencies
pip install --no-cache-dir pandas==2.0.3
pip install --no-cache-dir yfinance==0.2.48

# Clean up cache and unnecessary files
find /vercel/.local -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /vercel/.local -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find /vercel/.local -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
find /vercel/.local -type f -name "*.pyc" -delete 2>/dev/null || true
find /vercel/.local -type f -name "*.pyo" -delete 2>/dev/null || true
