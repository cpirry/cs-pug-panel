# lobby.py
# Purpose: In-memory lobby create/join/leave state, keyed by a short shareable code.

import secrets
import string
import threading

CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I - easy to read aloud
CODE_LENGTH = 5

PASSWORD_ALPHABET = string.ascii_letters + string.digits
PASSWORD_LENGTH = 10

_lock = threading.Lock()
_lobbies = {}  # code -> {"host": steam_id, "members": [steam_id, ...], "state": "waiting"}


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
        if not lobby["members"]:
            del _lobbies[code]
        elif lobby["host"] == steam_id:
            lobby["host"] = lobby["members"][0]
        return


def create_lobby(host_steam_id):
    with _lock:
        _leave_locked(host_steam_id)
        code = _generate_code()
        _lobbies[code] = {"host": host_steam_id, "members": [host_steam_id], "state": "waiting"}
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


def generate_match_password():
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def start_lobby(code, steam_id, connect):
    """Marks the lobby as in_match and stores its connect info. Only the host may start it."""
    with _lock:
        lobby = _lobbies.get(code)
        if lobby is None or lobby["host"] != steam_id:
            return False
        lobby["state"] = "in_match"
        lobby["connect"] = connect
        return True


def reset_lobby(code, steam_id):
    """Returns the lobby to waiting (clearing its connect info) so the same group can start another
    match without re-sharing the code. Only the host may reset it."""
    with _lock:
        lobby = _lobbies.get(code)
        if lobby is None or lobby["host"] != steam_id:
            return False
        lobby["state"] = "waiting"
        lobby.pop("connect", None)
        return True
