#!/usr/bin/env python3
"""CLI that's broken — crashes on import (NameError) regardless of args."""
import sys

print(f"running with args: {sys.argv[1:]}")
raise RuntimeError("intentional crash — probe should catch non-zero exit")
