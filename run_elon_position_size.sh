#!/bin/sh

BANKROLL="${1:-50}"
python3 scripts/elon_position_size.py --bankroll "$BANKROLL"
