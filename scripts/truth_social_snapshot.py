#!/usr/bin/env python3

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
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
class SnapshotRow:
    snapshot_utc: str
    slug: str
    market_link: str
    current_total: int
    pace: float
    projected_daily_from_pace: float
    posts_last_24h: int
    posts_last_72h_avg: float
    days_remaining: float
    bin_low: int
    bin_high: int
    market_yes: float | None
    market_no: float | None
    fair_yes: float
    fair_no: float
    edge_yes: float | None
    edge_no: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist live Truth Social market snapshots as JSONL."
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
        help="Manual price in the format slug:low-high:yes_price",
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
        "--output",
        default="data/snapshots/truth_social_snapshots.jsonl",
        help="Output JSONL path. Defaults to data/snapshots/truth_social_snapshots.jsonl",
    )
    return parser.parse_args()


def collect_prices(args: argparse.Namespace, trackings) -> dict[tuple[str, tuple[int, int]], float]:
    prices = ev.load_price_lines(args.price)
    if args.price_file:
        with open(args.price_file, "r", encoding="utf-8") as handle:
            prices.update(ev.load_price_lines(handle.readlines()))
    if args.auto_prices:
        prices.update(ev.auto_fetch_prices(trackings))
    return prices


def build_rows(trackings, prices, now: datetime) -> list[SnapshotRow]:
    rows: list[SnapshotRow] = []
    snapshot_utc = now.isoformat()

    for tracking in trackings:
        days_remaining = max((tracking.end_date - now).total_seconds(), 0) / 86400
        projected_daily = tracking.pace / 7.0
        for low, high in ev.KEY_BINS:
            price_key = (tracking.slug, (low, high))
            market_yes = prices.get(price_key)
            market_no = None if market_yes is None else 1.0 - market_yes
            fair_yes = ev.fair_probability(tracking, low, high, now)
            fair_no = 1.0 - fair_yes
            edge_yes = None if market_yes is None else fair_yes - market_yes
            edge_no = None if market_no is None else fair_no - market_no

            rows.append(
                SnapshotRow(
                    snapshot_utc=snapshot_utc,
                    slug=tracking.slug,
                    market_link=tracking.market_link,
                    current_total=tracking.total,
                    pace=tracking.pace,
                    projected_daily_from_pace=projected_daily,
                    posts_last_24h=tracking.last_24h,
                    posts_last_72h_avg=tracking.last_72h_avg,
                    days_remaining=days_remaining,
                    bin_low=low,
                    bin_high=high,
                    market_yes=market_yes,
                    market_no=market_no,
                    fair_yes=fair_yes,
                    fair_no=fair_no,
                    edge_yes=edge_yes,
                    edge_no=edge_no,
                )
            )

    return rows


def write_jsonl(rows: list[SnapshotRow], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), sort_keys=True) + "\n")


def main() -> int:
    args = parse_args()
    now = datetime.now(timezone.utc)
    trackings = ev.load_active_trackings()

    if args.slug:
        allowed = set(args.slug)
        trackings = [tracking for tracking in trackings if tracking.slug in allowed]

    if not trackings:
        print("No matching active trackings found.")
        return 0

    prices = collect_prices(args, trackings)
    rows = build_rows(trackings, prices, now)
    output_path = Path(args.output)
    write_jsonl(rows, output_path)

    print(f"snapshot_utc: {now.isoformat()}")
    print(f"rows_written: {len(rows)}")
    print(f"output: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
