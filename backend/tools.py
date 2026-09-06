"""Tool schemas (for Claude tool use) and their Python implementations,
all backed by backend.fpl_client."""

import difflib
import re
from datetime import datetime, timezone
from typing import Any

from . import db
from . import fpl_client as fpl

# ---------------------------------------------------------------------------
# Lookup helpers built from bootstrap-static
# ---------------------------------------------------------------------------


def _positions() -> dict[int, str]:
    return {p["id"]: p["singular_name_short"] for p in fpl.get_bootstrap()["element_types"]}


def _teams() -> dict[int, dict]:
    return {t["id"]: t for t in fpl.get_bootstrap()["teams"]}


def _player_full_name(p: dict) -> str:
    return f"{p['first_name']} {p['second_name']}".strip()


def _serialize_player(p: dict) -> dict[str, Any]:
    teams = _teams()
    positions = _positions()
    team = teams.get(p["team"], {})
    return {
        "id": p["id"],
        "name": _player_full_name(p),
        "web_name": p["web_name"],
        "team": team.get("name"),
        "team_short": team.get("short_name"),
        "team_code": team.get("code"),
        "position": positions.get(p["element_type"]),
        "price_m": p["now_cost"] / 10,
        "form": p["form"],
        "total_points": p["total_points"],
        "points_per_game": p["points_per_game"],
        "selected_by_percent": p["selected_by_percent"],
        "minutes": p["minutes"],
        "goals_scored": p["goals_scored"],
        "assists": p["assists"],
        "expected_goals": p.get("expected_goals"),
        "expected_assists": p.get("expected_assists"),
        "ict_index": p.get("ict_index"),
        "bonus": p.get("bonus"),
        "status": p["status"],  # a=available, d=doubtful, i=injured, s=suspended, u=unavailable
        "news": p.get("news") or None,
        "chance_of_playing_next_round": p.get("chance_of_playing_next_round"),
    }


def _find_players(query: str, limit: int = 5) -> list[dict]:
    players = fpl.get_bootstrap()["elements"]
    query_l = query.lower().strip()

    substring_hits = [
        p for p in players
        if query_l in p["web_name"].lower() or query_l in _player_full_name(p).lower()
    ]
    if substring_hits:
        substring_hits.sort(key=lambda p: p["total_points"], reverse=True)
        return substring_hits[:limit]

    names = {p["id"]: f"{p['web_name']} {_player_full_name(p)}".lower() for p in players}
    close = difflib.get_close_matches(query_l, names.values(), n=limit, cutoff=0.5)
    matched_ids = [pid for pid, name in names.items() if name in close]
    id_set = set(matched_ids)
    return [p for p in players if p["id"] in id_set][:limit]


def _find_team_id(name: str) -> int | None:
    name_l = name.lower().strip()
    for t in _teams().values():
        if name_l in (t["name"].lower(), t["short_name"].lower()):
            return t["id"]
    close = difflib.get_close_matches(
        name_l, [t["name"].lower() for t in _teams().values()], n=1, cutoff=0.4
    )
    if close:
        for t in _teams().values():
            if t["name"].lower() == close[0]:
                return t["id"]
    return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def search_players(query: str, limit: int = 5) -> dict:
    matches = _find_players(query, limit)
    if not matches:
        return {"error": f"No players found matching '{query}'"}
    return {"players": [_serialize_player(p) for p in matches]}


def compare_players(names: list[str]) -> dict:
    results = []
    for name in names:
        matches = _find_players(name, limit=1)
        if matches:
            results.append(_serialize_player(matches[0]))
        else:
            results.append({"error": f"No player found matching '{name}'"})
    return {"comparison": results}


