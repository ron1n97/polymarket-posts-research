#!/usr/bin/env python3

import argparse
import importlib.util
import math
import sys
from dataclasses import dataclass
from pathlib import Path


def load_module():
    script_path = Path(__file__).with_name("elon_weekly_signal.py")
    spec = importlib.util.spec_from_file_location("elon_weekly_signal", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load elon_weekly_signal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


elon = load_module()


@dataclass
class SizingPlan:
    label: str
    shares: int
    risk_dollars: float
    max_profit_dollars: float
    risk_pct: float


def round2(value: float) -> float:
    return math.floor(value * 100 + 0.5) / 100


def current_signal():
    raw = elon.fetch_json(elon.XTRACKER_URL)
    now = elon.datetime.now(elon.timezone.utc)
    entries = raw["data"] if isinstance(raw, dict) and "data" in raw else raw

    trackings = []
    for entry in entries:
        tracking = elon.build_tracking(entry)
        if tracking and tracking.end_date > now:
            trackings.append(tracking)

    candidates = []
    for tracking in sorted(trackings, key=lambda item: item.start_date):
        series_slug, bins = elon.load_event_bins(tracking.slug)
        if series_slug != elon.TARGET_SERIES:
            continue
        hours_since_start = max((now - tracking.start_date).total_seconds(), 0) / 3600
        if hours_since_start < 24 or hours_since_start > 36:
            continue
        current_candidates = elon.build_candidates(tracking, bins, now)
        filtered = []
        for candidate in current_candidates:
            low = int(candidate.bin_label.split("-")[0])
            if candidate.side == "NO" and low >= 300:
                filtered.append(candidate)
        if filtered:
            candidates.append(filtered[0])

    if not candidates:
        return None
    candidates.sort(key=lambda item: item.edge, reverse=True)
    return candidates[0]


def sizing_plans(bankroll: float, no_price: float) -> list[SizingPlan]:
    plan_inputs = [
        ("micro", 0.05),
        ("moderate", 0.08),
        ("aggressive", 0.12),
    ]
    plans = []
    for label, target_risk_pct in plan_inputs:
        risk_budget = bankroll * target_risk_pct
        shares = max(int(risk_budget // no_price), 1)
        risk_dollars = shares * no_price
        max_profit_dollars = shares * (1.0 - no_price)
        plans.append(
            SizingPlan(
                label=label,
                shares=shares,
                risk_dollars=risk_dollars,
                max_profit_dollars=max_profit_dollars,
                risk_pct=(risk_dollars / bankroll) if bankroll > 0 else 0.0,
            )
        )
    return plans


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute exploratory position sizes for the current weekly Elon live signal."
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
        print("No current exploratory Elon weekly signal found.")
        return 0

    no_price = signal.market
    yes_price = 1.0 - no_price

    print(f"bankroll: ${round2(args.bankroll)}")
    print("mode: exploratory")
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
            f"risk_pct={round2(plan.risk_pct * 100)}%"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
