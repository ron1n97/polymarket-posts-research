#!/usr/bin/env python3

import argparse
import importlib.util
import itertools
import sys
from pathlib import Path


def load_module():
    script_path = Path(__file__).with_name("backtest_elon_weekly.py")
    spec = importlib.util.spec_from_file_location("backtest_elon_weekly", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backtest_elon_weekly.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bt = load_module()


def parse_int_list(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_float_list(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def summarize(trades) -> tuple[int, float, float]:
    if not trades:
        return 0, 0.0, 0.0
    wins = sum(1 for trade in trades if trade.pnl > 0)
    total_pnl = sum(trade.pnl for trade in trades)
    return len(trades), (wins / len(trades)) * 100, total_pnl


def main() -> int:
    parser = argparse.ArgumentParser(description="Sensitivity grid for exploratory weekly Elon backtest.")
    parser.add_argument("--windows", type=int, default=10)
    parser.add_argument("--entry-hours-grid", default="24")
    parser.add_argument("--min-edge-grid", default="0.10")
    parser.add_argument("--upper-cutoff-grid", default="300,320,340,360")
    parser.add_argument("--mode", choices=["all", "no_only", "no_upper_only"], default="no_upper_only")
    parser.add_argument("--max-trades-per-window", type=int, default=1)
    parser.add_argument("--fidelity-minutes", type=int, default=60)
    args = parser.parse_args()

    entry_hours_grid = parse_int_list(args.entry_hours_grid)
    min_edge_grid = parse_float_list(args.min_edge_grid)
    upper_cutoff_grid = parse_int_list(args.upper_cutoff_grid)
    trackings = bt.load_closed_weekly_trackings(args.windows)

    print(f"windows_tested: {len(trackings)}")
    print(f"mode: {args.mode}")
    print(f"max_trades_per_window: {args.max_trades_per_window}")
    print()
    print("sensitivity:")

    for entry_hours, min_edge, upper_cutoff in itertools.product(
        entry_hours_grid,
        min_edge_grid,
        upper_cutoff_grid,
    ):
        trades = []
        for tracking in reversed(trackings):
            trades.extend(
                bt.backtest_tracking(
                    tracking,
                    entry_hours_after_start=entry_hours,
                    min_edge=min_edge,
                    fidelity_minutes=args.fidelity_minutes,
                    max_trades_per_window=args.max_trades_per_window,
                    mode=args.mode,
                    upper_cutoff=upper_cutoff,
                )
            )
        trade_count, win_rate, total_pnl = summarize(trades)
        avg_pnl = total_pnl / trade_count if trade_count else 0.0
        print(
            f"- entry_hours={entry_hours}, min_edge={min_edge:.2f}, upper_cutoff={upper_cutoff}: "
            f"trades={trade_count}, win_rate={bt.round4(win_rate)}%, "
            f"total_pnl={bt.round4(total_pnl)}, avg_pnl={bt.round4(avg_pnl)}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
