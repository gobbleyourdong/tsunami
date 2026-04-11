#!/usr/bin/env python3
"""
tsunami — the tide rises

Usage:
    python run.py                              # Interactive mode
    python run.py --task "Research X"          # Single task
    python run.py --endpoint http://localhost:8090  # Endpoint override
    python run.py --watcher                    # Enable the Watcher
"""

from tsunami.cli import main

if __name__ == "__main__":
    main()
