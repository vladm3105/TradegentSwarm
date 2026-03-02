#!/bin/bash
# Run Streamlit dashboard with clean OpenSSL (fixes conda conflict)
cd "$(dirname "$0")/.."
LD_LIBRARY_PATH= streamlit run dashboard/app.py "$@"
