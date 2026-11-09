#!/usr/bin/env python3

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


@dataclass
class Tracking:
    title: str
    market_link: str | None
    start_date: datetime
    end_date: datetime
    is_active: bool
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


def classify_regime(rate: float) -> str:
    if rate <= 10:
        return "quiet"
    if rate <= 13:
        return "base"
    if rate <= 16:
        return "active"
    return "spike"


def build_tracking(entry: dict) -> Tracking:
    data = entry["tweetData"]
    daily = data.get("daily", [])

    last_24h = daily[-1]["tweet_count"] if daily else 0
    last_72h = sum(item["tweet_count"] for item in daily[-3:])
    last_72h_avg = last_72h / min(len(daily), 3) if daily else 0.0

    return Tracking(
        title=entry["marketLink"].split("/")[-1] if entry.get("marketLink") else entry["handle"],
        market_link=entry.get("marketLink"),
        start_date=parse_dt(entry["startDate"]),
        end_date=parse_dt(entry["endDate"]),
        is_active=True,
        total=int(data["totalBetweenStartAndEnd"]),
        pace=float(data["pace"]),
        last_24h=int(last_24h),
        last_72h_avg=last_72h_avg,
    )


def print_tracking(tracking: Tracking, now: datetime) -> None:
    remaining_seconds = max((tracking.end_date - now).total_seconds(), 0)
    days_remaining = remaining_seconds / 86400

    print(f"# {tracking.title}")
    if tracking.market_link:
        print(f"market: {tracking.market_link}")
    print(f"current_total: {tracking.total}")
    print(f"pace: {round2(tracking.pace)}")
    print(f"posts_last_24h: {tracking.last_24h}")
    print(f"posts_last_72h_avg: {round2(tracking.last_72h_avg)}")
    print(f"days_remaining: {round2(days_remaining)}")
    print("bins:")

    for low, high in KEY_BINS:
        need_low = max(low - tracking.total, 0)
        need_high = max(high - tracking.total, 0)
        req_low = need_low / days_remaining if days_remaining > 0 else 0
        req_high = need_high / days_remaining if days_remaining > 0 else 0
        regime = classify_regime(req_low)
        print(
            "  "
            f"{low}-{high}: need={need_low}-{need_high}, "
            f"req/day={round2(req_low)}-{round2(req_high)}, "
            f"regime={regime}"
        )

    print()


def main() -> int:
    raw = fetch_json(TRACKINGS_URL)
    entries = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    now = datetime.now(timezone.utc)

    trackings = [
        build_tracking(entry)
        for entry in entries
        if entry.get("marketLink")
    ]

    active = [
        tracking for tracking in trackings
        if tracking.end_date > now
    ]
    active.sort(key=lambda item: item.start_date)

    if not active:
        print("No active trackings found.")
        return 0

    print(f"snapshot_utc: {now.isoformat()}")
    print()
    for tracking in active:
        print_tracking(tracking, now)

    return 0


if __name__ == "__main__":
    sys.exit(main())
