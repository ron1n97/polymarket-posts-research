#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache


TRACKINGS_URL = "https://xtracker.polymarket.com/api/users/elonmusk/trackings?platform=X"
TRACKING_DETAIL_URL = "https://xtracker.polymarket.com/api/trackings/{tracking_id}?includeStats=true"
SERIES_URL = "https://gamma-api.polymarket.com/series?slug=elon-tweets"
EVENT_URL_TEMPLATE = "https://gamma-api.polymarket.com/events?slug={slug}"


@dataclass
class HistoricalTracking:
    tracking_id: str
    slug: str
    market_link: str
    start_date: datetime
    end_date: datetime


@dataclass
class TrackingState:
    start_date: datetime
    end_date: datetime
    total: int
    pace: float
    last_24h: int
    last_72h_avg: float


@dataclass
class Trade:
    slug: str
    bin_label: str
    side: str
    entry_time_utc: str
    entry_price: float
    fair: float
    edge: float
    pnl: float


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def round4(value: float) -> float:
    return round(value, 4)


@lru_cache(maxsize=None)
def fetch_json(url: str):
    last_error: Exception | None = None
    try:
        import requests

        for attempt in range(4):
            try:
                response = requests.get(url, timeout=45)
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == 3:
                    break
    except ImportError:
        pass

    for _ in range(3):
        result = subprocess.run(
            ["curl", "-sS", "--retry", "3", "--retry-delay", "1", url],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        last_error = RuntimeError(result.stderr.strip() or f"curl exit {result.returncode}")
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def seconds_between(left: datetime, right: datetime) -> float:
    return abs((left - right).total_seconds())


def parse_yes_price(market: dict) -> float | None:
    outcomes = json.loads(market.get("outcomes", "[]"))
    prices = json.loads(market.get("outcomePrices", "[]"))
    for outcome, price in zip(outcomes, prices):
        if outcome == "Yes":
            return float(price)
    return None


def parse_yes_token_id(market: dict) -> str | None:
    token_ids = json.loads(market.get("clobTokenIds", "[]"))
    outcomes = json.loads(market.get("outcomes", "[]"))
    for token_id, outcome in zip(token_ids, outcomes):
        if outcome == "Yes":
            return token_id
    return None


def parse_bin(value: str) -> tuple[int, int] | None:
    if not value or "+" in value or "-" not in value:
        return None
    parts = value.split("-")
    if len(parts) != 2:
        return None
    return int(parts[0]), int(parts[1])


def duration_days(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 86400


def scenario_rates() -> list[float]:
    return [20.0, 25.0, 30.0, 35.0, 40.0, 50.0, 60.0]


def normalize(weights: list[float]) -> list[float]:
    total = sum(weights)
    return [weight / total for weight in weights] if total > 0 else [1.0 / len(weights)] * len(weights)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def scenario_center(state: TrackingState) -> float:
    projected_daily = state.pace / 7.0
    last_72 = state.last_72h_avg if state.last_72h_avg > 0 else projected_daily
    last_24 = state.last_24h if state.last_24h > 0 else last_72
    momentum = last_24 - last_72
    center = 0.35 * projected_daily + 0.35 * last_72 + 0.30 * last_24 + 0.25 * momentum
    return clamp(center, 15.0, 70.0)


def scenario_spread(state: TrackingState) -> float:
    projected_daily = state.pace / 7.0
    last_72 = state.last_72h_avg if state.last_72h_avg > 0 else projected_daily
    last_24 = state.last_24h if state.last_24h > 0 else last_72
    momentum = abs(last_24 - last_72)
    return 4.0 + 0.35 * momentum


def scenario_weights(state: TrackingState) -> list[float]:
    center = scenario_center(state)
    spread = scenario_spread(state)
    raw = []
    for rate in scenario_rates():
        distance = (rate - center) / spread
        raw.append(1.0 / (1.0 + distance * distance))
    return normalize(raw)


def expected_total(state: TrackingState, daily_rate: float, now: datetime) -> float:
    days_remaining = max((state.end_date - now).total_seconds(), 0) / 86400
    return state.total + daily_rate * days_remaining


def fair_probability(state: TrackingState, low: int, high: int, now: datetime) -> float:
    fair = 0.0
    for rate, weight in zip(scenario_rates(), scenario_weights(state)):
        total = expected_total(state, rate, now)
        if low <= total <= high:
            fair += weight
    return fair


def load_weekly_series_events() -> list[dict]:
    raw = fetch_json(SERIES_URL)
    events = raw[0].get("events", []) if raw else []
    weekly = []
    for event in events:
        if not event.get("slug") or not event.get("startTime") or not event.get("endDate"):
            continue
        start_date = parse_dt(event["startTime"])
        end_date = parse_dt(event["endDate"])
        days = duration_days(start_date, end_date)
        if 6.5 <= days <= 7.5:
            weekly.append(event)
    return weekly


def find_matching_event(series_events: list[dict], start_date: datetime, end_date: datetime) -> dict | None:
    best = None
    best_score = None
    for event in series_events:
        event_start = parse_dt(event["startTime"])
        event_end = parse_dt(event["endDate"])
        score = seconds_between(start_date, event_start) + seconds_between(end_date, event_end)
        if best_score is None or score < best_score:
            best = event
            best_score = score
    if best_score is not None and best_score <= 3600:
        return best
    return None


def load_closed_weekly_trackings(limit: int) -> list[HistoricalTracking]:
    raw = fetch_json(TRACKINGS_URL)
    entries = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    series_events = load_weekly_series_events()
    now = datetime.now(timezone.utc)
    trackings = []
    for entry in entries:
        start_date = parse_dt(entry["startDate"])
        end_date = parse_dt(entry["endDate"])
        if end_date >= now:
            continue
        if not (6.5 <= duration_days(start_date, end_date) <= 7.5):
            continue
        match = find_matching_event(series_events, start_date, end_date)
        if not match:
            continue
        slug = match["slug"]
        trackings.append(
            HistoricalTracking(
                tracking_id=entry["id"],
                slug=slug,
                market_link=f"https://polymarket.com/event/{slug}",
                start_date=start_date,
                end_date=end_date,
            )
        )
    trackings.sort(key=lambda item: item.start_date, reverse=True)
    return trackings[:limit]


def load_tracking_detail(tracking_id: str) -> dict:
    return fetch_json(TRACKING_DETAIL_URL.format(tracking_id=tracking_id))["data"]


def load_event_market_map(slug: str) -> dict[tuple[int, int], dict]:
    raw = fetch_json(EVENT_URL_TEMPLATE.format(slug=slug))
    if not raw:
        return {}
    event = raw[0]
    market_map = {}
    for market in event.get("markets", []):
        bin_range = parse_bin(market.get("groupItemTitle", ""))
        if bin_range:
            market_map[bin_range] = market
    return market_map


def load_price_history(token_id: str, start: datetime, end: datetime, fidelity_minutes: int) -> list[dict]:
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    url = (
        "https://clob.polymarket.com/prices-history"
        f"?market={token_id}&startTs={start_ts}&endTs={end_ts}&fidelity={fidelity_minutes}"
    )
    raw = fetch_json(url)
    return raw.get("history", [])


def select_entry_point(points: list[dict], entry_ts: int) -> dict | None:
    eligible = [point for point in points if point["t"] >= entry_ts]
    return eligible[0] if eligible else None


def build_observations(detail: dict) -> list[tuple[datetime, int]]:
    return [(parse_dt(item["date"]), int(item["cumulative"])) for item in detail["stats"]["daily"]]


def observation_features(observations: list[tuple[datetime, int]], observation_index: int) -> tuple[int, float]:
    current_total = observations[observation_index][1]
    if observation_index >= 24:
        total_24h_ago = observations[observation_index - 24][1]
        last_24h = current_total - total_24h_ago
    else:
        last_24h = current_total
    if observation_index >= 72:
        total_72h_ago = observations[observation_index - 72][1]
    else:
        total_72h_ago = 0
    elapsed_hours = max(observation_index + 1, 1)
    lookback_hours = min(elapsed_hours, 72)
    effective_days = max(lookback_hours / 24.0, 1 / 24.0)
    last_72h_avg = (current_total - total_72h_ago) / effective_days
    return last_24h, last_72h_avg


def compute_pnl(side: str, yes_price: float, won: bool) -> float:
    if side == "YES":
        return (1.0 - yes_price) if won else -yes_price
    no_price = 1.0 - yes_price
    return (1.0 - no_price) if won else -no_price


def trade_allowed(side: str, bin_label: str, mode: str, upper_cutoff: int) -> bool:
    low = int(bin_label.split("-")[0])
    if mode == "all":
        return True
    if mode == "no_only":
        return side == "NO"
    if mode == "no_upper_only":
        return side == "NO" and low >= upper_cutoff
    raise ValueError(f"Unknown mode: {mode}")


def backtest_tracking(
    tracking: HistoricalTracking,
    entry_hours_after_start: int,
    min_edge: float,
    fidelity_minutes: int,
    max_trades_per_window: int,
    mode: str,
    upper_cutoff: int,
) -> list[Trade]:
    detail = load_tracking_detail(tracking.tracking_id)
    observations = build_observations(detail)
    entry_cutoff = int(tracking.start_date.timestamp()) + entry_hours_after_start * 3600
    observation_index = next(
        (idx for idx, item in enumerate(observations) if int(item[0].timestamp()) >= entry_cutoff),
        None,
    )
    if observation_index is None:
        return []

    observation_time, cumulative_total = observations[observation_index]
    last_24h, last_72h_avg = observation_features(observations, observation_index)
    state = TrackingState(
        start_date=tracking.start_date,
        end_date=tracking.end_date,
        total=cumulative_total,
        pace=(cumulative_total / max((observation_time - tracking.start_date).total_seconds(), 1)) * 7 * 86400,
        last_24h=last_24h,
        last_72h_avg=last_72h_avg,
    )

    event_market_map = load_event_market_map(tracking.slug)
    candidates = []

    for bin_range, market in event_market_map.items():
        label = f"{bin_range[0]}-{bin_range[1]}"
        if mode == "no_upper_only" and not trade_allowed("NO", label, mode, upper_cutoff):
            continue
        token_id = parse_yes_token_id(market)
        if not token_id:
            continue
        history = load_price_history(token_id, tracking.start_date, tracking.end_date, fidelity_minutes)
        entry_point = select_entry_point(history, int(observation_time.timestamp()))
        if not entry_point:
            continue

        market_yes = float(entry_point["p"])
        fair_yes = fair_probability(state, bin_range[0], bin_range[1], observation_time)
        fair_no = 1.0 - fair_yes
        market_no = 1.0 - market_yes
        yes_edge = fair_yes - market_yes
        no_edge = fair_no - market_no
        resolved_yes = 1 if parse_yes_price(market) and parse_yes_price(market) >= 0.999 else 0

        if yes_edge >= min_edge:
            candidates.append(
                Trade(
                    slug=tracking.slug,
                    bin_label=label,
                    side="YES",
                    entry_time_utc=datetime.fromtimestamp(entry_point["t"], tz=timezone.utc).isoformat(),
                    entry_price=market_yes,
                    fair=fair_yes,
                    edge=yes_edge,
                    pnl=compute_pnl("YES", market_yes, resolved_yes == 1),
                )
            )
        if no_edge >= min_edge:
            candidates.append(
                Trade(
                    slug=tracking.slug,
                    bin_label=label,
                    side="NO",
                    entry_time_utc=datetime.fromtimestamp(entry_point["t"], tz=timezone.utc).isoformat(),
                    entry_price=market_yes,
                    fair=fair_no,
                    edge=no_edge,
                    pnl=compute_pnl("NO", market_yes, resolved_yes == 0),
                )
            )

    filtered = [
        trade for trade in candidates
        if trade_allowed(trade.side, trade.bin_label, mode, upper_cutoff)
    ]
    filtered.sort(key=lambda trade: trade.edge, reverse=True)
    return filtered[:max_trades_per_window]


def summarize(trades: list[Trade]) -> None:
    if not trades:
        print("No trades matched.")
        return
    wins = sum(1 for trade in trades if trade.pnl > 0)
    total_pnl = sum(trade.pnl for trade in trades)
    print(f"trades: {len(trades)}")
    print(f"wins: {wins}")
    print(f"win_rate: {round4(wins / len(trades) * 100)}%")
    print(f"total_pnl_per_1_share: {round4(total_pnl)}")
    print(f"avg_pnl_per_trade: {round4(total_pnl / len(trades))}")
    print()
    print("trade_log:")
    for trade in trades:
        print(
            f"- {trade.slug} | {trade.side} {trade.bin_label} | "
            f"entry={round4(trade.entry_price)} | fair={round4(trade.fair)} | "
            f"edge={round4(trade.edge)} | pnl={round4(trade.pnl)} | at={trade.entry_time_utc}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Exploratory weekly Elon backtest.")
    parser.add_argument("--windows", type=int, default=30)
    parser.add_argument("--entry-hours", type=int, default=24)
    parser.add_argument("--min-edge", type=float, default=0.10)
    parser.add_argument("--fidelity-minutes", type=int, default=60)
    parser.add_argument("--max-trades-per-window", type=int, default=1)
    parser.add_argument("--mode", choices=["all", "no_only", "no_upper_only"], default="all")
    parser.add_argument("--upper-cutoff", type=int, default=320)
    args = parser.parse_args()

    trackings = load_closed_weekly_trackings(args.windows)
    trades = []
    for tracking in reversed(trackings):
        trades.extend(
            backtest_tracking(
                tracking,
                entry_hours_after_start=args.entry_hours,
                min_edge=args.min_edge,
                fidelity_minutes=args.fidelity_minutes,
                max_trades_per_window=args.max_trades_per_window,
                mode=args.mode,
                upper_cutoff=args.upper_cutoff,
            )
        )

    print(f"windows_tested: {len(trackings)}")
    print(f"entry_hours: {args.entry_hours}")
    print(f"min_edge: {args.min_edge}")
    print(f"mode: {args.mode}")
    print(f"upper_cutoff: {args.upper_cutoff}")
    print()
    summarize(trades)
    return 0


if __name__ == "__main__":
    sys.exit(main())
