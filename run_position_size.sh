#!/bin/sh

BANKROLL="${1:-50}"
python3 scripts/position_size.py --bankroll "$BANKROLL"