def get_top_performers(position: str = "all", metric: str = "total_points", limit: int = 5) -> dict:
    players = fpl.get_bootstrap()["elements"]
    positions = _positions()
    pos_short_to_id = {v: k for k, v in positions.items()}

    if position.lower() != "all":
        pos_id = pos_short_to_id.get(position.upper())
        if pos_id is None:
            return {"error": f"Unknown position '{position}'. Use GKP, DEF, MID, FWD, or all."}
        players = [p for p in players if p["element_type"] == pos_id]

    def sort_key(p: dict):
        val = p.get(metric)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    if not players or metric not in players[0]:
        return {"error": f"Unknown metric '{metric}'."}

    players = sorted(players, key=sort_key, reverse=True)[:limit]
    return {"position": position, "metric": metric, "players": [_serialize_player(p) for p in players]}


def get_fixture_difficulty(team_name: str, num_gameweeks: int = 5) -> dict:
    team_id = _find_team_id(team_name)
    if team_id is None:
        return {"error": f"No team found matching '{team_name}'"}

    teams = _teams()
    fixtures = [
        f for f in fpl.get_fixtures()
        if f["event"] is not None
        and not f["finished"]
        and (f["team_h"] == team_id or f["team_a"] == team_id)
    ]
    fixtures.sort(key=lambda f: f["event"])
    fixtures = fixtures[:num_gameweeks]

    out = []
    for f in fixtures:
        is_home = f["team_h"] == team_id
        opponent_id = f["team_a"] if is_home else f["team_h"]
        difficulty = f["team_h_difficulty"] if is_home else f["team_a_difficulty"]
        out.append({
            "gameweek": f["event"],
            "opponent": teams.get(opponent_id, {}).get("name"),
            "venue": "home" if is_home else "away",
            "difficulty": difficulty,  # FPL scale 1 (easiest) - 5 (hardest)
        })

    return {"team": teams[team_id]["name"], "fixtures": out}


def get_gameweek_status() -> dict:
    current = fpl.get_current_event()
    if current is None:
        return {"error": "No current/next gameweek found."}
    return {
        "id": current["id"],
        "name": current["name"],
        "deadline_time": current["deadline_time"],
        "finished": current["finished"],
        "is_current": current["is_current"],
        "is_next": current["is_next"],
    }


def get_next_deadline() -> dict:
    """Always points at the next transfer deadline that hasn't passed yet -
    based on the deadline time itself, not the event's 'finished' flag, which
    FPL doesn't set until bonus points are confirmed (often a day or more
    after its matches, and therefore after its deadline). Using 'finished'
    here would keep pointing at a gameweek whose deadline already passed -
    already locked, un-actionable - for that whole lag window. Also returns
    the previous gameweek's deadline as window_start, so the frontend can
    draw a progress bar across the current gameweek window."""
    events = fpl.get_bootstrap()["events"]
    now = datetime.now(timezone.utc)
    for i, event in enumerate(events):
        deadline = datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00"))
        if deadline > now:
            window_start = events[i - 1]["deadline_time"] if i > 0 else None
            return {
                "id": event["id"],
                "name": event["name"],
                "deadline_time": event["deadline_time"],
                "window_start": window_start,
                "is_current": event["is_current"],
                "is_next": event["is_next"],
            }
    return {"error": "No upcoming gameweek found."}


def _fixture_for_team(team_id: int, gameweek: int | None = None) -> dict | None:
    """Find the single fixture a team plays in `gameweek` (pinned to that
    gameweek so a "Next Gameweek" plan shows GW3's fixture, not a
    currently-in-progress GW2 one that just happens to still be unplayed) -
    falls back to whichever unplayed fixture comes soonest when no gameweek
    is given."""
    if gameweek is not None:
        candidates = [f for f in fpl.get_fixtures() if f["event"] == gameweek]
    else:
        candidates = [f for f in fpl.get_fixtures() if not f["finished"] and f["event"] is not None]
        candidates.sort(key=lambda f: f["event"])
    for f in candidates:
        if f["team_h"] == team_id or f["team_a"] == team_id:
            return f
    return None


def _fixture_label(fixture: dict, team_id: int) -> str:
    """The opponent shown under a player on a squad card."""
    teams = _teams()
    if fixture["team_h"] == team_id:
        return f"{teams.get(fixture['team_a'], {}).get('short_name', '?')} (H)"
    return f"{teams.get(fixture['team_h'], {}).get('short_name', '?')} (A)"


