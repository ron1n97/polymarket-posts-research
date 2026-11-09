#!/usr/bin/env python3

import argparse
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
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

TRACKINGS_URL = (
    "https://xtracker.polymarket.com/api/users/realDonaldTrump/trackings"
    "?platform=TRUTH_SOCIAL"
)
TRACKING_DETAIL_URL = "https://xtracker.polymarket.com/api/trackings/{tracking_id}?includeStats=true"
SERIES_URL = "https://gamma-api.polymarket.com/series?slug=trump-truth-social"


@dataclass
class HistoricalTracking:
    tracking_id: str
    slug: str
    title: str
    market_link: str
    start_date: datetime
    end_date: datetime


@dataclass
class Trade:
    slug: str
    bin_label: str
    side: str
    entry_time_utc: str
    entry_price: float
    fair: float
    edge: float
    outcome: int
    pnl: float


@lru_cache(maxsize=None)
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


def round4(value: float) -> float:
    return round(value, 4)


def seconds_between(left: datetime, right: datetime) -> float:
    return abs((left - right).total_seconds())


def find_matching_event(series_events: list[dict], start_date: datetime, end_date: datetime) -> dict | None:
    best = None
    best_score = None
    for event in series_events:
        if not event.get("slug") or not event.get("startTime") or not event.get("endDate"):
            continue
        event_start = parse_dt(event["startTime"])
        event_end = parse_dt(event["endDate"])
        score = seconds_between(start_date, event_start) + seconds_between(end_date, event_end)
        if best_score is None or score < best_score:
            best = event
            best_score = score
    if best_score is not None and best_score <= 3600:
        return best
    return None


def load_closed_trackings(limit: int) -> list[HistoricalTracking]:
    raw = fetch_json(TRACKINGS_URL)
    entries = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    series_raw = fetch_json(SERIES_URL)
    series_events = series_raw[0].get("events", []) if series_raw else []
    now = datetime.now(timezone.utc)
    trackings = []
    for entry in entries:
        start_date = parse_dt(entry["startDate"])
        end_date = parse_dt(entry["endDate"])
        if end_date >= now:
            continue
        market_link = entry.get("marketLink")
        slug = market_link.split("/")[-1] if market_link else None
        match = find_matching_event(series_events, start_date, end_date)
        if match:
            slug = match["slug"]
            market_link = f"https://polymarket.com/event/{slug}"
        if not market_link or not slug:
            continue
        trackings.append(
            HistoricalTracking(
                tracking_id=entry["id"],
                slug=slug,
                title=entry["title"],
                market_link=market_link,
                start_date=start_date,
                end_date=end_date,
            )
        )
    trackings.sort(key=lambda item: item.start_date, reverse=True)
    return trackings[:limit]


def load_tracking_detail(tracking_id: str) -> dict:
    return fetch_json(TRACKING_DETAIL_URL.format(tracking_id=tracking_id))["data"]


def parse_yes_token_id(market: dict) -> str | None:
    token_ids = json.loads(market.get("clobTokenIds", "[]"))
    outcomes = json.loads(market.get("outcomes", "[]"))
    for token_id, outcome in zip(token_ids, outcomes):
        if outcome == "Yes":
            return token_id
    return None


def load_event_market_map(slug: str) -> dict[tuple[int, int], dict]:
    raw = fetch_json(ev.EVENT_URL_TEMPLATE.format(slug=slug))
    if not raw:
        return {}
    event = raw[0]
    market_map = {}
    for market in event.get("markets", []):
        bin_range = ev.parse_group_item_title(market.get("groupItemTitle", ""))
        if bin_range in ev.KEY_BINS:
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
    if not eligible:
        return None
    return eligible[0]


def build_observation_detail(detail: dict) -> list[tuple[datetime, int]]:
    observations = []
    for item in detail["stats"]["daily"]:
        observations.append((parse_dt(item["date"]), int(item["cumulative"])))
    return observations


def observation_features(
    observations: list[tuple[datetime, int]],
    observation_index: int,
) -> tuple[int, float]:
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


