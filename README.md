# Polymarket Posts Research

[![Research Note PDF](https://img.shields.io/badge/Research%20Note-PDF-red?style=for-the-badge&logo=adobeacrobatreader&logoColor=white)](docs/pdf/research_note.pdf)
[![Markdown](https://img.shields.io/badge/Research%20Note-Markdown-blue?style=for-the-badge)](docs/research_note.md)

Research toolkit for Polymarket **overlapping weekly post-count** markets:

- Trump Truth Social: `donald-trump-of-truth-social-posts-*`
- Elon weekly tweets: exploratory only

This is a **curated public extract**. Empirically it is the **weakest** of the Polymarket portfolio repos — on purpose we do **not** dress tiny-N results as alpha.

**Bottom line:** preferred live family is sparse **`NO` on upper bins** (~24h after open). On **20** Trump windows that filter fires **twice** (both wins, **+0.385**/share). Broad YES hunting looks “profitable” only via lottery skew. Elon is exploratory.

Start here: **[open the PDF](docs/pdf/research_note.pdf)** · [Markdown note](docs/research_note.md) · [experiment log](docs/experiment_log.md)

---

## Why this repo exists

Shows:

1. Microstructure thinking on overlapping windows  
2. Regime / required-rate translation instead of exact-count forecasting  
3. Filter ablation (and how unfiltered YES lies)  
4. Honest sample-size limits next to a usable daily CLI  

---

## Selected defaults (Trump)

| Knob | Value |
|---|---|
| Family | `no_upper_only` |
| Bins | `80-99`, `100-119` |
| Timing | ~24h after window start |
| Edge | ≥ 10% model edge |
| Cap | 1 trade per window |

```bash
python scripts/live_signal.py
python scripts/position_size.py --bankroll 50
# or combined:
python scripts/daily_run.py --bankroll 50
```

Elon: `python scripts/elon_live_signal.py` — **exploratory**, see [`ELON_WEEKLY.md`](ELON_WEEKLY.md).

---

## Repository layout

```
docs/
  research_note.md / pdf/     # start here
  experiment_log.md
results/                      # sanitized backtest tables
figures/
scripts/                      # live + backtest + ranking
STRATEGY.md                   # full Trump thesis
ELON_WEEKLY.md                # Elon status
DAILY_TEMPLATE.md             # worksheet
```

`data/` snapshots are gitignored.

---

## Backtest (network)

```bash
pip install -r requirements.txt
python scripts/backtest_truth_social_baseline.py \
  --windows 20 --entry-hours 24 --min-edge 0.10 \
  --max-trades-per-window 1 --mode no_upper_only

python scripts/make_figures.py
```

---

## Related public work

- [polymarket-btc-5m-research](https://github.com/ron1n97/polymarket-btc-5m-research)  
- [polymarket-weather-research](https://github.com/ron1n97/polymarket-weather-research)  
- [f1-pitstop-prediction](https://github.com/ron1n97/f1-pitstop-prediction)
