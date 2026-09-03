# match_state.py
# Purpose: Tracks the live map/match timer and lists connected players via RCON status.

import re
import threading
import time

from .envfile import read_env, write_env
from .maps import list_maps
from .rcon import RconError, rcon_command

PLAYER_RE = re.compile(
    r"^\s*(?P<id>\d+)\s+(?P<time>\S+)\s+(?P<ping>\d+)\s+\d+\s+\S+\s+\d+\s+(?:\S+\s+)?'(?P<name>.*)'\s*$"
)
SPAWNGROUP_MAP_RE = re.compile(r"spawngroup\(\s*1\)\s*:\s*SV:\s*\[1:\s*(\S+?)\s*\|")

_match_lock = threading.Lock()
_match_state = {"map": None, "started_at": None}


def _update_match_state(live_map):
    if not live_map:
        return
    changed = False
    with _match_lock:
        if live_map != _match_state["map"]:
            _match_state["map"] = live_map
            _match_state["started_at"] = time.time()
            changed = True
    if not changed:
        return
    maps = list_maps()
    if live_map not in maps["core"] and live_map not in maps["extra"]:
        return
    if read_env().get("CS2_STARTMAP", "") != live_map:
        write_env({"CS2_STARTMAP": live_map})


def _reset_match_state():
    with _match_lock:
        _match_state["map"] = None
        _match_state["started_at"] = None


def match_elapsed_seconds():
    with _match_lock:
        started = _match_state["started_at"]
    return None if started is None else int(time.time() - started)


def list_players():
    try:
        output = rcon_command("status")
    except (RconError, OSError):
        return []
    map_match = SPAWNGROUP_MAP_RE.search(output)
    if map_match:
        _update_match_state(map_match.group(1))
    players = []
    for line in output.splitlines():
        m = PLAYER_RE.match(line)
        if m:
            players.append(
                {
                    "id": int(m.group("id")),
                    "name": m.group("name"),
                    "ping": int(m.group("ping")),
                    "bot": m.group("time").strip().upper() == "BOT",
                }
            )
    return players


def real_players():
    """Connected players, excluding bots (status shows 'BOT' in the connect-time field, not the name)."""
    return [p for p in list_players() if not p["bot"]]
