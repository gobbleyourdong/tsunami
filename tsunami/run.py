#!/usr/bin/env python3
"""
TSUNAMI — Autonomous Execution Agent

Usage:
    python run.py                              # Interactive mode
    python run.py --task "Research X"          # Single task
    python run.py --model ollama:qwen2.5:72b  # Model override
    python run.py --model api:gpt-4o --endpoint https://api.openai.com --api-key sk-xxx
    python run.py --watcher                    # Enable the Watcher
"""

from tsunami.cli import main

if __name__ == "__main__":
    main()
