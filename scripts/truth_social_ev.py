#!/usr/bin/env python3

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone


TRACKINGS_URL = (
    "https://xtracker.polymarket.com/api/users?stats=true&platform=TRUTH_SOCIAL"
)

KEY_BINS = [
    (60, 79),
    (80, 99),
    (100, 119),
]

SCENARIO_RATES = [9.0, 11.0, 13.0, 16.0]
EVENT_URL_TEMPLATE = "https://gamma-api.polymarket.com/events?slug={slug}"


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


def build_tracking(entry: dict) -> Tracking:
    data = entry["tweetData"]
    daily = data.get("daily", [])
    slug = entry["marketLink"].split("/")[-1]

    last_24h = daily[-1]["tweet_count"] if daily else 0
    last_72h = sum(item["tweet_count"] for item in daily[-3:])
    last_72h_avg = last_72h / min(len(daily), 3) if daily else 0.0

    return Tracking(
        slug=slug,
        market_link=entry["marketLink"],
        start_date=parse_dt(entry["startDate"]),
        end_date=parse_dt(entry["endDate"]),
        total=int(data["totalBetweenStartAndEnd"]),
        pace=float(data["pace"]),
        last_24h=int(last_24h),
        last_72h_avg=last_72h_avg,
    )


def load_active_trackings() -> list[Tracking]:
    raw = fetch_json(TRACKINGS_URL)
    entries = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    now = datetime.now(timezone.utc)
    trackings = [
        build_tracking(entry)
        for entry in entries
        if entry.get("marketLink")
    ]
    return sorted(
        [tracking for tracking in trackings if tracking.end_date > now],
        key=lambda item: item.start_date,
    )


def parse_market_yes_price(market: dict) -> float | None:
    outcomes = json.loads(market.get("outcomes", "[]"))
    outcome_prices = json.loads(market.get("outcomePrices", "[]"))
    for outcome, price in zip(outcomes, outcome_prices):
        if outcome == "Yes":
            return float(price)
    return None


def parse_group_item_title(value: str) -> tuple[int, int] | None:
    if not value or "+" in value or "-" not in value:
        return None
    parts = value.split("-")
    if len(parts) != 2:
        return None
    low_str, high_str = parts
    return int(low_str), int(high_str)


def fetch_event_prices(slug: str) -> dict[tuple[str, tuple[int, int]], float]:
    raw = fetch_json(EVENT_URL_TEMPLATE.format(slug=slug))
    if not raw:
        return {}

    event = raw[0]
    prices = {}
    allowed_bins = set(KEY_BINS)

    for market in event.get("markets", []):
        bin_range = parse_group_item_title(market.get("groupItemTitle", ""))
        if bin_range is None or bin_range not in allowed_bins:
            continue
        yes_price = parse_market_yes_price(market)
        if yes_price is None:
            continue
        prices[(slug, bin_range)] = yes_price

    return prices


def auto_fetch_prices(trackings: list[Tracking]) -> dict[tuple[str, tuple[int, int]], float]:
    prices = {}
    for tracking in trackings:
        prices.update(fetch_event_prices(tracking.slug))
    return prices


def normalize(weights: list[float]) -> list[float]:
    total = sum(weights)
    if total <= 0:
        return [1.0 / len(weights)] * len(weights)
    return [weight / total for weight in weights]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def implied_daily_from_pace(tracking: Tracking) -> float:
    return tracking.pace / 7.0


def scenario_center(tracking: Tracking) -> float:
    projected_daily = implied_daily_from_pace(tracking)
    last_72 = tracking.last_72h_avg if tracking.last_72h_avg > 0 else projected_daily
    last_24 = tracking.last_24h if tracking.last_24h > 0 else last_72
    momentum = last_24 - last_72

    center = (
        0.35 * projected_daily
        + 0.35 * last_72
        + 0.30 * last_24
    )
    center += 0.35 * momentum
    return clamp(center, 6.0, 20.0)


def scenario_spread(tracking: Tracking) -> float:
    projected_daily = implied_daily_from_pace(tracking)
    last_72 = tracking.last_72h_avg if tracking.last_72h_avg > 0 else projected_daily
    last_24 = tracking.last_24h if tracking.last_24h > 0 else last_72
    momentum = abs(last_24 - last_72)
    return 1.75 + 0.25 * momentum


