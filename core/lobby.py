# lobby.py
# Purpose: In-memory lobby create/join/leave/ready state, keyed by a short shareable code.

import secrets
import string
import threading

CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I - easy to read aloud
CODE_LENGTH = 5

PASSWORD_ALPHABET = string.ascii_letters + string.digits
PASSWORD_LENGTH = 10

_lock = threading.Lock()
_lobbies = {}  # code -> {"host": steam_id, "members": [steam_id, ...], "state": "waiting",
               #          "ready": {steam_id, ...}, "teams": {steam_id: "t" | "ct"}}


def _assign_team(lobby):
    teams = lobby.setdefault("teams", {})
    t_count = sum(1 for v in teams.values() if v == "t")
    ct_count = sum(1 for v in teams.values() if v == "ct")
    return "t" if t_count <= ct_count else "ct"


def _generate_code():
    while True:
        code = "".join(secrets.choice(CODE_CHARS) for _ in range(CODE_LENGTH))
        if code not in _lobbies:
            return code


def _leave_locked(steam_id):
    for code, lobby in list(_lobbies.items()):
        if steam_id not in lobby["members"]:
            continue
        lobby["members"].remove(steam_id)
        lobby["ready"].discard(steam_id)
        lobby.get("teams", {}).pop(steam_id, None)
        if not lobby["members"]:
            del _lobbies[code]
        elif lobby["host"] == steam_id:
            lobby["host"] = lobby["members"][0]
        return


def create_lobby(host_steam_id):
    with _lock:
        _leave_locked(host_steam_id)
        code = _generate_code()
        _lobbies[code] = {
            "host": host_steam_id,
            "members": [host_steam_id],
            "state": "waiting",
            "ready": set(),
            "teams": {host_steam_id: "t"},
        }
        return code


def join_lobby(code, steam_id):
    code = code.strip().upper()
    with _lock:
        lobby = _lobbies.get(code)
        if lobby is None:
            return None
        if steam_id in lobby["members"]:
            return code
        if lobby["state"] != "waiting":
            return None
        _leave_locked(steam_id)
        lobby = _lobbies.get(code)
        if lobby is None:
            return None
        lobby["members"].append(steam_id)
        lobby.setdefault("teams", {})[steam_id] = _assign_team(lobby)
        return code


def leave_lobby(steam_id):
    with _lock:
        _leave_locked(steam_id)


def find_lobby_for(steam_id):
    with _lock:
        for code, lobby in _lobbies.items():
            if steam_id in lobby["members"]:
                return code, dict(lobby)
    return None, None


def toggle_ready(steam_id):
    with _lock:
        for code, lobby in _lobbies.items():
            if steam_id in lobby["members"]:
                if steam_id in lobby["ready"]:
                    lobby["ready"].discard(steam_id)
                else:
                    lobby["ready"].add(steam_id)
                return code
    return None


def move_member(actor_steam_id, steam_id, team, swap_with=None):
    """Moves steam_id onto the given team ("t"/"ct"). If swap_with is set, that member (who must
    already be on the target team) is moved onto steam_id's old team in exchange. Only the member
    themself or the lobby host may move a member, and only while the lobby is waiting."""
    if team not in ("t", "ct"):
        return False
    with _lock:
        lobby = None
        for candidate in _lobbies.values():
            if steam_id in candidate["members"]:
                lobby = candidate
                break
        if lobby is None:
            return False
        if actor_steam_id != steam_id and actor_steam_id != lobby["host"]:
            return False
        if lobby["state"] != "waiting":
            return False
        teams = lobby.setdefault("teams", {})
        if swap_with:
            if swap_with not in lobby["members"] or swap_with == steam_id:
                return False
            if teams.get(swap_with, "t") != team:
                return False
            teams[swap_with] = teams.get(steam_id, "t")
        teams[steam_id] = team
        return True


def kick_member(actor_steam_id, steam_id):
    """Removes steam_id from their lobby. Only the host may kick, and only someone else."""
    if steam_id == actor_steam_id:
        return False
    with _lock:
        lobby = None
        for candidate in _lobbies.values():
            if steam_id in candidate["members"]:
                lobby = candidate
                break
        if lobby is None or lobby["host"] != actor_steam_id:
            return False
        _leave_locked(steam_id)
        return True


def generate_match_password():
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def start_lobby(code, steam_id, connect):
    """Marks the lobby as in_match and stores its connect info. Only the host may start it, and
    only once every member has readied up."""
    with _lock:
        lobby = _lobbies.get(code)
        if lobby is None or lobby["host"] != steam_id:
            return False
        if not lobby["members"] or len(lobby["ready"]) != len(lobby["members"]):
            return False
        lobby["state"] = "in_match"
        lobby["connect"] = connect
        return True


def reset_lobby(code, steam_id):
    """Returns the lobby to waiting (clearing its connect info and everyone's ready state) so the
    same group can start another match without re-sharing the code. Only the host may reset it."""
    with _lock:
        lobby = _lobbies.get(code)
        if lobby is None or lobby["host"] != steam_id:
            return False
        lobby["state"] = "waiting"
        lobby["ready"] = set()
        lobby.pop("connect", None)
        return True