def _fixture_status(fixture: dict | None) -> str | None:
    """Whether a player's fixture has finished, is being played right now, or
    hasn't kicked off yet - drives the live-points badge color on the front
    end. Uses finished_provisional (true right at full-time) rather than
    finished (which FPL doesn't set until bonus points are confirmed, often a
    day or more later) so this doesn't lag the same way the gameweek-rollover
    bug did."""
    if fixture is None:
        return None
    if fixture.get("finished_provisional") or fixture.get("finished"):
        return "finished"
    if fixture.get("started"):
        return "live"
    return "not_started"


def get_players_status(element_ids: list[int]) -> dict[int, str]:
    """Current status ('a'=available, 'd'=doubtful, 'i'=injured, 's'=suspended,
    'u'=unavailable) for each given FPL element id, from the same short-TTL
    bootstrap cache used everywhere else - no extra API cost to call this."""
    players_by_id = {p["id"]: p for p in fpl.get_bootstrap()["elements"]}
    return {
        element_id: players_by_id[element_id]["status"]
        for element_id in element_ids
        if element_id in players_by_id
    }


CHIP_NAMES = {
    "wildcard": "Wildcard",
    "freehit": "Free Hit",
    "bboost": "Bench Boost",
    "3xc": "Triple Captain",
}


def get_chip_status(team_id: int) -> list[dict]:
    try:
        used = fpl.get_entry_history(team_id).get("chips", [])
    except Exception:
        used = []
    used_by_key = {c["name"]: c["event"] for c in used}
    return [
        {"key": key, "name": name, "used": key in used_by_key, "used_gameweek": used_by_key.get(key)}
        for key, name in CHIP_NAMES.items()
    ]


MAX_BANKED_FREE_TRANSFERS = 5  # current FPL rule - adjust here if FPL changes the cap


def get_free_transfers(team_id: int) -> int:
    """How many free transfers this manager has banked for their next
    transfer window, derived from their actual season history rather than
    asked of the user - FPL's API doesn't expose this count directly.

    Rule: everyone starts GW2 with 1 free transfer; each gameweek after that
    either banks (+1, up to the cap) or resets toward 0 based on how many of
    that gameweek's transfers ate into the bank. A gameweek where Wildcard or
    Free Hit was active doesn't touch the bank at all - chip transfers are
    unlimited and free regardless of how many are made."""
    try:
        history = fpl.get_entry_history(team_id)
    except Exception:
        return 1

    chip_events = {c["event"] for c in history.get("chips", []) if c["name"] in ("wildcard", "freehit")}

    free_transfers = 1
    for gw in history.get("current", []):
        if gw["event"] < 2:
            continue  # GW1 has unlimited transfers - doesn't participate in the bank
        if gw["event"] in chip_events:
            used = 0
        else:
            extra_paid = gw.get("event_transfers_cost", 0) // 4
            used = max(0, gw.get("event_transfers", 0) - extra_paid)
        free_transfers = min(MAX_BANKED_FREE_TRANSFERS, max(0, free_transfers - used) + 1)
    return free_transfers


STAT_LABELS = {
    "minutes": "Minutes played",
    "goals_scored": "Goals",
    "assists": "Assists",
    "clean_sheets": "Clean sheet",
    "goals_conceded": "Goals conceded",
    "own_goals": "Own goals",
    "penalties_saved": "Penalty saved",
    "penalties_missed": "Penalty missed",
    "yellow_cards": "Yellow card",
    "red_cards": "Red card",
    "saves": "Saves",
    "bonus": "Bonus",
    "defensive_contribution": "Defensive contribution",
}


