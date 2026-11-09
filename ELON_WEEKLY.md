# Elon Weekly Markets

This file tracks the exploratory weekly Polymarket series for Elon Musk tweets:

- series slug: `elon-tweets`
- tracked handle: `elonmusk`
- tracker source: `xtracker.polymarket.com`

## Scope

This repo support is currently exploratory only.

It is not yet historically validated like the Trump weekly workflow.

The current script:

- filters for weekly Elon markets only
- ignores short 2-day Elon windows
- ignores the monthly May 2026 market
- builds rough fair values from current posting pace, last 24h, and last 72h

## Run

```bash
python3 scripts/elon_weekly_signal.py
```

or:

```bash
./run_elon_weekly_signal.sh
```

Exploratory live wrapper with the current best weekly defaults:

```bash
python3 scripts/elon_live_signal.py
```

or:

```bash
./run_elon_live_signal.sh
```

Exploratory sizing for the current weekly Elon signal:

```bash
python3 scripts/elon_position_size.py --bankroll 50
```

or:

```bash
./run_elon_position_size.sh 50
```

## Current Status

The script is useful for:

- identifying active weekly Elon windows
- seeing current totals and pace
- comparing rough fair values vs current market prices

It should not yet be treated as a validated strategy.

Current exploratory live defaults:

- trade family: `NO` upper weekly bins only
- upper cutoff: `300+`
- timing: roughly `24h-36h` after market start
- one strongest trade per market

## Next Step

To bring Elon to the same level as Trump:

1. collect a longer historical sample for weekly Elon windows
2. backtest with historical Polymarket prices
3. determine whether any stable trade family exists
4. only then promote a validated `live_signal` mode
