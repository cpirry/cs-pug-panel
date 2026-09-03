# handler.py
# Purpose: HTTP request routing (GET/POST) for the panel's API and static files.

import json
import os
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
    ENV_PATH,
    GAME_MODE_MODS,
    GAMEMODE_CFG_RE,
    MAP_IMAGES_DIR,
    MIME,
    PROJECT_NAME,
    SERVICE,
    STATIC_DIR,
)
from .envfile import write_env
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
from .maps import fetch_workshop_details, parse_workshop_id, save_workshop_map
from .match_state import _reset_match_state, list_players, match_elapsed_seconds
from .mods import toggle_mod, write_game_mode
from .proc_status import container_status, server_uptime_seconds, tail_console, tail_logs
from .rcon import RconError, rcon_command
from .state import build_state
from .util import run, sanitize_cvar_string


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
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

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self._send_json(build_state())
            return
        if parsed.path == "/api/tail":
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
        self._send_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self._read_json()
        except (json.JSONDecodeError, ValueError):
            self._send_json({"error": "invalid json"}, 400)
            return

        if parsed.path == "/api/settings":
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
            if "map" in body and body["map"] and body.get("mapSource") != "workshop":
                updates["CS2_STARTMAP"] = body["map"]
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
            file = body.get("file", "")
            if not GAMEMODE_CFG_RE.match(file) or file not in list_gamemode_configs():
                self._send_json({"error": "invalid config file"}, 400)
                return
            ok = delete_preset(file, body.get("name", ""))
            self._send_json({"ok": ok, "presets": list_presets(file)})
            return

        if parsed.path == "/api/mods/toggle":
            name = body.get("name", "")
            try:
                enabled = toggle_mod(name)
            except FileNotFoundError:
                self._send_json({"error": "mod not found"}, 404)
                return
            self._send_json({"name": name, "enabled": enabled})
            return

        if parsed.path == "/api/workshop/add":
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
            self._send_json({"ok": code == 0, "output": out + err})
            return

        if parsed.path == "/api/stop":
            code, out, err = run(["docker", "stop", CONTAINER], timeout=30)
            self._send_json({"ok": code == 0, "output": out + err})
            return

        self._send_json({"error": "not found"}, 404)