def _explain_breakdown(explain_fixtures: list[dict]) -> list[dict]:
    """Turns FPL's own per-fixture 'explain' stat breakdown (already scored
    under its own rules) into one aggregated, human-labeled list - summed
    across fixtures for the rare double-gameweek case."""
    totals: dict[str, dict] = {}
    for fixture in explain_fixtures:
        for stat in fixture.get("stats", []):
            identifier = stat.get("identifier")
            entry = totals.setdefault(identifier, {"value": 0, "points": 0})
            entry["value"] += stat.get("value", 0)
            entry["points"] += stat.get("points", 0) + stat.get("points_modification", 0)
    breakdown = []
    for identifier, agg in totals.items():
        if agg["value"] == 0 and agg["points"] == 0:
            continue
        breakdown.append({
            "label": STAT_LABELS.get(identifier, identifier.replace("_", " ").capitalize()),
            "value": agg["value"],
            "points": agg["points"],
        })
    return breakdown


def resolve_picks(picks: list[dict], gameweek: int | None = None) -> tuple[list[dict], int]:
    """Turns raw FPL picks ([{element, multiplier, is_captain, is_vice_captain}, ...])
    into fully serialized squad entries (name, position, price, status, etc.),
    plus the total squad value in pence. Shared by get_user_team and the draft
    endpoints so both render identically.

    Pass `gameweek` to attach that gameweek's live points (updates continuously
    while its matches are played) - only meaningful for an actual locked squad,
    so draft/hypothetical picks are resolved without it."""
    players_by_id = {p["id"]: p for p in fpl.get_bootstrap()["elements"]}
    positions = _positions()
    teams = _teams()
    live_points_by_id: dict[int, int] = {}
    live_explain_by_id: dict[int, list[dict]] = {}
    if gameweek is not None:
        try:
            live = fpl.get_event_live(gameweek)
            for e in live.get("elements", []):
                live_points_by_id[e["id"]] = e["stats"]["total_points"]
                live_explain_by_id[e["id"]] = e.get("explain", [])
        except Exception:
            pass
    squad = []
    squad_value_now = 0
    for pick in picks:
        p = players_by_id.get(pick["element"])
        if not p:
            continue
        squad_value_now += p["now_cost"]
        raw_points = live_points_by_id.get(p["id"])
        fixture = _fixture_for_team(p["team"], gameweek)
        squad.append({
            "element": p["id"],
            "name": p["web_name"],
            "team_short": teams.get(p["team"], {}).get("short_name"),
            # FPL's own numeric club code (distinct from "id") - the key its
            # official crest CDN uses: resources.premierleague.com/.../t{code}.png
            "team_code": teams.get(p["team"], {}).get("code"),
            "position": positions.get(p["element_type"]),
            "price_m": p["now_cost"] / 10,
            "price_change_m": p.get("cost_change_start", 0) / 10,  # vs season start; +risen, -fallen, 0 unchanged
            "is_captain": pick["is_captain"],
            "is_vice_captain": pick["is_vice_captain"],
            "multiplier": pick["multiplier"],
            "next_fixture": _fixture_label(fixture, p["team"]) if fixture else None,
            "fixture_status": _fixture_status(fixture),  # finished | live | not_started
            "status": p["status"],  # a=available, d=doubtful, i=injured, s=suspended, u=unavailable
            "chance_of_playing_next_round": p.get("chance_of_playing_next_round"),
            "news": p.get("news") or None,
            "gw_points": raw_points,
            "gw_points_scored": raw_points * pick["multiplier"] if raw_points is not None else None,
            "gw_points_breakdown": (
                _explain_breakdown(live_explain_by_id.get(p["id"], [])) if raw_points is not None else None
            ),
        })
    return squad, squad_value_now


def _strip_replacement_chars(text: str | None) -> str | None:
    """FPL's own API occasionally returns U+FFFD in a manager/team name in
    place of a character it couldn't encode (observed with flag emoji) - the
    original character is lost upstream before we ever see it, so just drop
    the placeholder (and any resulting double space) instead of displaying a
    broken glyph."""
    if not text:
        return text
    return re.sub(r"\s*�\s*", " ", text).strip()


