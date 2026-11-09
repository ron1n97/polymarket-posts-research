# Experiment log

## Kept (Trump)

| Idea | Result | Notes |
|---|---|---|
| Required-rate / regime map on overlapping windows | Framework kept | Core thesis |
| `no_upper_only` + ~24h entry + edge≥10% + 1/window | 2 / 20 windows trade; both wins | Selected live defaults — tiny N |
| Live CLI (`live_signal`, sizing, snapshot) | Operational | Strongest non-statistical asset |

## Dropped / demoted

| Idea | Result | Notes |
|---|---|---|
| `mode=all` (YES+NO by max edge) | 18 trades, 11% WR | Total PnL skewed by one ~0.5¢ YES lottery |
| Middle-bin YES as default live family | Not promoted | Needs more evidence |
| Elon weekly as “validated” | Demoted to exploratory | 7 windows, 2 trades under same filter |

## Sensitivity (Trump `no_upper_only`)

Across entry_hours ∈ {12,24,36,48} × min_edge ∈ {0.05,0.10,0.15}: trade counts stay in **1–5**. Perfect WR appears often — treat as **underpowered**, not robust.

## Next experiments (not done)

1. Expand beyond 20 closed Trump windows; report bootstrap CIs  
2. Proper fee / spread / partial-fill assumptions on CLOB entry  
3. Adjacent-window relative-value as a separate backtest family  
4. Grow Elon weekly sample before sharing live defaults
