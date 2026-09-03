# steam_auth.py
# Purpose: Allow login with Steam OIDC.

import json
import os
import secrets
import threading
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
STEAM_ID_PREFIX = "https://steamcommunity.com/openid/id/"
STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "")

SESSION_COOKIE = "cs2panel_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_sessions_lock = threading.Lock()
_sessions = {}  # token -> steam_id64


def build_login_url(return_to, realm):
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_URL}?{urlencode(params)}"


def verify_callback(params):
    """Verifies an OpenID callback from Steam and returns the SteamID64, or None if invalid."""
    claimed_id = params.get("openid.claimed_id", "")
    if not claimed_id.startswith(STEAM_ID_PREFIX):
        return None
    steam_id = claimed_id[len(STEAM_ID_PREFIX):]
    if not steam_id.isdigit():
        return None

    check_params = dict(params)
    check_params["openid.mode"] = "check_authentication"
    body = urlencode(check_params).encode()
    req = Request(STEAM_OPENID_URL, data=body, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            result = resp.read().decode()
    except (URLError, OSError, TimeoutError):
        return None
    if "is_valid:true" not in result:
        return None
    return steam_id


def create_session(steam_id):
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = steam_id
    return token


def session_steam_id(token):
    if not token:
        return None
    with _sessions_lock:
        return _sessions.get(token)


def destroy_session(token):
    with _sessions_lock:
        _sessions.pop(token, None)


def fetch_player_summary(steam_id):
    """Returns {personaName, avatar} for steam_id, or None if no API key is configured or the lookup fails."""
    if not STEAM_API_KEY:
        return None
    params = {"key": STEAM_API_KEY, "steamids": steam_id}
    url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?{urlencode(params)}"
    try:
        with urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read())
    except (URLError, OSError, TimeoutError, json.JSONDecodeError):
        return None
    players = payload.get("response", {}).get("players", [])
    if not players:
        return None
    p = players[0]
    return {"personaName": p.get("personaname", steam_id), "avatar": p.get("avatar", "")}
