#!/bin/bash
# Run the Streamlit demo app
set -e
echo "Starting MaiStorage Streamlit Demo..."
echo "Open http://localhost:8501 in your browser"
cd "$(dirname "$0")"
pip install streamlit -q
streamlit run demo_app.py --server.port 8501
