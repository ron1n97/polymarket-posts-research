# Donald Trump Truth Social Posts Strategy

## Goal

Build a repeatable trading framework for the Polymarket series:

- `donald-trump-of-truth-social-posts-*`

This strategy is designed for overlapping 7-day windows where a new market opens every few days. The objective is not to predict an exact post count from scratch, but to trade persistent pricing errors caused by:

- overreaction to recent posting spikes
- underreaction to overlap arithmetic between adjacent windows
- repeated overpricing of upper bins

## Core Idea

These markets are not independent weekly totals. They are overlapping windows.

For adjacent windows:

- `Window_t = old_shared_block + future_tail`
- `Window_t+1 = partial_new_block + future_shared_tail + new_tail`

Because of this, the best trades usually come from:

1. translating each bin into a required posts-per-day rate on the remaining time
2. comparing that required rate against observed posting regimes
3. comparing two adjacent windows against each other

The strategy is regime-based and relative-value based, not pure directional guessing.

## Daily Workflow

For each active market, record:

- `current_total`
- `days_remaining`
- `current_pace`
- `posts_last_24h`
- `posts_last_72h_avg`
- current prices for key bins

Recommended key bins:

- `60-79`
- `80-99`
- `100-119`

Then answer:

1. What rate does each bin require from here?
2. What posting regime is currently being observed?
3. Is the market pricing that regime fairly?

## Formulas

For a bin `[L, H]`:

- `need_low = max(L - current_total, 0)`
- `need_high = max(H - current_total, 0)`
- `req_low = need_low / days_remaining`
- `req_high = need_high / days_remaining`

Interpretation:

- if a bin only needs `quiet` or `base` posting to win, it is still very live
- if a bin needs `active` posting, price discipline matters
- if a bin needs `spike` posting, the default posture should be skeptical unless a catalyst exists

## Posting Regimes

Use simple regime buckets:

- `quiet`: `7-10` posts/day
- `base`: `10-13` posts/day
- `active`: `13-16` posts/day
- `spike`: `16+` posts/day

These buckets are intentionally simple. Their purpose is to map market prices to realistic requirements instead of pretending to estimate a precise total.

## Entry Rules

Buy `Yes` when:

- the bin requires no more than `base` posting on the remaining time
- the market prices it materially below your rough fair value
- there is no evidence that the regime has shifted upward

Buy `No` when:

- the bin requires `active` or `spike` posting on the remaining time
- the market still treats it as a central scenario
- the recent strength comes from one spike day rather than a sustained multi-day run

Best entry timing:

- `12-36` hours after a new window opens
- `48-72` hours before expiry when arithmetic becomes restrictive

## Exit Rules

Exit or reduce when:

- the market reprices and most of the edge is gone
- the required regime no longer looks unrealistic
- a real catalyst appears and changes the posting regime

Invalidate the thesis when:

- two consecutive days print above the assumed regime
- pace moves into a meaningfully higher regime

## Best Trade Types

### 1. Underpriced Middle Bin

The most common setup in this series.

Examples:

- market overpays for `100-119`
- middle bin such as `60-79` or `80-99` only needs `base` posting

### 2. Sell Overheated Top Bin

After a single strong posting day, upper bins often get overpriced.

Question to ask:

- does this upper bin still need several more days of `16+` posting to win?

If yes, default bias is `No`.

### 3. Adjacent Window Spread

Trade differences between overlapping windows instead of just absolute totals.

Typical setup:

- older window already has a large locked-in base
- newer window opened weakly
- market prices them too similarly

### 4. Late Arithmetic Fade

Near expiry, the math often becomes clearer than the market.

Typical setup:

- favorite bin still has a strong price
- but now requires an unrealistic finish rate

## Risk Management

- treat multiple positions driven by the same posting-regime thesis as one risk bucket
- avoid holding more than `2-3` strongly correlated positions at once
- size bigger only when arithmetic, regime, and overlap all point in the same direction
- reduce if price moves in your favor faster than the underlying data changes