def fair_from_observation(
    total: int,
    start_date: datetime,
    observation_time: datetime,
    end_date: datetime,
    last_24h: int,
    last_72h_avg: float,
) -> dict[tuple[int, int], float]:
    elapsed_days = max((observation_time - start_date).total_seconds(), 0) / 86400
    pace = (total / elapsed_days) * 7.0 if elapsed_days > 0 else 0.0
    temp_tracking = ev.Tracking(
        slug="historical",
        market_link="",
        start_date=start_date,
        end_date=end_date,
        total=total,
        pace=pace,
        last_24h=last_24h,
        last_72h_avg=last_72h_avg,
    )
    fair = {}
    for low, high in ev.KEY_BINS:
        fair[(low, high)] = ev.fair_probability(temp_tracking, low, high, observation_time)
    return fair


def compute_pnl(side: str, entry_price: float, won: bool) -> float:
    if side == "YES":
        return (1.0 - entry_price) if won else -entry_price
    no_price = 1.0 - entry_price
    return (1.0 - no_price) if won else -no_price


def determine_outcome(market: dict) -> int:
    yes_price = ev.parse_market_yes_price(market)
    return 1 if yes_price is not None and yes_price >= 0.999 else 0


def trade_group(trade: Trade) -> str:
    low = int(trade.bin_label.split("-")[0])
    if trade.side == "YES" and low < 80:
        return "YES_middle"
    if trade.side == "YES":
        return "YES_upper"
    if low >= 80:
        return "NO_upper"
    return "NO_middle"


def trade_allowed(trade: Trade, mode: str) -> bool:
    group = trade_group(trade)
    if mode == "all":
        return True
    if mode == "no_only":
        return trade.side == "NO"
    if mode == "no_upper_only":
        return group == "NO_upper"
    if mode == "no_upper_plus_middle":
        return group in {"NO_upper", "NO_middle"}
    raise ValueError(f"Unknown mode: {mode}")


def backtest_tracking(
    tracking: HistoricalTracking,
    entry_hours_after_start: int,
    min_edge: float,
    fidelity_minutes: int,
    max_trades_per_window: int,
    mode: str,
) -> list[Trade]:
    detail = load_tracking_detail(tracking.tracking_id)
    observations = build_observation_detail(detail)
    entry_cutoff = int((tracking.start_date.timestamp()) + entry_hours_after_start * 3600)
    observation_index = next(
        (idx for idx, item in enumerate(observations) if int(item[0].timestamp()) >= entry_cutoff),
        None,
    )
    if observation_index is None:
        return []

    observation_time, cumulative_total = observations[observation_index]
    last_24h, last_72h_avg = observation_features(observations, observation_index)
    event_market_map = load_event_market_map(tracking.slug)
    fairs = fair_from_observation(
        cumulative_total,
        tracking.start_date,
        observation_time,
        tracking.end_date,
        last_24h,
        last_72h_avg,
    )
    candidate_trades: list[Trade] = []

    for bin_range in ev.KEY_BINS:
        market = event_market_map.get(bin_range)
        if not market:
            continue
        token_id = parse_yes_token_id(market)
        if not token_id:
            continue
        history = load_price_history(token_id, tracking.start_date, tracking.end_date, fidelity_minutes)
        entry_point = select_entry_point(history, int(observation_time.timestamp()))
        if not entry_point:
            continue

        market_yes = float(entry_point["p"])
        fair_yes = fairs[bin_range]
        fair_no = 1.0 - fair_yes
        market_no = 1.0 - market_yes
        outcome_yes = determine_outcome(market)

        yes_edge = fair_yes - market_yes
        no_edge = fair_no - market_no

        if yes_edge >= min_edge and yes_edge >= no_edge:
            won = outcome_yes == 1
            candidate_trades.append(
                Trade(
                    slug=tracking.slug,
                    bin_label=f"{bin_range[0]}-{bin_range[1]}",
                    side="YES",
                    entry_time_utc=datetime.fromtimestamp(entry_point["t"], tz=timezone.utc).isoformat(),
                    entry_price=market_yes,
                    fair=fair_yes,
                    edge=yes_edge,
                    outcome=outcome_yes,
                    pnl=compute_pnl("YES", market_yes, won),
                )
            )
        elif no_edge >= min_edge:
            won = outcome_yes == 0
            candidate_trades.append(
                Trade(
                    slug=tracking.slug,
                    bin_label=f"{bin_range[0]}-{bin_range[1]}",
                    side="NO",
                    entry_time_utc=datetime.fromtimestamp(entry_point["t"], tz=timezone.utc).isoformat(),
                    entry_price=market_yes,
                    fair=fair_no,
                    edge=no_edge,
                    outcome=1 - outcome_yes,
                    pnl=compute_pnl("NO", market_yes, won),
                )
            )

    filtered_trades = [trade for trade in candidate_trades if trade_allowed(trade, mode)]
    filtered_trades.sort(key=lambda trade: trade.edge, reverse=True)
    return filtered_trades[:max_trades_per_window]


