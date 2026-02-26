#!/usr/bin/env python3
"""
Tradegent CLI - Trading Agent Platform

This is the main entry point for the Tradegent platform.
Equivalent to orchestrator.py (legacy name).

Usage:
    python tradegent.py --help
    python tradegent.py analyze NVDA --type stock
    python tradegent.py status
"""

# Import and run the orchestrator CLI
from orchestrator import main

if __name__ == "__main__":
    main()
