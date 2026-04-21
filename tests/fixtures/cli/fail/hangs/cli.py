#!/usr/bin/env python3
"""CLI that hangs before argparse — import-time sleep blocks --help.

Models the failure mode where a dev does heavy initialization at
module level (DB connection, API handshake, model load) that runs
before argparse gets the chance to short-circuit on --help. Probe's
timeout catches the hang.
"""
import time
import sys

# Unconditional long sleep simulates slow/blocking init
time.sleep(60)

import argparse
parser = argparse.ArgumentParser(prog="hangs")
parser.parse_args()
print("never reached")
