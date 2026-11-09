#!/usr/bin/env python3

import argparse
import importlib.util
import math
import sys
from dataclasses import dataclass
from pathlib import Path


def load_rank_module():
    script_path = Path(__file__).with_name("truth_social_rank.py")
    spec = importlib.util.spec_from_file_location("truth_social_rank", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load truth_social_rank.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rank = load_rank_module()
ev = rank.ev


@dataclass
class SizingPlan:
    label: str
    target_risk_pct: float
    shares: int
    risk_dollars: float
    max_profit_dollars: float


def round2(value: float) -> float:
    return math.floor(value * 100 + 0.5) / 100


def current_signal():
    now = rank.datetime.now(rank.timezone.utc)
    trackings = ev.load_active_trackings()
    prices = ev.auto_fetch_prices(trackings)
    candidates = rank.build_candidates(trackings, prices, now)

    filtered = [
        candidate for candidate in candidates
        if (
            candidate.edge > 0
            and rank.candidate_allowed(candidate, "no_upper_only")
            and rank.candidate_in_entry_window(candidate, 12.0, 30.0)
        )
    ]
    filtered.sort(key=lambda item: item.edge, reverse=True)

    deduped = []
    seen = set()
    for candidate in filtered:
        if candidate.slug in seen:
            continue
        seen.add(candidate.slug)
        deduped.append(candidate)

    return deduped[0] if deduped else None


def sizing_plans(bankroll: float, no_price: float) -> list[SizingPlan]:
    plan_inputs = [
        ("micro", 0.0675),
        ("moderate", 0.095),
        ("aggressive", 0.135),
    ]
    plans = []
    for label, risk_pct in plan_inputs:
        risk_budget = bankroll * risk_pct
        shares = max(int(risk_budget // no_price), 1)
        risk_dollars = shares * no_price
        max_profit_dollars = shares * (1.0 - no_price)
        plans.append(
            SizingPlan(
                label=label,
                target_risk_pct=risk_pct,
                shares=shares,
                risk_dollars=risk_dollars,
                max_profit_dollars=max_profit_dollars,
            )
        )
    return plans


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute practical position sizes for the current validated live signal."
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        default=50.0,
        help="Bankroll in dollars. Defaults to 50.",
    )
    args = parser.parse_args()

    signal = current_signal()
    if signal is None:
        print("No current validated signal found.")
        return 0

    no_price = signal.market
    yes_price = 1.0 - no_price

    print(f"bankroll: ${round2(args.bankroll)}")
    print(f"signal: {signal.slug} | {signal.side} {signal.bin_label}")
    print(f"market_no_price: {round2(no_price)}")
    print(f"market_yes_price: {round2(yes_price)}")
    print(f"edge: {round2(signal.edge * 100)} pts")
    print()
    print("plans:")
    for plan in sizing_plans(args.bankroll, no_price):
        print(
            f"- {plan.label}: shares={plan.shares}, "
            f"risk=${round2(plan.risk_dollars)}, "
            f"max_profit=${round2(plan.max_profit_dollars)}, "
            f"risk_pct={round2(plan.risk_dollars / args.bankroll * 100)}%"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
