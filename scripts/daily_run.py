#!/usr/bin/env python3

import argparse
import importlib.util
import math
import sys
from pathlib import Path


def load_module(filename: str, module_name: str):
    script_path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trump_size = load_module("position_size.py", "position_size")
elon_size = load_module("elon_position_size.py", "elon_position_size")


def round2(value: float) -> float:
    return math.floor(value * 100 + 0.5) / 100


def print_plan(label: str, signal, plans, preferred_label: str, bankroll_view: float) -> None:
    print(f"## {label}")
    if signal is None:
        print("No current signal.")
        print()
        return

    no_price = signal.market
    yes_price = 1.0 - no_price
    print(f"signal: {signal.slug} | {signal.side} {signal.bin_label}")
    print(f"market_no_price: {round2(no_price)}")
    print(f"market_yes_price: {round2(yes_price)}")
    print(f"edge: {round2(signal.edge * 100)} pts")
    print("sizes:")
    for plan in plans:
        marker = " <- preferred" if plan.label == preferred_label else ""
        risk_pct = (plan.risk_dollars / bankroll_view * 100) if bankroll_view > 0 else 0.0
        print(
            f"- {plan.label}: shares={plan.shares}, "
            f"risk=${round2(plan.risk_dollars)}, "
            f"max_profit=${round2(plan.max_profit_dollars)}, "
            f"risk_pct={round2(risk_pct)}%{marker}"
        )
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Daily combined run for Trump and Elon tweet-market workflows."
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        default=50.0,
        help="Total bankroll in dollars. Defaults to 50.",
    )
    parser.add_argument(
        "--trump-bankroll-pct",
        type=float,
        default=0.6,
        help="Fraction of total bankroll to allocate to the Trump sizing view. Defaults to 0.6.",
    )
    parser.add_argument(
        "--elon-bankroll-pct",
        type=float,
        default=0.4,
        help="Fraction of total bankroll to allocate to the Elon sizing view. Defaults to 0.4.",
    )
    args = parser.parse_args()

    trump_bankroll = args.bankroll * args.trump_bankroll_pct
    elon_bankroll = args.bankroll * args.elon_bankroll_pct

    trump_signal = trump_size.current_signal()
    trump_plans = trump_size.sizing_plans(trump_bankroll, trump_signal.market) if trump_signal else []

    elon_signal = elon_size.current_signal()
    elon_plans = elon_size.sizing_plans(elon_bankroll, elon_signal.market) if elon_signal else []

    print(f"total_bankroll: ${round2(args.bankroll)}")
    print(f"trump_bankroll_view: ${round2(trump_bankroll)}")
    print(f"elon_bankroll_view: ${round2(elon_bankroll)}")
    print()

    print_plan("Trump", trump_signal, trump_plans, preferred_label="micro", bankroll_view=trump_bankroll)
    print_plan("Elon", elon_signal, elon_plans, preferred_label="micro", bankroll_view=elon_bankroll)

    print("## Today")
    if trump_signal:
        trump_preferred = next((plan for plan in trump_plans if plan.label == "micro"), trump_plans[0])
        print(
            f"- Trump: {trump_signal.side} {trump_signal.bin_label} on {trump_signal.slug}, "
            f"{trump_preferred.shares} shares"
        )
    else:
        print("- Trump: no action")

    if elon_signal:
        elon_preferred = next((plan for plan in elon_plans if plan.label == "micro"), elon_plans[0])
        print(
            f"- Elon: {elon_signal.side} {elon_signal.bin_label} on {elon_signal.slug}, "
            f"{elon_preferred.shares} shares"
        )
    else:
        print("- Elon: no action")

    return 0


if __name__ == "__main__":
    sys.exit(main())