def get_team_preview(team_id: int) -> dict:
    """Lightweight lookup (no picks/gameweek fetch) used at signup so a user
    can confirm they typed their own FPL team ID before creating an account -
    there's no self-serve way to change it afterwards (see db.set_team_id)."""
    try:
        entry = fpl.get_entry(team_id)
    except Exception:
        return {"error": f"No FPL team found with id {team_id}"}
    return {
        "manager_name": _strip_replacement_chars(
            f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}".strip()
        ),
        "team_name": _strip_replacement_chars(entry.get("name")),
    }


def get_user_team(team_id: int, gameweek: int | None = None, fixture_gameweek: int | None = None) -> dict:
    """`gameweek` picks which locked squad to fetch (FPL only exposes a
    manager's picks once that gameweek's deadline has passed). `fixture_gameweek`
    lets a caller resolve fixtures/live-points against a *different* gameweek
    than the one the picks were fetched for - used when this same locked squad
    is being carried forward as a display/starting point for a later, not-yet-
    played gameweek (e.g. the "Next Gameweek" plan), so opponents shown match
    the gameweek actually being planned for, not the one just played."""
    try:
        entry = fpl.get_entry(team_id)
    except Exception:
        return {"error": f"No FPL team found with id {team_id}"}

    if gameweek is None:
        # FPL's picks endpoint 404s for a gameweek whose deadline hasn't
        # passed yet (it never exposes a manager's live, pre-deadline squad,
        # even to the manager themselves via this public endpoint) - so the
        # most recent *locked* gameweek is the only one available by default.
        current = fpl.get_current_event()
        gameweek = current["id"] if current else None
    if gameweek is None:
        return {"error": "Could not determine a gameweek to fetch picks for."}

    try:
        picks_data = fpl.get_entry_picks(team_id, gameweek)
    except Exception:
        return {"error": f"No picks found for team {team_id} in gameweek {gameweek}"}

    squad, squad_value_now = resolve_picks(
        picks_data.get("picks", []), gameweek=fixture_gameweek if fixture_gameweek is not None else gameweek
    )

    entry_history = picks_data.get("entry_history", {})
    # entry_history["value"] can be a stale snapshot (observed £0.5m off from the
    # real FPL site for GW1) - sum each picked player's current price instead,
    # which matches what the official site's Finance page actually shows.
    squad_value_m = squad_value_now / 10
    bank_m = entry_history.get("bank", 0) / 10

    # entry_history["points"] lags behind actual play (FPL doesn't finalize it
    # until the gameweek is fully confirmed, bonus points included), and
    # entry["summary_event_points"] turned out not to update on the same live
    # cadence as the per-player scores shown on each squad card either - so
    # sum each player's own already-live gw_points_scored instead, which is
    # the exact same event/live-backed number the squad cards already show.
    # Only falls back to FPL's own aggregate if the live per-player fetch
    # failed entirely (every player's gw_points_scored came back None).
    live_scores = [p["gw_points_scored"] for p in squad if p.get("gw_points_scored") is not None]
    gameweek_points = sum(live_scores) if live_scores else entry.get("summary_event_points")

    return {
        "manager_name": _strip_replacement_chars(
            f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}".strip()
        ),
        "team_name": _strip_replacement_chars(entry.get("name")),
        "overall_rank": entry.get("summary_overall_rank"),
        "overall_points": entry.get("summary_overall_points"),
        "gameweek": gameweek,
        "gameweek_points": gameweek_points,
        "squad_value_m": squad_value_m,
        "bank_m": bank_m,
        "total_budget_m": round(squad_value_m + bank_m, 1),
        "squad": squad,
        "active_chip": picks_data.get("active_chip"),
        "chips": get_chip_status(team_id),
    }


