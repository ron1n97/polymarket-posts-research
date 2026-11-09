# Truth Social Posts Strategy

This repo is a small research and execution toolkit for the Polymarket series:

- `donald-trump-of-truth-social-posts-*`

The current validated live workflow focuses on:

- `NO` ideas only
- upper bins only: `80-99`, `100-119`
- one strongest trade per window
- entry during the historically working early window

## One Daily Command

For the current combined daily workflow across Trump and Elon:

```bash
python3 scripts/daily_run.py --bankroll 50
```

or:

```bash
./run_daily.sh 50
```

This prints:

- current Trump signal and suggested size
- current Elon signal and suggested size
- a short `Today` section with the actions to take

## Quick Start

Print the current live operational signal:

```bash
python3 scripts/live_signal.py
```

Short wrapper:

```bash
./run_live_signal.sh
```

Print the current validated live signal and position sizing for a `$50` bankroll:

```bash
python3 scripts/live_signal.py
python3 scripts/position_size.py --bankroll 50
```

Short wrappers:

```bash
./run_live_signal.sh
./run_position_size.sh 50
```

## Current Recommended Workflow

### 1. Get the live signal

```bash
python3 scripts/live_signal.py
```

or:

```bash
./run_live_signal.sh
```

This applies the current preferred defaults:

- auto-fetch live prices from Polymarket
- use the validated `no_upper_only` trade family
- use the validated live entry window
- keep only the strongest remaining trade per market

### 2. Size the position

Example for a `$50` test bankroll:

```bash
python3 scripts/position_size.py --bankroll 50
```

This prints:

- current live signal
- `NO` and `YES` market prices
- model edge
- a few simple sizing plans

### 3. Save a snapshot

```bash
python3 scripts/truth_social_snapshot.py --auto-prices
```

This appends JSONL rows to:

- `data/snapshots/truth_social_snapshots.jsonl`

## Main Scripts

### `scripts/live_signal.py`

One-command operational wrapper.

Use this when you just want the current validated signal.

```bash
python3 scripts/live_signal.py
```

### `scripts/position_size.py`

Position sizing for the current validated signal.

```bash
python3 scripts/position_size.py --bankroll 50
python3 scripts/position_size.py --bankroll 200
```

or:

```bash
./run_position_size.sh 50
./run_position_size.sh 200
```

### `scripts/truth_social_rank.py`

Full ranking engine with manual controls.

Examples:

```bash
python3 scripts/truth_social_rank.py --auto-prices --top 10
python3 scripts/truth_social_rank.py --auto-prices --mode no_upper_only --top 10
python3 scripts/truth_social_rank.py --auto-prices --mode no_upper_only --validated-entry-window --one-per-window --top 10
```

Useful flags:

- `--auto-prices`
- `--mode no_upper_only`
- `--validated-entry-window`
- `--one-per-window`
- `--slug <market-slug>`

### `scripts/truth_social_strategy.py`

Shows live market math:

- current total
- pace
- days remaining
- required posts/day for key bins

```bash
python3 scripts/truth_social_strategy.py
```

### `scripts/truth_social_ev.py`

Shows rough fair probabilities and EV for key bins.

With auto prices:

```bash
python3 scripts/truth_social_ev.py --auto-prices
```

With manual prices:

```bash
python3 scripts/truth_social_ev.py --price-file prices.example.txt
```

### `scripts/truth_social_snapshot.py`

Persists live market state for later analysis.

```bash
python3 scripts/truth_social_snapshot.py --auto-prices
```

or:

```bash
./run_snapshot.sh
```

### `scripts/backtest_truth_social_baseline.py`

Historical backtest using:

- historical XTracker counts
- historical Polymarket prices
- resolved Polymarket outcomes

Current best historical mode:

```bash
python3 scripts/backtest_truth_social_baseline.py \
  --windows 20 \
  --entry-hours 24 \
  --min-edge 0.10 \
  --max-trades-per-window 1 \
  --mode no_upper_only
```

### `scripts/backtest_truth_social_sensitivity.py`

Parameter sensitivity grid for the backtest.

Example:

```bash
python3 scripts/backtest_truth_social_sensitivity.py \
  --windows 20 \
  --mode no_upper_only \
  --max-trades-per-window 1 \
  --entry-hours-grid 24,36 \
  --min-edge-grid 0.05,0.10,0.15
```

### `scripts/prepare_prices.py`

Converts manual price snapshots into the format used by the EV and ranking scripts.

Examples:

```bash
python3 scripts/prepare_prices.py prices.snapshot.example.txt -o prices.txt
python3 scripts/prepare_prices.py prices.copy_paste.example.txt -o prices.txt
```

## Files

- `STRATEGY.md`: strategy notes and workflow
- `DAILY_TEMPLATE.md`: daily worksheet template
- `prices.example.txt`: manual prices in normalized format
- `prices.snapshot.example.txt`: simple manual snapshot format
- `prices.copy_paste.example.txt`: more flexible copy-paste format

## Current Practical Defaults

As of the current research in this repo, the best validated live defaults are:

- trade family: `no_upper_only`
- timing: early window, around `24h` after start
- one trade per market
- for very small bankrolls, use fixed small share counts rather than fancy sizing

For a `$50` test bankroll, the current simple usage is:

```bash
python3 scripts/live_signal.py
python3 scripts/position_size.py --bankroll 50
```
