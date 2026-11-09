#!/bin/sh

BANKROLL="${1:-50}"
python3 scripts/daily_run.py --bankroll "$BANKROLL"