def get_next_gameweek_squad(team_id: int, user_id: int | None = None) -> dict:
    """The user's own squad as planned for the upcoming, not-yet-played
    gameweek - their saved draft if they have one, else their last locked
    squad carried forward unchanged. Chat advice should always use this (not
    get_user_team) for the logged-in user's own team, so it's never grading a
    gameweek that's already been played."""
    try:
        entry = fpl.get_entry(team_id)
    except Exception:
        return {"error": f"No FPL team found with id {team_id}"}

    next_gw = get_next_deadline()
    if "error" in next_gw:
        return next_gw
    gameweek = next_gw["id"]

    saved = db.get_draft(user_id) if user_id is not None else None
    # A draft saved for an earlier gameweek is stale once that gameweek has
    # moved on (real transfers may have happened on the official site since) -
    # only trust it as "the plan" if it's still for the current next gameweek.
    if saved and saved["team_id"] == str(team_id) and saved["gameweek"] == gameweek:
        squad, squad_value_now = resolve_picks(saved["picks"], gameweek=gameweek)
        squad_value_m = squad_value_now / 10
        bank_m = saved["bank_m"]
        total_budget_m = saved["total_budget_m"]
        is_saved_plan = True
    else:
        live = get_user_team(team_id, fixture_gameweek=gameweek)
        if "error" in live:
            return live
        squad = live["squad"]
        squad_value_m = live["squad_value_m"]
        bank_m = live["bank_m"]
        total_budget_m = live["total_budget_m"]
        is_saved_plan = False

    # Strip any live-gameweek points carried over from the fallback (last
    # locked squad) - they're from a gameweek that's already been played and
    # would be misleading attached to a not-yet-played plan.
    squad = [
        {k: v for k, v in p.items() if k not in ("gw_points", "gw_points_scored", "gw_points_breakdown")}
        for p in squad
    ]

    return {
        "manager_name": _strip_replacement_chars(
            f"{entry.get('player_first_name', '')} {entry.get('player_last_name', '')}".strip()
        ),
        "team_name": _strip_replacement_chars(entry.get("name")),
        "overall_rank": entry.get("summary_overall_rank"),
        "overall_points": entry.get("summary_overall_points"),
        "gameweek": gameweek,
        "is_saved_plan": is_saved_plan,
        "free_transfers": get_free_transfers(team_id),
        "squad_value_m": squad_value_m,
        "bank_m": bank_m,
        "total_budget_m": total_budget_m,
        "squad": squad,
        "chips": get_chip_status(team_id),
    }


def get_user_rank_history(team_id: int) -> dict:
    try:
        history = fpl.get_entry_history(team_id)
    except Exception:
        return {"error": f"No FPL team found with id {team_id}"}

    season = [
        {
            "gameweek": gw["event"],
            "points": gw["points"],
            "total_points": gw["total_points"],
            "overall_rank": gw["overall_rank"],
            "value_m": gw["value"] / 10,
            "bank_m": gw["bank"] / 10,
        }
        for gw in history.get("current", [])
    ]
    return {"team_id": team_id, "season": season}


