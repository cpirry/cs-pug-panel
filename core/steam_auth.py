# steam_auth.py
# Purpose: Allow login with Steam OIDC.

import json
import os
import secrets
import threading
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .constants import STEAM_ALLOWLIST, STEAM_ALLOWLIST_DISABLED

STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
STEAM_ID_PREFIX = "https://steamcommunity.com/openid/id/"
STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "")

SESSION_COOKIE = "cs2panel_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_sessions_lock = threading.Lock()
_sessions = {}  # token -> steam_id64

SUMMARY_CACHE_TTL = 300  # seconds - display names/avatars rarely change mid-session

_summary_cache_lock = threading.Lock()
_summary_cache = {}  # steam_id -> (expires_at, {personaName, avatar})


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


def is_allowed(steam_id):
    return STEAM_ALLOWLIST_DISABLED or steam_id in STEAM_ALLOWLIST


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


def fetch_player_summaries(steam_ids):
    """Returns {steam_id: {personaName, avatar}} for the given steam_ids, using a short-lived
    cache so frequent polling doesn't hammer Steam's API. Missing/failed lookups are simply absent."""
    steam_ids = [s for s in dict.fromkeys(steam_ids) if s]
    if not steam_ids:
        return {}

    now = time.monotonic()
    results = {}
    to_fetch = []
    with _summary_cache_lock:
        for steam_id in steam_ids:
            cached = _summary_cache.get(steam_id)
            if cached and cached[0] > now:
                results[steam_id] = cached[1]
            else:
                to_fetch.append(steam_id)

    if not to_fetch or not STEAM_API_KEY:
        return results

    params = {"key": STEAM_API_KEY, "steamids": ",".join(to_fetch)}
    url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?{urlencode(params)}"
    try:
        with urlopen(url, timeout=10) as resp:
            payload = json.loads(resp.read())
    except (URLError, OSError, TimeoutError, json.JSONDecodeError):
        return results
    players = payload.get("response", {}).get("players", [])
    with _summary_cache_lock:
        for p in players:
            summary = {"personaName": p.get("personaname", p["steamid"]), "avatar": p.get("avatar", "")}
            _summary_cache[p["steamid"]] = (now + SUMMARY_CACHE_TTL, summary)
            results[p["steamid"]] = summary
    return results


def fetch_player_summary(steam_id):
    """Returns {personaName, avatar} for steam_id, or None if no API key is configured or the lookup fails."""
    return fetch_player_summaries([steam_id]).get(steam_id)