def scenario_weights(tracking: Tracking) -> list[float]:
    center = scenario_center(tracking)
    spread = scenario_spread(tracking)
    raw_weights = []
    for rate in SCENARIO_RATES:
        distance = (rate - center) / spread
        raw_weights.append(1.0 / (1.0 + distance * distance))
    return normalize(raw_weights)


def expected_total(tracking: Tracking, rate: float, now: datetime) -> float:
    days_remaining = max((tracking.end_date - now).total_seconds(), 0) / 86400
    return tracking.total + rate * days_remaining


def fair_probability(tracking: Tracking, low: int, high: int, now: datetime) -> float:
    weights = scenario_weights(tracking)
    fair = 0.0
    for rate, weight in zip(SCENARIO_RATES, weights):
        total = expected_total(tracking, rate, now)
        if low <= total <= high:
            fair += weight
    return fair


def parse_price_arg(value: str) -> tuple[str, tuple[int, int], float]:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(
            "price must be in the format slug:low-high:yes_price"
        )
    slug = parts[0]
    low_str, high_str = parts[1].split("-")
    yes_price = float(parts[2])
    return slug, (int(low_str), int(high_str)), yes_price


def load_price_lines(lines: list[str]) -> dict[tuple[str, tuple[int, int]], float]:
    prices = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        slug, bin_range, yes_price = parse_price_arg(line)
        prices[(slug, bin_range)] = yes_price
    return prices


def print_tracking_report(
    tracking: Tracking,
    now: datetime,
    prices: dict[tuple[str, tuple[int, int]], float],
) -> None:
    days_remaining = max((tracking.end_date - now).total_seconds(), 0) / 86400
    weights = scenario_weights(tracking)
    print(f"# {tracking.slug}")
    print(f"market: {tracking.market_link}")
    print(f"current_total: {tracking.total}")
    print(f"days_remaining: {round2(days_remaining)}")
    print(f"projected_daily_from_pace: {round2(implied_daily_from_pace(tracking))}")
    print(f"posts_last_24h: {tracking.last_24h}")
    print(f"posts_last_72h_avg: {round2(tracking.last_72h_avg)}")
    print(f"scenario_center: {round2(scenario_center(tracking))}")
    print(f"scenario_spread: {round2(scenario_spread(tracking))}")
    print("scenario_weights:")
    for rate, weight in zip(SCENARIO_RATES, weights):
        print(f"  {rate}/day -> {round2(weight * 100)}%")

    print("bins:")
    for low, high in KEY_BINS:
        fair = fair_probability(tracking, low, high, now)
        print(
            f"  {low}-{high}: fair_yes={round2(fair * 100)}%"
        )
        price_key = (tracking.slug, (low, high))
        if price_key in prices:
            yes_price = prices[price_key]
            no_price = 1.0 - yes_price
            yes_ev = fair - yes_price
            no_ev = (1.0 - fair) - no_price
            print(
                "    "
                f"market_yes={round2(yes_price * 100)}%, "
                f"ev_yes={round2(yes_ev * 100)} pts, "
                f"ev_no={round2(no_ev * 100)} pts"
            )
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute rough fair probabilities and EV for Truth Social post markets."
    )
    parser.add_argument(
        "--slug",
        help="Only show one market slug.",
    )
    parser.add_argument(
        "--price",
        action="append",
        default=[],
        help="Price in the format slug:low-high:yes_price, for example "
        "donald-trump-of-truth-social-posts-april-3-april-10:60-79:0.15",
    )
    parser.add_argument(
        "--price-file",
        help="Path to a text file containing one price per line in the same slug:low-high:yes_price format.",
    )
    parser.add_argument(
        "--auto-prices",
        action="store_true",
        help="Fetch current key-bin prices directly from the Polymarket Gamma API.",
    )
    args = parser.parse_args()

    prices = load_price_lines(args.price)
    if args.price_file:
        with open(args.price_file, "r", encoding="utf-8") as handle:
            file_prices = load_price_lines(handle.readlines())
        prices.update(file_prices)

    now = datetime.now(timezone.utc)
    trackings = load_active_trackings()
    if args.slug:
        trackings = [tracking for tracking in trackings if tracking.slug == args.slug]

    if not trackings:
        print("No matching active trackings found.")
        return 0

    if args.auto_prices:
        prices.update(auto_fetch_prices(trackings))

    print(f"snapshot_utc: {now.isoformat()}")
    print()
    for tracking in trackings:
        print_tracking_report(tracking, now, prices)

    return 0


if __name__ == "__main__":
    sys.exit(main())