def summarize_trades(trades: list[Trade]) -> None:
    if not trades:
        print("No trades matched the baseline rules.")
        return

    total_pnl = sum(trade.pnl for trade in trades)
    wins = sum(1 for trade in trades if trade.pnl > 0)
    avg_pnl = total_pnl / len(trades)

    print(f"trades: {len(trades)}")
    print(f"wins: {wins}")
    print(f"win_rate: {round4(wins / len(trades) * 100)}%")
    print(f"total_pnl_per_1_share: {round4(total_pnl)}")
    print(f"avg_pnl_per_trade: {round4(avg_pnl)}")
    print()
    print("trade_log:")
    for trade in trades:
        print(
            f"- {trade.slug} | {trade.side} {trade.bin_label} | "
            f"entry={round4(trade.entry_price)} | fair={round4(trade.fair)} | "
            f"edge={round4(trade.edge)} | pnl={round4(trade.pnl)} | "
            f"at={trade.entry_time_utc}"
        )


def summarize_groups(trades: list[Trade]) -> None:
    if not trades:
        return

    groups: dict[str, list[Trade]] = {}
    for trade in trades:
        key = trade_group(trade)
        groups.setdefault(key, []).append(trade)

    print()
    print("group_summary:")
    for key in sorted(groups):
        group = groups[key]
        wins = sum(1 for trade in group if trade.pnl > 0)
        total_pnl = sum(trade.pnl for trade in group)
        avg_pnl = total_pnl / len(group)
        print(
            f"- {key}: trades={len(group)}, "
            f"win_rate={round4(wins / len(group) * 100)}%, "
            f"total_pnl={round4(total_pnl)}, "
            f"avg_pnl={round4(avg_pnl)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backtest the Truth Social baseline strategy on historical Polymarket prices."
    )
    parser.add_argument(
        "--windows",
        type=int,
        default=4,
        help="Number of closed windows to test, most recent first.",
    )
    parser.add_argument(
        "--entry-hours",
        type=int,
        default=24,
        help="Enter trades at the first observation at or after this many hours from market start.",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=0.10,
        help="Minimum model edge required to take a trade.",
    )
    parser.add_argument(
        "--fidelity-minutes",
        type=int,
        default=60,
        help="Price-history fidelity in minutes.",
    )
    parser.add_argument(
        "--max-trades-per-window",
        type=int,
        default=99,
        help="Maximum number of trades to allow per window, ranked by model edge.",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "no_only", "no_upper_only", "no_upper_plus_middle"],
        default="all",
        help="Trade filter mode.",
    )
    args = parser.parse_args()

    trackings = load_closed_trackings(args.windows)
    trades: list[Trade] = []
    for tracking in reversed(trackings):
        trades.extend(
            backtest_tracking(
                tracking,
                entry_hours_after_start=args.entry_hours,
                min_edge=args.min_edge,
                fidelity_minutes=args.fidelity_minutes,
                max_trades_per_window=args.max_trades_per_window,
                mode=args.mode,
            )
        )

    print(f"windows_tested: {len(trackings)}")
    print(f"entry_hours: {args.entry_hours}")
    print(f"min_edge: {args.min_edge}")
    print(f"max_trades_per_window: {args.max_trades_per_window}")
    print(f"mode: {args.mode}")
    print()
    summarize_trades(trades)
    summarize_groups(trades)
    return 0


if __name__ == "__main__":
    sys.exit(main())
