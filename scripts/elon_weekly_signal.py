#!/usr/bin/env python3

import json
import math
import subprocess
import sys
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone


XTRACKER_URL = "https://xtracker.polymarket.com/api/users?stats=true&platform=X"
EVENT_URL_TEMPLATE = "https://gamma-api.polymarket.com/events?slug={slug}"
TARGET_HANDLE = "elonmusk"
TARGET_SERIES = "elon-tweets"


@dataclass
class Tracking:
    slug: str
    market_link: str
    start_date: datetime
    end_date: datetime
    total: int
    pace: float
    last_24h: int
    last_72h_avg: float


@dataclass
class BinCandidate:
    slug: str
    market_link: str
    bin_label: str
    side: str
    fair: float
    market: float
    edge: float
    hours_since_start: float


def fetch_json(url: str):
    result = subprocess.run(
        ["curl", "-s", url],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def round2(value: float) -> float:
    return math.floor(value * 100 + 0.5) / 100


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def scenario_rates() -> list[float]:
    return [20.0, 25.0, 30.0, 35.0, 40.0, 50.0, 60.0]


def scenario_center(tracking: Tracking) -> float:
    projected_daily = tracking.pace / 7.0
    last_72 = tracking.last_72h_avg if tracking.last_72h_avg > 0 else projected_daily
    last_24 = tracking.last_24h if tracking.last_24h > 0 else last_72
    momentum = last_24 - last_72
    center = 0.35 * projected_daily + 0.35 * last_72 + 0.30 * last_24 + 0.25 * momentum
    return clamp(center, 15.0, 70.0)


def scenario_spread(tracking: Tracking) -> float:
    projected_daily = tracking.pace / 7.0
    last_72 = tracking.last_72h_avg if tracking.last_72h_avg > 0 else projected_daily
    last_24 = tracking.last_24h if tracking.last_24h > 0 else last_72
    momentum = abs(last_24 - last_72)
    return 4.0 + 0.35 * momentum


def normalize(weights: list[float]) -> list[float]:
    total = sum(weights)
    return [weight / total for weight in weights] if total > 0 else [1.0 / len(weights)] * len(weights)


def scenario_weights(tracking: Tracking) -> list[float]:
    center = scenario_center(tracking)
    spread = scenario_spread(tracking)
    raw = []
    for rate in scenario_rates():
        distance = (rate - center) / spread
        raw.append(1.0 / (1.0 + distance * distance))
    return normalize(raw)


def expected_total(tracking: Tracking, posts_per_day: float, now: datetime) -> float:
    days_remaining = max((tracking.end_date - now).total_seconds(), 0) / 86400
    return tracking.total + posts_per_day * days_remaining


def fair_probability(tracking: Tracking, low: int, high: int, now: datetime) -> float:
    fair = 0.0
    for rate, weight in zip(scenario_rates(), scenario_weights(tracking)):
        total = expected_total(tracking, rate, now)
        if low <= total <= high:
            fair += weight
    return fair


def build_tracking(entry: dict) -> Tracking | None:
    if entry.get("handle") != TARGET_HANDLE or not entry.get("marketLink"):
        return None
    data = entry["tweetData"]
    daily = data.get("daily", [])
    slug = entry["marketLink"].split("/")[-1]
    return Tracking(
        slug=slug,
        market_link=entry["marketLink"],
        start_date=parse_dt(entry["startDate"]),
        end_date=parse_dt(entry["endDate"]),
        total=int(data["totalBetweenStartAndEnd"]),
        pace=float(data["pace"]),
        last_24h=int(daily[-1]["tweet_count"]) if daily else 0,
        last_72h_avg=(sum(item["tweet_count"] for item in daily[-3:]) / min(len(daily), 3)) if daily else 0.0,
    )


def parse_yes_price(market: dict) -> float | None:
    outcomes = json.loads(market.get("outcomes", "[]"))
    prices = json.loads(market.get("outcomePrices", "[]"))
    for outcome, price in zip(outcomes, prices):
        if outcome == "Yes":
            return float(price)
    return None


def parse_bin(value: str) -> tuple[int, int] | None:
    if not value or "+" in value or "-" not in value:
        return None
    parts = value.split("-")
    if len(parts) != 2:
        return None
    return int(parts[0]), int(parts[1])


def load_event_bins(slug: str) -> tuple[str | None, list[tuple[tuple[int, int], float]]]:
    raw = fetch_json(EVENT_URL_TEMPLATE.format(slug=slug))
    if not raw:
        return None, []
    event = raw[0]
    series_slug = event.get("seriesSlug")
    bins = []
    for market in event.get("markets", []):
        bin_range = parse_bin(market.get("groupItemTitle", ""))
        if not bin_range:
            continue
        yes_price = parse_yes_price(market)
        if yes_price is None:
            continue
        bins.append((bin_range, yes_price))
    bins.sort(key=lambda item: item[0][0])
    return series_slug, bins


def build_candidates(tracking: Tracking, bins: list[tuple[tuple[int, int], float]], now: datetime) -> list[BinCandidate]:
    candidates = []
    hours_since_start = max((now - tracking.start_date).total_seconds(), 0) / 3600
    for (low, high), yes_price in bins:
        fair_yes = fair_probability(tracking, low, high, now)
        fair_no = 1.0 - fair_yes
        no_price = 1.0 - yes_price
        label = f"{low}-{high}"
        candidates.append(
            BinCandidate(
                slug=tracking.slug,
                market_link=tracking.market_link,
                bin_label=label,
                side="YES",
                fair=fair_yes,
                market=yes_price,
                edge=fair_yes - yes_price,
                hours_since_start=hours_since_start,
            )
        )
        candidates.append(
            BinCandidate(
                slug=tracking.slug,
                market_link=tracking.market_link,
                bin_label=label,
                side="NO",
                fair=fair_no,
                market=no_price,
                edge=fair_no - no_price,
                hours_since_start=hours_since_start,
            )
        )
    return sorted(candidates, key=lambda item: item.edge, reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exploratory live signal for weekly Elon tweet markets.")
    parser.add_argument(
        "--mode",
        choices=["all", "no_only", "no_upper_only"],
        default="all",
        help="Exploratory trade-family filter.",
    )
    parser.add_argument(
        "--upper-cutoff",
        type=int,
        default=300,
        help="Minimum lower bound for upper bins when using no_upper_only mode.",
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
        "--one-per-window",
        action="store_true",
        help="Keep only the strongest candidate per market after filtering.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=8,
        help="Number of candidates to print per market.",
    )
    args = parser.parse_args()

    raw = fetch_json(XTRACKER_URL)
    now = datetime.now(timezone.utc)
    entries = raw["data"] if isinstance(raw, dict) and "data" in raw else raw

    trackings = []
    for entry in entries:
        tracking = build_tracking(entry)
        if tracking and tracking.end_date > now:
            trackings.append(tracking)

    print(f"snapshot_utc: {now.isoformat()}")
    print()

    for tracking in sorted(trackings, key=lambda item: item.start_date):
        series_slug, bins = load_event_bins(tracking.slug)
        if series_slug != TARGET_SERIES:
            continue

        print(f"# {tracking.slug}")
        print(f"market: {tracking.market_link}")
        print(f"current_total: {tracking.total}")
        print(f"pace: {round2(tracking.pace)}")
        print(f"posts_last_24h: {tracking.last_24h}")
        print(f"posts_last_72h_avg: {round2(tracking.last_72h_avg)}")
        print(f"scenario_center: {round2(scenario_center(tracking))}")
        print(f"scenario_spread: {round2(scenario_spread(tracking))}")
        print("top_candidates:")
        candidates = build_candidates(tracking, bins, now)
        hours_since_start = max((now - tracking.start_date).total_seconds(), 0) / 3600
        filtered = []
        for candidate in candidates:
            low = int(candidate.bin_label.split("-")[0])
            if args.mode == "no_only" and candidate.side != "NO":
                continue
            if args.mode == "no_upper_only" and not (candidate.side == "NO" and low >= args.upper_cutoff):
                continue
            if args.min_hours_since_start is not None and hours_since_start < args.min_hours_since_start:
                continue
            if args.max_hours_since_start is not None and hours_since_start > args.max_hours_since_start:
                continue
            filtered.append(candidate)

        if args.one_per_window:
            filtered = filtered[:1]

        top = filtered[: args.top]
        for candidate in top:
            print(
                f"  {candidate.side} {candidate.bin_label} | "
                f"fair={round2(candidate.fair * 100)}% | "
                f"market={round2(candidate.market * 100)}% | "
                f"edge={round2(candidate.edge * 100)} pts | "
                f"hours_since_start={round2(candidate.hours_since_start)}"
            )
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