Suggested sizing by conviction:

- `high`: arithmetic + regime + overlap align
- `medium`: arithmetic + price align
- `low`: only relative-value is present

## Operational Checklist

Use this every day:

1. Update all active windows from XTracker.
2. Recompute `req_low` and `req_high` for key bins.
3. Label each bin by required regime.
4. Compare those required regimes against the last `24h` and `72h`.
5. Rank the top `1-2` mispricings only.
6. Avoid adding multiple positions that are just the same thesis in disguise.

## Current Example: 2026-04-04

Observed windows:

- `March 31 - April 7, 2026`
- `April 3 - April 10, 2026`
- `April 7 - April 14, 2026`

At the time of analysis:

- `March 31 - April 7` had about `43` posts
- `April 3 - April 10` had about `9` posts

Illustrative conclusions from the framework:

- `April 3 - April 10: 60-79` looked attractive because it only required a moderate remaining rate
- `April 3 - April 10: 100-119` looked expensive because it required a sustained high remaining rate
- `March 31 - April 7` looked more like a `60-79` vs `80-99` battle than a true `100-119` market

This example should be treated as a demonstration of the framework, not as a permanent signal.

## Data Sources

Primary:

- Polymarket market pages
- XTracker live counters

Resolution notes:

- these markets use XTracker-style counting logic
- reposts and quote-style activity matter
- temporary spikes can distort prices faster than they change fair value

## Next Step

Turn this document into a repeatable process:

- add a daily worksheet
- add scripts to fetch active windows and compute required rates
- add a small model that maps regimes to rough fair probabilities

## Repo Workflow

Current repo tools:

- `python3 scripts/truth_social_strategy.py`
  Prints active windows, current totals, days remaining, and required rates for key bins.
- `python3 scripts/truth_social_ev.py --price-file prices.example.txt`
  Computes rough fair probabilities and EV using live XTracker data plus manual prices.
- `python3 scripts/truth_social_rank.py --price-file prices.example.txt --top 10`
  Ranks the best positive-edge trades from the provided prices.
- `python3 scripts/truth_social_rank.py --auto-prices --top 10`
  Fetches current key-bin prices directly from Polymarket Gamma API and ranks the best positive-edge trades automatically.
- `python3 scripts/truth_social_rank.py --auto-prices --mode no_upper_only --top 10`
  Applies the current historically-validated live filter: only one-sided `NO` ideas on upper bins.
- `python3 scripts/truth_social_rank.py --auto-prices --mode no_upper_only --validated-entry-window --top 10`
  Applies both the historically-validated trade family and the validated timing window for live entry.
- `python3 scripts/truth_social_rank.py --auto-prices --mode no_upper_only --validated-entry-window --one-per-window --top 10`
  Applies the validated trade family, validated timing window, and keeps only the strongest trade per market.
- `python3 scripts/live_signal.py`
  Runs the current validated operational live signal with all preferred defaults.
- `python3 scripts/truth_social_snapshot.py --auto-prices`
  Stores a JSONL snapshot of current totals, fair values, market prices, and edges for later analysis.
- `python3 scripts/prepare_prices.py prices.snapshot.example.txt -o prices.txt`
  Converts a simple pasted snapshot file into the `slug:low-high:yes_price` format used by the EV and ranking scripts.
- `python3 scripts/prepare_prices.py prices.copy_paste.example.txt -o prices.txt`
  Converts more flexible copy-paste lines that include URLs, `%`, `Yes`, or mixed separators.

Recommended daily flow:

1. Preferred: run `python3 scripts/live_signal.py`.
2. If needed, override with manual prices from a snapshot file.
3. Sanity-check the top trades with `truth_social_strategy.py`.
4. Persist the state with `truth_social_snapshot.py --auto-prices`.

Snapshot storage:

- `data/snapshots/truth_social_snapshots.jsonl`
