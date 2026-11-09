#!/usr/bin/env python3

import argparse
import importlib.util
import itertools
import sys
from pathlib import Path


def load_backtest_module():
    script_path = Path(__file__).with_name("backtest_truth_social_baseline.py")
    spec = importlib.util.spec_from_file_location("backtest_truth_social_baseline", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backtest_truth_social_baseline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bt = load_backtest_module()


def parse_int_list(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_float_list(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def summarize_compact(trades) -> dict:
    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "avg_pnl": 0.0,
        }

    wins = sum(1 for trade in trades if trade.pnl > 0)
    total_pnl = sum(trade.pnl for trade in trades)
    return {
        "trades": len(trades),
        "wins": wins,
        "win_rate": (wins / len(trades)) * 100,
        "total_pnl": total_pnl,
        "avg_pnl": total_pnl / len(trades),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a sensitivity grid for the Truth Social baseline backtest."
    )
    parser.add_argument("--windows", type=int, default=20)
    parser.add_argument("--entry-hours-grid", default="12,24,36,48")
    parser.add_argument("--min-edge-grid", default="0.05,0.10,0.15")
    parser.add_argument("--mode", default="no_upper_only", choices=["all", "no_only", "no_upper_only", "no_upper_plus_middle"])
    parser.add_argument("--max-trades-per-window", type=int, default=1)
    parser.add_argument("--fidelity-minutes", type=int, default=60)
    args = parser.parse_args()

    entry_hours_grid = parse_int_list(args.entry_hours_grid)
    min_edge_grid = parse_float_list(args.min_edge_grid)
    trackings = bt.load_closed_trackings(args.windows)

    print(f"windows_tested: {len(trackings)}")
    print(f"mode: {args.mode}")
    print(f"max_trades_per_window: {args.max_trades_per_window}")
    print()
    print("sensitivity:")

    for entry_hours, min_edge in itertools.product(entry_hours_grid, min_edge_grid):
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
                )
            )
        summary = summarize_compact(trades)
        print(
            f"- entry_hours={entry_hours}, min_edge={min_edge:.2f}: "
            f"trades={summary['trades']}, "
            f"win_rate={bt.round4(summary['win_rate'])}%, "
            f"total_pnl={bt.round4(summary['total_pnl'])}, "
            f"avg_pnl={bt.round4(summary['avg_pnl'])}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