def get_league_standings(league_id: int) -> dict:
    try:
        data = fpl.get_league_standings(league_id)
    except Exception:
        return {"error": f"No league found with id {league_id}"}

    league = data.get("league", {})
    results = data.get("standings", {}).get("results", [])
    return {
        "league_name": league.get("name"),
        "standings": [
            {
                "rank": r["rank"],
                "entry_name": r["entry_name"],
                "player_name": r["player_name"],
                "total": r["total"],
                "event_total": r["event_total"],
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# Claude tool schemas + dispatch
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    # Server-side (Anthropic-hosted) tool, not dispatched via _DISPATCH below -
    # lets the assistant look up current FPL-relevant news (press conference
    # team talk, expected lineups, price rise/fall news, injury updates not
    # yet reflected in the bootstrap-static "news" field) that the FPL API
    # itself doesn't carry. Capped at 3 searches/turn and restricted to
    # reputable football/FPL sources to keep results relevant and reliable.
    {
        "type": "web_search_20260209",
        "name": "web_search",
        "max_uses": 3,
        "allowed_domains": [
            "fantasy.premierleague.com",
            "premierleague.com",
            "skysports.com",
            "fantasyfootballscout.co.uk",
            "espn.com",
        ],
    },
    {
        "name": "search_players",
        "description": "Search for FPL players by name (fuzzy match) and get their current stats: price, form, points, ownership, injury status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Player name or partial name"},
                "limit": {"type": "integer", "description": "Max results, default 5"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "compare_players",
        "description": "Compare multiple players side by side on price, form, points, ownership, and underlying stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "names": {"type": "array", "items": {"type": "string"}, "description": "Player names to compare"},
            },
            "required": ["names"],
        },
    },
    {
        "name": "get_top_performers",
        "description": "Get the top N players by a given stat, optionally filtered by position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "string", "description": "GKP, DEF, MID, FWD, or all (default all)"},
                "metric": {
                    "type": "string",
                    "description": "Stat to rank by: total_points, form, goals_scored, assists, expected_goals, expected_assists, ict_index, bonus, now_cost (default total_points)",
                },
                "limit": {"type": "integer", "description": "Number of players to return, default 5"},
            },
            "required": [],
        },
    },
    {
        "name": "get_fixture_difficulty",
        "description": "Get a club's upcoming fixtures with FPL's Fixture Difficulty Rating (1=easiest, 5=hardest), useful for transfer and chip planning.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_name": {"type": "string", "description": "Club name, e.g. 'Arsenal' or 'Man City'"},
                "num_gameweeks": {"type": "integer", "description": "How many upcoming gameweeks to look at, default 5"},
            },
            "required": ["team_name"],
        },
    },
    {
        "name": "get_gameweek_status",
        "description": "Get the current/next FPL gameweek number and transfer deadline.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_my_next_gameweek_squad",
        "description": (
            "Get the CURRENT USER's own squad as planned for the upcoming, not-yet-played gameweek "
            "(their saved draft if they have one, else their last squad carried forward). The actual "
            "captain/transfer/bench verdict always comes from this, never from a gameweek already "
            "played - but pair it with get_user_team on the same team_id when a look back at their last "
            "gameweek's actual result would strengthen that verdict."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "integer", "description": "The user's own FPL team/entry ID"},
            },
            "required": ["team_id"],
        },
    },
    {
        "name": "get_user_team",
        "description": (
            "Get a specific FPL manager's squad, captain, and points for a gameweek that has already "
            "been played, given their public team ID. Use this for another manager (e.g. a league rival), "
            "or alongside get_my_next_gameweek_squad to see how the current user's own last gameweek "
            "actually went - but the current user's own forward-looking verdict always comes from "
            "get_my_next_gameweek_squad, not this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "integer", "description": "The manager's FPL team/entry ID"},
                "gameweek": {"type": "integer", "description": "Gameweek number; defaults to the last played gameweek"},
            },
            "required": ["team_id"],
        },
    },
    {
        "name": "get_user_rank_history",
        "description": "Get a manager's overall rank and points progression across the season, given their public team ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "team_id": {"type": "integer", "description": "The manager's FPL team/entry ID"},
            },
            "required": ["team_id"],
        },
    },
    {
        "name": "get_league_standings",
        "description": "Get the standings table for a classic FPL mini-league, given its league ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "league_id": {"type": "integer", "description": "The classic mini-league ID"},
            },
            "required": ["league_id"],
        },
    },
]

_DISPATCH = {
    "search_players": search_players,
    "compare_players": compare_players,
    "get_top_performers": get_top_performers,
    "get_fixture_difficulty": get_fixture_difficulty,
    "get_gameweek_status": get_gameweek_status,
    "get_user_team": get_user_team,
    "get_my_next_gameweek_squad": get_next_gameweek_squad,
    "get_user_rank_history": get_user_rank_history,
    "get_league_standings": get_league_standings,
}

# Tools that need the logged-in user's own id (not something the model can
# supply itself) get it injected here rather than exposed as a tool_input field.
_NEEDS_USER_ID = {"get_my_next_gameweek_squad"}


def call_tool(name: str, tool_input: dict, user_id: int | None = None) -> dict:
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool '{name}'"}
    try:
        if name in _NEEDS_USER_ID:
            return fn(**tool_input, user_id=user_id)
        return fn(**tool_input)
    except Exception as exc:  # keep the agent loop alive on bad tool args
        return {"error": str(exc)}
