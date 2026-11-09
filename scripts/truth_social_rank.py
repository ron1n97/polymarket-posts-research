#!/usr/bin/env python3

import argparse
import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def load_ev_module():
    script_path = Path(__file__).with_name("truth_social_ev.py")
    spec = importlib.util.spec_from_file_location("truth_social_ev", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load truth_social_ev.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = load_ev_module()


@dataclass
class TradeCandidate:
    slug: str
    market_link: str
    bin_label: str
    side: str
    fair: float
    market: float
    edge: float
    hours_since_start: float


def candidate_group(candidate: TradeCandidate) -> str:
    low = int(candidate.bin_label.split("-")[0])
    if candidate.side == "YES" and low < 80:
        return "YES_middle"
    if candidate.side == "YES":
        return "YES_upper"
    if low >= 80:
        return "NO_upper"
    return "NO_middle"


def candidate_allowed(candidate: TradeCandidate, mode: str) -> bool:
    group = candidate_group(candidate)
    if mode == "all":
        return True
    if mode == "no_only":
        return candidate.side == "NO"
    if mode == "no_upper_only":
        return group == "NO_upper"
    if mode == "no_upper_plus_middle":
        return group in {"NO_upper", "NO_middle"}
    raise ValueError(f"Unknown mode: {mode}")


def candidate_in_entry_window(
    candidate: TradeCandidate,
    min_hours_since_start: float | None,
    max_hours_since_start: float | None,
) -> bool:
    if min_hours_since_start is not None and candidate.hours_since_start < min_hours_since_start:
        return False
    if max_hours_since_start is not None and candidate.hours_since_start > max_hours_since_start:
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rank top Truth Social post-market trades from live XTracker data and manual prices."
    )
    parser.add_argument(
        "--slug",
        action="append",
        default=[],
        help="Optional market slug filter. Can be passed multiple times.",
    )
    parser.add_argument(
        "--price",
        action="append",
        default=[],
        help="Price in the format slug:low-high:yes_price",
    )
    parser.add_argument(
        "--price-file",
        help="Path to a text file containing one price per line in the format slug:low-high:yes_price",
    )
    parser.add_argument(
        "--auto-prices",
        action="store_true",
        help="Fetch current key-bin prices directly from the Polymarket Gamma API.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of ranked trades to print.",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "no_only", "no_upper_only", "no_upper_plus_middle"],
        default="all",
        help="Filter live candidates by the historically-tested trade family.",
    )
    parser.add_argument(
        "--min-hours-since-start",
        type=float,
        help="Optional minimum market age in hours.",
    )
    parser.add_argument(
        "--max-hours-since-start",
        type=float,
        help="Optional maximum market age in hours.",
    )
    parser.add_argument(
        "--validated-entry-window",
        action="store_true",
        help="Apply the current historically-validated live entry window for no_upper_only mode.",
    )
    parser.add_argument(
        "--one-per-window",
        action="store_true",
        help="Keep only the strongest remaining candidate per market slug after filtering.",
    )
    return parser.parse_args()


def parse_prices(values: list[str]) -> dict[tuple[str, tuple[int, int]], float]:
    return ev.load_price_lines(values)


def build_candidates(trackings, prices, now: datetime) -> list[TradeCandidate]:
    candidates: list[TradeCandidate] = []
    for tracking in trackings:
        hours_since_start = max((now - tracking.start_date).total_seconds(), 0) / 3600
        for low, high in ev.KEY_BINS:
            key = (tracking.slug, (low, high))
            if key not in prices:
                continue

            fair_yes = ev.fair_probability(tracking, low, high, now)
            market_yes = prices[key]
            fair_no = 1.0 - fair_yes
            market_no = 1.0 - market_yes
            label = f"{low}-{high}"

            candidates.append(
                TradeCandidate(
                    slug=tracking.slug,
                    market_link=tracking.market_link,
                    bin_label=label,
                    side="YES",
                    fair=fair_yes,
                    market=market_yes,
                    edge=fair_yes - market_yes,
                    hours_since_start=hours_since_start,
                )
            )
            candidates.append(
                TradeCandidate(
                    slug=tracking.slug,
                    market_link=tracking.market_link,
                    bin_label=label,
                    side="NO",
                    fair=fair_no,
                    market=market_no,
                    edge=fair_no - market_no,
                    hours_since_start=hours_since_start,
                )
            )
    return candidates


def print_ranked(
    candidates: list[TradeCandidate],
    top_n: int,
    mode: str,
    min_hours_since_start: float | None,
    max_hours_since_start: float | None,
    one_per_window: bool,
) -> None:
    ranked = sorted(candidates, key=lambda item: item.edge, reverse=True)
    positive = [
        candidate for candidate in ranked
        if (
            candidate.edge > 0
            and candidate_allowed(candidate, mode)
            and candidate_in_entry_window(
                candidate,
                min_hours_since_start=min_hours_since_start,
                max_hours_since_start=max_hours_since_start,
            )
        )
    ]

    if one_per_window:
        deduped = []
        seen_slugs = set()
        for candidate in positive:
            if candidate.slug in seen_slugs:
                continue
            seen_slugs.add(candidate.slug)
            deduped.append(candidate)
        positive = deduped

    if not positive:
        print("No positive-edge trades found for the provided prices.")
        return

    print("top_trades:")
    for index, candidate in enumerate(positive[:top_n], start=1):
        print(
            f"{index}. {candidate.slug} | {candidate.side} {candidate.bin_label} | "
            f"fair={ev.round2(candidate.fair * 100)}% | "
            f"market={ev.round2(candidate.market * 100)}% | "
            f"edge={ev.round2(candidate.edge * 100)} pts | "
            f"hours_since_start={ev.round2(candidate.hours_since_start)}"
        )
        print(f"   {candidate.market_link}")


def main() -> int:
    args = parse_args()
    now = datetime.now(timezone.utc)
    prices = parse_prices(args.price)
    if args.price_file:
        with open(args.price_file, "r", encoding="utf-8") as handle:
            prices.update(ev.load_price_lines(handle.readlines()))
    trackings = ev.load_active_trackings()

    if args.slug:
        allowed = set(args.slug)
        trackings = [tracking for tracking in trackings if tracking.slug in allowed]

    if not trackings:
        print("No matching active trackings found.")
        return 0

    if args.auto_prices:
        prices.update(ev.auto_fetch_prices(trackings))

    min_hours_since_start = args.min_hours_since_start
    max_hours_since_start = args.max_hours_since_start
    if args.validated_entry_window and args.mode == "no_upper_only":
        min_hours_since_start = 12.0 if min_hours_since_start is None else min_hours_since_start
        max_hours_since_start = 30.0 if max_hours_since_start is None else max_hours_since_start

    candidates = build_candidates(trackings, prices, now)
    print(f"snapshot_utc: {now.isoformat()}")
    print(f"mode: {args.mode}")
    if min_hours_since_start is not None or max_hours_since_start is not None:
        print(
            "entry_window_hours: "
            f"{'-inf' if min_hours_since_start is None else min_hours_since_start}"
            " to "
            f"{'+inf' if max_hours_since_start is None else max_hours_since_start}"
        )
    print()
    print_ranked(
        candidates,
        args.top,
        args.mode,
        min_hours_since_start=min_hours_since_start,
        max_hours_since_start=max_hours_since_start,
        one_per_window=args.one_per_window,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
