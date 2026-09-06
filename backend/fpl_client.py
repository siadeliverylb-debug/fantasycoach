"""Thin wrapper around the public Fantasy Premier League API with a small
in-memory TTL cache for the two heavy, mostly-static endpoints."""

import time

import requests

BASE = "https://fantasy.premierleague.com/api"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
CACHE_TTL_SECONDS = 15 * 60
LIVE_CACHE_TTL_SECONDS = 60  # live points change during matches - refresh often

_cache: dict[str, tuple[float, object]] = {}


def _get(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _cached_get(key: str, url: str, ttl: float = CACHE_TTL_SECONDS) -> dict:
    now = time.time()
    hit = _cache.get(key)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    data = _get(url)
    _cache[key] = (now, data)
    return data


def get_bootstrap() -> dict:
    """Players, teams, positions, gameweeks. Refreshed every ~15 min."""
    return _cached_get("bootstrap", f"{BASE}/bootstrap-static/")


def get_fixtures() -> list[dict]:
    """All fixtures with FDR. Refreshed every ~15 min."""
    return _cached_get("fixtures", f"{BASE}/fixtures/")


def get_current_event() -> dict | None:
    for event in get_bootstrap()["events"]:
        if event["is_current"]:
            return event
    # season not started yet / between seasons: fall back to next event
    for event in get_bootstrap()["events"]:
        if event["is_next"]:
            return event
    return None


def get_entry(team_id: int) -> dict:
    return _get(f"{BASE}/entry/{team_id}/")


def get_entry_history(team_id: int) -> dict:
    return _get(f"{BASE}/entry/{team_id}/history/")


def get_entry_picks(team_id: int, event: int) -> dict:
    return _get(f"{BASE}/entry/{team_id}/event/{event}/picks/")


def get_event_live(event: int) -> dict:
    """Live per-player stats (points, minutes, goals, etc.) for one gameweek -
    updates continuously while its matches are being played."""
    return _cached_get(
        f"event_live_{event}", f"{BASE}/event/{event}/live/", ttl=LIVE_CACHE_TTL_SECONDS
    )


def get_league_standings(league_id: int, page: int = 1) -> dict:
    return _get(
        f"{BASE}/leagues-classic/{league_id}/standings/?page_standings={page}"
    )
