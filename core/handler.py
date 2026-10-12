# handler.py
# Purpose: HTTP request routing (GET/POST) for the panel's API and static files.

import json
import os
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urlparse

from .cfg_sync import (
    read_team_names,
    write_fake_rcon_password,
    write_match_format,
    write_team_names,
)
from .constants import (
    COMPOSE_FILE,
    CONTAINER,
    CS2_APP_ID,
    CS2_CONNECT_HOST,
    ENV_PATH,
    GAME_MODE_MODS,
    GAMEMODE_CFG_RE,
    MAP_IMAGES_DIR,
    MIME,
    PROJECT_NAME,
    SERVICE,
    SMALL_TEAM_DEFUSAL_CFG,
    SMALL_TEAM_RUSH_CFG,
    STATIC_DIR,
)
from .envfile import read_env, write_env
from .firewall import request_apply as request_firewall_apply
from .gamemode_cfg import (
    delete_preset,
    list_gamemode_configs,
    list_presets,
    read_gamemode_cfg,
    read_preset,
    resolve_gamemode_cfg,
    save_preset,
    write_gamemode_cfg,
)
from .idle import mark_activity
from .lobby import (
    create_lobby,
    delete_lobby,
    find_lobby_for,
    generate_match_password,
    join_lobby,
    kick_member,
    leave_lobby,
    move_member,
    reset_lobby,
    set_selected_map,
    start_lobby,
    toggle_ready,
)
from .maps import fetch_workshop_details, parse_workshop_id, save_workshop_map
from .match_history import (
    demo_download_name,
    get_match,
    get_match_file_path,
    get_player_matches,
    get_player_stats,
    list_matches,
)
from .match_state import _reset_match_state, list_players, match_elapsed_seconds
from .mods import toggle_mod, write_game_mode
from .proc_status import container_status, server_uptime_seconds, tail_console, tail_logs
from .rcon import RconError, rcon_command
from .state import build_state
from .steam_auth import (
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    build_login_url,
    create_session,
    destroy_session,
    fetch_player_summaries,
    fetch_player_summary,
    is_allowed,
    session_steam_id,
    verify_callback,
)
from .util import run, sanitize_cvar_string


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, payload, status=200, headers=None):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path, root=STATIC_DIR):
        if path == "/":
            path = "/index.html"
        full = os.path.normpath(os.path.join(root, path.lstrip("/")))
        if not full.startswith(root) or not os.path.isfile(full):
            self.send_response(404)
            self.end_headers()
            return
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file_download(self, full_path, download_name):
        if not os.path.isfile(full_path):
            self.send_response(404)
            self.end_headers()
            return
        size = os.path.getsize(full_path)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        with open(full_path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _request_origin(self):
        proto = self.headers.get("X-Forwarded-Proto", "http")
        host = self.headers.get("Host", "localhost")
        return f"{proto}://{host}"

    def _session_token(self):
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _session_cookie_header(self, token=None, clear=False):
        if clear:
            return f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
        return f"{SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_MAX_AGE}; HttpOnly; SameSite=Lax"

    def _require_login(self):
        steam_id = session_steam_id(self._session_token())
        if not steam_id:
            self._send_json({"error": "not logged in"}, 401)
            return None
        return steam_id

    def _auth_info(self, steam_id):
        if not steam_id:
            return {"loggedIn": False}
        summary = fetch_player_summary(steam_id) or {}
        return {
            "loggedIn": True,
            "steamId": steam_id,
            "displayName": summary.get("personaName", steam_id),
            "avatar": summary.get("avatar", ""),
            "avatarFull": summary.get("avatarFull", ""),
        }

    def _lobby_info(self, steam_id):
        if not steam_id:
            return None
        code, lobby = find_lobby_for(steam_id)
        if lobby is None:
            return None
        summaries = fetch_player_summaries(lobby["members"])
        ready_set = lobby.get("ready", set())
        teams = lobby.get("teams", {})
        members = [
            {
                "steamId": member_id,
                "displayName": summaries.get(member_id, {}).get("personaName", member_id),
                "avatar": summaries.get(member_id, {}).get("avatar", ""),
                "ready": member_id in ready_set,
                "team": teams.get(member_id, "t"),
            }
            for member_id in lobby["members"]
        ]
        return {
            "code": code,
            "host": lobby["host"],
            "members": members,
            "state": lobby["state"],
            "connect": lobby.get("connect"),
            "allReady": bool(lobby["members"]) and len(ready_set) == len(lobby["members"]),
            "selectedMap": lobby.get("selectedMap", ""),
            "selectedMapSource": lobby.get("selectedMapSource", "local"),
            "selectedMapIsRandom": lobby.get("selectedMapIsRandom", False),
        }

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            steam_id = session_steam_id(self._session_token())
            if steam_id:
                _, lobby = find_lobby_for(steam_id)
                if lobby is not None:
                    self.send_response(302)
                    self.send_header("Location", "/app.html")
                    self.end_headers()
                    return
            self._send_static("/")
            return
        if parsed.path == "/app.html":
            steam_id = session_steam_id(self._session_token())
            in_lobby = steam_id and find_lobby_for(steam_id)[1] is not None
            if not in_lobby:
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            self._send_static(parsed.path)
            return
        if parsed.path == "/match.html":
            # Match history (and its /api/matches backing) is viewable by any logged-in
            # player regardless of whether they're currently in a lobby - unlike /app.html,
            # which is the in-lobby app shell and genuinely needs one.
            if session_steam_id(self._session_token()) is None:
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()
                return
            self._send_static(parsed.path)
            return
        if parsed.path == "/api/state":
            steam_id = self._require_login()
            if steam_id is None:
                return
            state = build_state()
            state["auth"] = self._auth_info(steam_id)
            state["lobby"] = self._lobby_info(steam_id)
            self._send_json(state)
            return
        if parsed.path == "/auth/steam/login":
            origin = self._request_origin()
            login_url = build_login_url(return_to=f"{origin}/auth/steam/callback", realm=origin)
            self.send_response(302)
            self.send_header("Location", login_url)
            self.end_headers()
            return
        if parsed.path == "/auth/steam/callback":
            params = {k: v[0] for k, v in parse_qs(parsed.query).items() if k.startswith("openid.")}
            steam_id = verify_callback(params)
            if steam_id and not is_allowed(steam_id):
                steam_id = None
            self.send_response(302)
            self.send_header("Location", "/")
            if steam_id:
                token = create_session(steam_id)
                self.send_header("Set-Cookie", self._session_cookie_header(token=token))
            self.end_headers()
            return
        if parsed.path == "/api/tail":
            if self._require_login() is None:
                return
            qs = parse_qs(parsed.query)
            n = int(qs.get("n", ["200"])[0])
            status = container_status()
            running = status == "running"
            if running:
                players = list_players()
            else:
                players = []
                _reset_match_state()
            self._send_json(
                {
                    "running": running,
                    "status": status,
                    "console": tail_console(n),
                    "logs": tail_logs(n),
                    "players": players,
                    "serverUptime": server_uptime_seconds() if running else None,
                    "matchTime": match_elapsed_seconds() if running else None,
                }
            )
            return
        if parsed.path.startswith("/map-images/"):
            self._send_static(parsed.path[len("/map-images/") :], MAP_IMAGES_DIR)
            return
        if parsed.path == "/api/config":
            if self._require_login() is None:
                return
            qs = parse_qs(parsed.query)
            file = resolve_gamemode_cfg(qs.get("file", [""])[0])
            if file is None:
                self._send_json({"error": "no gamemode configs found"}, 404)
                return
            self._send_json(
                {
                    "file": file,
                    "files": list_gamemode_configs(),
                    "content": read_gamemode_cfg(file),
                    "presets": list_presets(file),
                }
            )
            return
        if parsed.path.startswith("/api/config/presets/"):
            if self._require_login() is None:
                return
            rest = unquote(parsed.path[len("/api/config/presets/") :])
            file, _, name = rest.partition("/")
            if not GAMEMODE_CFG_RE.match(file) or file not in list_gamemode_configs():
                self._send_json({"error": "invalid config file"}, 400)
                return
            content = read_preset(file, name)
            if content is None:
                self._send_json({"error": "preset not found"}, 404)
                return
            self._send_json({"content": content})
            return
        if parsed.path == "/api/matches":
            if self._require_login() is None:
                return
            self._send_json({"matches": list_matches()})
            return
        if parsed.path == "/api/stats/me":
            steam_id = self._require_login()
            if steam_id is None:
                return
            self._send_json(get_player_stats(steam_id))
            return
        if parsed.path == "/api/matches/mine":
            steam_id = self._require_login()
            if steam_id is None:
                return
            self._send_json({"matches": get_player_matches(steam_id)})
            return
        if parsed.path.startswith("/api/matches/"):
            steam_id = self._require_login()
            if steam_id is None:
                return
            rest = unquote(parsed.path[len("/api/matches/") :])
            match_id, _, action = rest.partition("/")
            match = get_match(match_id)
            if match is None:
                self._send_json({"error": "match not found"}, 404)
                return
            if action == "":
                self._send_json(match)
                return
            if action == "demo":
                demo_path = get_match_file_path(match_id, "demo")
                if demo_path is None:
                    self._send_json({"error": "no demo recorded for this match"}, 404)
                    return
                self._send_file_download(demo_path, demo_download_name(match))
                return
            if action == "log":
                # The raw server log is more useful to debug with than to casually read, and
                # can reveal things like other players' SteamIDs - host-only, same gating as
                # the Admin tab, rather than open to every player who was in the match.
                _, lobby = find_lobby_for(steam_id)
                is_host = lobby is not None and lobby["host"] == steam_id
                if not is_host:
                    self._send_json({"error": "only the lobby host can download the raw log"}, 403)
                    return
                log_path = get_match_file_path(match_id, "log")
                if log_path is None:
                    self._send_json({"error": "log file not found"}, 404)
                    return
                self._send_file_download(log_path, os.path.basename(log_path))
                return
            self._send_json({"error": "not found"}, 404)
            return
        self._send_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self._read_json()
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "invalid json"}, 400)
            return

        if parsed.path == "/api/settings":
            if self._require_login() is None:
                return
            updates = {}
            if "serverName" in body:
                updates["CS2_SERVERNAME"] = body["serverName"]
            if "password" in body:
                updates["CS2_PW"] = body["password"]
            if "rconPassword" in body:
                updates["CS2_RCONPW"] = body["rconPassword"]
                write_fake_rcon_password(body["rconPassword"])
            if "maxPlayers" in body:
                updates["CS2_MAXPLAYERS"] = str(body["maxPlayers"])
            if "map" in body and body["map"]:
                # CS2_HOST_WORKSHOP_MAP makes the joedwards32/cs2 entrypoint boot straight
                # into that workshop item (it downloads/mounts it itself via steamcmd, same
                # as the live "host_workshop_map" RCON command below) - CS2_STARTMAP is
                # ignored by the entrypoint whenever CS2_HOST_WORKSHOP_MAP is set, but clear
                # it anyway so state doesn't lie about what map is actually selected. Clear
                # the workshop var symmetrically when picking a local map, or a stale
                # workshop id would silently override the local pick on the next boot.
                if body.get("mapSource") == "workshop":
                    updates["CS2_HOST_WORKSHOP_MAP"] = body["map"]
                    updates["CS2_STARTMAP"] = ""
                else:
                    updates["CS2_STARTMAP"] = body["map"]
                    updates["CS2_HOST_WORKSHOP_MAP"] = ""
            if "maxPlayers" in body or "smallTeamMode" in body:
                env = read_env()
                small_team_mode = body.get("smallTeamMode")
                if small_team_mode not in ("defusal", "rush"):
                    small_team_mode = env.get("CS2_SMALL_TEAM_MODE", "defusal")
                updates["CS2_SMALL_TEAM_MODE"] = small_team_mode
                max_players = int(updates.get("CS2_MAXPLAYERS") or env.get("CS2_MAXPLAYERS") or 10)
                team_size = max_players // 2
                if team_size in (2, 3, 4):
                    cfg = SMALL_TEAM_RUSH_CFG if small_team_mode == "rush" else SMALL_TEAM_DEFUSAL_CFG
                    updates["CS2_ADDITIONAL_ARGS"] = f"+exec {cfg}"
                else:
                    updates["CS2_ADDITIONAL_ARGS"] = ""
            if updates:
                write_env(updates)
            if "mode" in body and body["mode"] in ("bo1", "bo3", "bo5"):
                write_match_format(body["mode"])

            if body.get("gameMode") in ("versus", *GAME_MODE_MODS.keys()):
                write_game_mode(body["gameMode"])

            if "ctTeamName" in body or "tTeamName" in body:
                cur_ct, cur_t = read_team_names()
                ct_name = sanitize_cvar_string(body.get("ctTeamName", cur_ct))
                t_name = sanitize_cvar_string(body.get("tTeamName", cur_t))
                write_team_names(ct_name, t_name)
                if container_status() == "running":
                    try:
                        rcon_command(f'mp_teamname_2 "{ct_name}"')
                        rcon_command(f'mp_teamname_1 "{t_name}"')
                    except (RconError, OSError):
                        pass

            rcon_result = None
            if body.get("map") and container_status() == "running":
                map_value = str(body["map"])
                try:
                    if body.get("mapSource") == "workshop":
                        if not map_value.isdigit():
                            raise RconError("invalid workshop map id")
                        rcon_command(f"host_workshop_map {map_value}")
                    else:
                        rcon_command(f"changelevel {map_value}")
                    rcon_result = {"ok": True}
                except (RconError, OSError) as exc:
                    rcon_result = {"ok": False, "error": str(exc)}

            state = build_state()
            if rcon_result is not None:
                state["rcon"] = rcon_result
            self._send_json(state)
            return

        if parsed.path == "/api/rcon":
            if self._require_login() is None:
                return
            command = body.get("command", "").strip()
            if not command:
                self._send_json({"error": "no command given"}, 400)
                return
            try:
                output = rcon_command(command)
                self._send_json({"ok": True, "output": output})
            except (RconError, OSError) as exc:
                self._send_json({"ok": False, "error": str(exc)})
            return

        if parsed.path == "/api/config":
            if self._require_login() is None:
                return
            file = body.get("file", "")
            content = body.get("content", "")
            if not GAMEMODE_CFG_RE.match(file) or file not in list_gamemode_configs():
                self._send_json({"error": "invalid config file"}, 400)
                return
            write_gamemode_cfg(file, content)
            result = {"ok": True}
            if container_status() == "running":
                try:
                    rcon_command(f"exec {file}")
                    result["live"] = True
                except (RconError, OSError) as exc:
                    result["live"] = False
                    result["liveError"] = str(exc)
            self._send_json(result)
            return

        if parsed.path == "/api/config/presets":
            if self._require_login() is None:
                return
            file = body.get("file", "")
            name = body.get("name", "")
            content = body.get("content", "")
            if not GAMEMODE_CFG_RE.match(file) or file not in list_gamemode_configs():
                self._send_json({"error": "invalid config file"}, 400)
                return
            try:
                saved_name = save_preset(file, name, content)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
                return
            self._send_json({"ok": True, "name": saved_name, "presets": list_presets(file)})
            return

        if parsed.path == "/api/config/presets/delete":
            if self._require_login() is None:
                return
            file = body.get("file", "")
            if not GAMEMODE_CFG_RE.match(file) or file not in list_gamemode_configs():
                self._send_json({"error": "invalid config file"}, 400)
                return
            ok = delete_preset(file, body.get("name", ""))
            self._send_json({"ok": ok, "presets": list_presets(file)})
            return

        if parsed.path == "/api/mods/toggle":
            if self._require_login() is None:
                return
            name = body.get("name", "")
            try:
                enabled = toggle_mod(name)
            except FileNotFoundError:
                self._send_json({"error": "mod not found"}, 404)
                return
            self._send_json({"name": name, "enabled": enabled})
            return

        if parsed.path == "/api/workshop/add":
            if self._require_login() is None:
                return
            workshop_id = parse_workshop_id(body.get("input", ""))
            if not workshop_id:
                self._send_json({"error": "couldn't find a workshop ID in that input"}, 400)
                return
            try:
                details = fetch_workshop_details(workshop_id)
            except (URLError, OSError, TimeoutError) as exc:
                self._send_json({"error": f"couldn't reach Steam: {exc}"}, 502)
                return
            if details is None:
                self._send_json({"error": "workshop item not found"}, 404)
                return
            if details.pop("app_id", None) != CS2_APP_ID:
                self._send_json({"error": "that workshop item isn't a CS2 item"}, 400)
                return
            save_workshop_map(details)
            self._send_json({"ok": True, "map": details})
            return

        if parsed.path == "/api/launch":
            if self._require_login() is None:
                return
            code, out, err = run(
                [
                    "docker",
                    "compose",
                    "-p",
                    PROJECT_NAME,
                    "-f",
                    COMPOSE_FILE,
                    "--env-file",
                    ENV_PATH,
                    "up",
                    "-d",
                    "--force-recreate",
                    SERVICE,
                ],
                timeout=60,
            )
            mark_activity()
            request_firewall_apply(True)
            self._send_json({"ok": code == 0, "output": out + err})
            return

        if parsed.path == "/api/stop":
            if self._require_login() is None:
                return
            code, out, err = run(["docker", "stop", CONTAINER], timeout=30)
            request_firewall_apply(False)
            self._send_json({"ok": code == 0, "output": out + err})
            return

        if parsed.path == "/api/auth/logout":
            destroy_session(self._session_token())
            self._send_json({"ok": True}, headers={"Set-Cookie": self._session_cookie_header(clear=True)})
            return

        if parsed.path == "/api/lobby/create":
            steam_id = self._require_login()
            if steam_id is None:
                return
            code = create_lobby(steam_id)
            self._send_json({"ok": True, "code": code})
            return

        if parsed.path == "/api/lobby/join":
            steam_id = self._require_login()
            if steam_id is None:
                return
            code = join_lobby(body.get("code", ""), steam_id)
            if code is None:
                self._send_json({"error": "lobby not found"}, 404)
                return
            self._send_json({"ok": True, "code": code})
            return

        if parsed.path == "/api/lobby/leave":
            steam_id = session_steam_id(self._session_token())
            if steam_id:
                leave_lobby(steam_id)
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/lobby/start":
            steam_id = self._require_login()
            if steam_id is None:
                return
            code, lobby = find_lobby_for(steam_id)
            if lobby is None:
                self._send_json({"error": "not in a lobby"}, 400)
                return
            if lobby["host"] != steam_id:
                self._send_json({"error": "only the lobby host can start the match"}, 403)
                return
            if not lobby["members"] or len(lobby["ready"]) != len(lobby["members"]):
                self._send_json({"error": "not everyone is ready yet"}, 400)
                return

            password = generate_match_password()
            write_env({"CS2_PW": password})
            if container_status() == "running":
                try:
                    rcon_command(f'sv_password "{password}"')
                except (RconError, OSError):
                    pass
            else:
                run(
                    [
                        "docker",
                        "compose",
                        "-p",
                        PROJECT_NAME,
                        "-f",
                        COMPOSE_FILE,
                        "--env-file",
                        ENV_PATH,
                        "up",
                        "-d",
                        "--force-recreate",
                        SERVICE,
                    ],
                    timeout=60,
                )
                mark_activity()

            # Fires on both branches: a prior open may have failed (bad creds, a transient
            # Scaleway error) while the container itself started fine - request_apply() is
            # a no-op if the ports are already confirmed open, so this is free in the
            # common case and self-heals a stuck "running but unreachable" state otherwise.
            request_firewall_apply(True)

            port = read_env().get("CS2_PORT", "27015")
            connect = {
                "host": CS2_CONNECT_HOST,
                "port": port,
                "password": password,
                "steamUrl": f"steam://connect/{CS2_CONNECT_HOST}:{port}/{password}" if CS2_CONNECT_HOST else None,
            }
            started = start_lobby(code, steam_id, connect)
            self._send_json({"ok": started, "connect": connect})
            return

        if parsed.path == "/api/lobby/reset":
            steam_id = self._require_login()
            if steam_id is None:
                return
            code, lobby = find_lobby_for(steam_id)
            if lobby is None:
                self._send_json({"error": "not in a lobby"}, 400)
                return
            if lobby["host"] != steam_id:
                self._send_json({"error": "only the lobby host can reset the lobby"}, 403)
                return
            reset_lobby(code, steam_id)
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/lobby/force-stop":
            steam_id = self._require_login()
            if steam_id is None:
                return
            code, lobby = find_lobby_for(steam_id)
            if lobby is None:
                self._send_json({"error": "not in a lobby"}, 400)
                return
            if lobby["host"] != steam_id:
                self._send_json({"error": "only the lobby host can stop the server"}, 403)
                return

            run(["docker", "stop", CONTAINER], timeout=60)
            request_firewall_apply(False)

            # "docker stop" already blocks until the container exits, but CS2 can take a
            # while to shut down cleanly (or ignore SIGTERM and wait out the grace period
            # before Docker kills it) - poll for a confirmed exit rather than trusting a
            # single read, so the lobby only resets (ready states, waiting-for-players view)
            # once the server is actually down, not while it's still mid-shutdown.
            stopped = False
            for _ in range(45):
                if container_status() != "running":
                    stopped = True
                    break
                time.sleep(1)
            if stopped:
                reset_lobby(code, steam_id)
            self._send_json({"ok": stopped})
            return

        if parsed.path == "/api/lobby/ready":
            steam_id = self._require_login()
            if steam_id is None:
                return
            code = toggle_ready(steam_id)
            if code is None:
                self._send_json({"error": "not in a lobby"}, 400)
                return
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/lobby/move":
            steam_id = self._require_login()
            if steam_id is None:
                return
            target = body.get("steamId") or steam_id
            team = body.get("team")
            swap_with = body.get("swapWith") or None
            moved = move_member(steam_id, target, team, swap_with)
            if not moved:
                self._send_json({"error": "couldn't move that player"}, 400)
                return
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/lobby/map":
            steam_id = self._require_login()
            if steam_id is None:
                return
            map_id = body.get("map", "")
            map_source = body.get("mapSource", "local")
            is_random = bool(body.get("isRandom", False))
            if not map_id or not set_selected_map(steam_id, map_id, map_source, is_random):
                self._send_json({"error": "couldn't set the map selection"}, 400)
                return
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/lobby/kick":
            steam_id = self._require_login()
            if steam_id is None:
                return
            target = body.get("steamId")
            if not target or not kick_member(steam_id, target):
                self._send_json({"error": "couldn't kick that player"}, 400)
                return
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/lobby/delete":
            steam_id = self._require_login()
            if steam_id is None:
                return
            if not delete_lobby(steam_id):
                self._send_json({"error": "couldn't delete this lobby"}, 400)
                return
            self._send_json({"ok": True})
            return

        self._send_json({"error": "not found"}, 404)
