# match_log_parser.py
# Purpose: Parses a single CS2 server log file into one match's results (score + per-player
# kills/deaths/assists/headshots/damage dealt/team). K/D, ADR, and headshot % are deliberately
# NOT computed here - they're derived from these raw counts at serving time (see
# match_history.py), so they can't drift out of sync with the numbers they're based on.
#
# Server logs are noisier than one clean "a match happened" record: the engine fires an
# initial Match_Start the instant a map loads (before anyone's connected), and - because this
# server runs with mp_match_end_changelevel true - fires another Match_Start/Game_Commencing
# pair right after a match ends, when the map auto-reloads into a fresh warmup. So "the real
# match" is the *last* Match_Start that actually has rounds played after it, up to the next
# restart (or end of file). This boundary logic was derived from, and verified against, real
# production log files - not guessed.

import re
from datetime import datetime

LINE_RE = re.compile(r"^L (\d\d/\d\d/\d\d\d\d) - (\d\d:\d\d:\d\d): (.*)$")
PLAYER_RE = r'"([^<]+)<(\d+)><([^>]*)><([A-Za-z]*)>"'
KILL_RE = re.compile(
    PLAYER_RE + r" \[[-\d ]+\] killed " + PLAYER_RE + r' \[[-\d ]+\] with "(\w+)"(\s*\(headshot\))?'
)
ASSIST_RE = re.compile(PLAYER_RE + r" assisted killing " + PLAYER_RE)
# Raw, as-logged damage - not capped/normalized to the target's remaining health the way
# HLTV-style ADR sometimes is (confirmed against real logs: a hit that overkills a near-dead
# player still logs its full raw weapon damage, not the smaller amount actually "used").
ATTACK_RE = re.compile(
    PLAYER_RE + r' \[[-\d ]+\] attacked ' + PLAYER_RE + r' \[[-\d ]+\] with "[^"]*" \(damage "(\d+)"\)'
)
ROUNDEND_RE = re.compile(r'Team "(\w+)" triggered "(SFUI_Notice_\w+)" \(CT "(\d+)"\) \(T "(\d+)"\)')
MATCHSTART_RE = re.compile(r'World triggered "Match_Start" on "([\w_]+)"')


def _is_real_player(steam_id):
    return steam_id.startswith("[U:1:")


def _parse_events(lines):
    events = []
    for line in lines:
        m = LINE_RE.match(line.rstrip("\n"))
        if not m:
            continue
        date_str, time_str, rest = m.groups()
        ts = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H:%M:%S")
        if "Match_Start" in rest:
            mm = MATCHSTART_RE.search(rest)
            if mm:
                events.append((ts, "match_start", mm.group(1)))
        elif "Game_Commencing" in rest:
            events.append((ts, "game_commencing", None))
        elif ROUNDEND_RE.search(rest):
            events.append((ts, "round_end", ROUNDEND_RE.search(rest).groups()))
        elif " killed " in rest:
            km = KILL_RE.search(rest)
            if km:
                events.append((ts, "kill", km.groups()))
        elif " assisted killing " in rest:
            am = ASSIST_RE.search(rest)
            if am:
                events.append((ts, "assist", am.groups()))
        elif " attacked " in rest:
            atm = ATTACK_RE.search(rest)
            if atm:
                events.append((ts, "attack", atm.groups()))
    return events


def _find_real_match_window(events):
    """Returns (start_idx, end_idx) bounding the real match within `events`, or None if no
    Match_Start in this file ever had a round played after it."""
    match_start_idxs = [i for i, e in enumerate(events) if e[1] == "match_start"]
    real_start_idx = None
    for idx in match_start_idxs:
        j = idx + 1
        has_round = False
        while j < len(events) and events[j][1] != "match_start":
            if events[j][1] == "round_end":
                has_round = True
            j += 1
        if has_round:
            real_start_idx = idx  # keep scanning for the LAST one that qualifies

    if real_start_idx is None:
        return None

    end_idx = len(events)
    for i in range(real_start_idx + 1, len(events)):
        if events[i][1] == "game_commencing":
            end_idx = i
            break
    return real_start_idx, end_idx


def parse_log_file(path):
    """Parses one CS2 server log file into a single match's results, or returns None if the
    file never had a real match played in it (e.g. a boot with no players, or a false-start
    that got abandoned before any round completed)."""
    with open(path, errors="replace") as f:
        lines = f.readlines()

    events = _parse_events(lines)
    window = _find_real_match_window(events)
    if window is None:
        return None
    start_idx, end_idx = window
    match_events = events[start_idx:end_idx]

    map_name = events[start_idx][2]
    kills = {}
    deaths = {}
    assists = {}
    headshots = {}
    damage_dealt = {}
    steam_ids = {}
    team_counts = {}
    last_score = (0, 0)

    def bump(d, name, amount=1):
        d[name] = d.get(name, 0) + amount

    for ts, kind, data in match_events:
        if kind == "kill":
            a_name, _, a_steam, a_team, v_name, _, v_steam, v_team, weapon, hs = data
            if a_name == v_name:
                continue
            if _is_real_player(a_steam):
                bump(kills, a_name)
                steam_ids[a_name] = a_steam
                if hs:
                    bump(headshots, a_name)
                if a_team in ("CT", "TERRORIST"):
                    team_counts.setdefault(a_name, {}).setdefault(a_team, 0)
                    team_counts[a_name][a_team] += 1
            if _is_real_player(v_steam):
                bump(deaths, v_name)
                steam_ids[v_name] = v_steam
                if v_team in ("CT", "TERRORIST"):
                    team_counts.setdefault(v_name, {}).setdefault(v_team, 0)
                    team_counts[v_name][v_team] += 1
        elif kind == "assist":
            a_name, _, a_steam, a_team, v_name, _, v_steam, v_team = data
            if _is_real_player(a_steam):
                bump(assists, a_name)
                steam_ids[a_name] = a_steam
        elif kind == "attack":
            a_name, _, a_steam, a_team, v_name, _, v_steam, v_team, dmg = data
            if a_name == v_name:
                continue  # fall damage logs as a player "attacking" themselves
            # Matches the kill-crediting rule above (real attacker, no check on the victim's
            # team) rather than inventing a different, inconsistent filter just for damage.
            if _is_real_player(a_steam):
                bump(damage_dealt, a_name, int(dmg))
                steam_ids[a_name] = a_steam
        elif kind == "round_end":
            _, _, ct_score, t_score = data
            last_score = (int(ct_score), int(t_score))

    names = sorted(steam_ids.keys())
    players = []
    for name in names:
        counts = team_counts.get(name, {})
        team = "CT" if counts.get("CT", 0) >= counts.get("TERRORIST", 0) else "T"
        players.append(
            {
                "steam_id": steam_ids[name],
                "name": name,
                "team": team,
                "kills": kills.get(name, 0),
                "deaths": deaths.get(name, 0),
                "assists": assists.get(name, 0),
                "headshots": headshots.get(name, 0),
                "damage_dealt": damage_dealt.get(name, 0),
            }
        )

    return {
        "map": map_name,
        "score_ct": last_score[0],
        "score_t": last_score[1],
        "started_at": match_events[0][0],
        "ended_at": match_events[-1][0],
        "players": players,
    }
