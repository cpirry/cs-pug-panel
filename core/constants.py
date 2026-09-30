# constants.py
# Purpose: Paths, environment-derived config, and static lookup tables shared across the panel.

import os
import re

COMPOSE_DIR = os.environ.get("COMPOSE_DIR", "/compose")
GAME_DIR = os.environ.get("GAME_DIR", "/gamedata")
CONTAINER = os.environ.get("CS2_CONTAINER", "cs2_server")
SERVICE = os.environ.get("CS2_SERVICE", "cs2_server")
PROJECT_NAME = os.environ.get("COMPOSE_PROJECT_NAME", "cs2server")
PORT = int(os.environ.get("PORT", "8080"))
RCON_HOST = os.environ.get("CS2_HOST", "cs2_server")
RCON_PORT = int(os.environ.get("CS2_RCON_PORT", "27015"))
# The externally-reachable host/IP players connect to (for steam://connect/ links).
# Not auto-detectable from inside the container - must be set explicitly.
CS2_CONNECT_HOST = os.environ.get("CS2_CONNECT_HOST", "")

# SteamID64s allowed to log in. Empty by default (fail-secure: nobody can log in
# until this is set) - configure via the STEAM_ALLOWLIST env var, comma-separated.
STEAM_ALLOWLIST = {s.strip() for s in os.environ.get("STEAM_ALLOWLIST", "").split(",") if s.strip()}

# Set STEAM_ALLOWLIST_DISABLED=1 to let anyone with a Steam account log in, ignoring
# STEAM_ALLOWLIST entirely. Off by default - only meant for temporary debugging.
STEAM_ALLOWLIST_DISABLED = os.environ.get("STEAM_ALLOWLIST_DISABLED", "").strip().lower() in ("1", "true", "yes")

ENV_PATH = os.path.join(COMPOSE_DIR, ".env")
COMPOSE_FILE = os.path.join(COMPOSE_DIR, "docker-compose.yml")
MAPS_DIR = os.path.join(GAME_DIR, "maps")
PLUGINS_DIR = os.path.join(GAME_DIR, "addons", "counterstrikesharp", "plugins")
SERVER_CFG = os.path.join(GAME_DIR, "cfg", "server.cfg")
CONFIG_PRESETS_DIR = os.path.join(GAME_DIR, "cfg", "panel_presets")
WORKSHOP_MAPS_FILE = os.path.join(GAME_DIR, "cfg", "panel_workshop_maps.json")
LOGS_DIR = os.path.join(GAME_DIR, "logs")
FAKE_RCON_CFG = os.path.join(GAME_DIR, "addons", "configs", "fake_rcon", "config.cfg")
MAP_IMAGES_DIR = os.environ.get("MAP_IMAGES_DIR", "/app/map-images")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
MIME = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

MAP_RE = re.compile(r"^de_[a-z0-9_]+\.vpk$")

CORE_MAPS = [
    "de_ancient",
    "de_anubis",
    "de_dust2",
    "de_cache",
    "de_inferno",
    "de_mirage",
    "de_nuke",
    "de_overpass",
]

# Best-effort list of CS2's Wingman (2v2) map pool - edit to match whatever's actually
# installed on the server (list_maps() only shows entries that are actually present).
WINGMAN_MAPS = [
    "de_lake",
    "de_shortdust",
    "de_shortnuke",
]

CS2_APP_ID = 730

# Game modes that are implemented as CounterStrikeSharp plugins living alongside
# the regular mods, but selected via the Game Mode picker instead of the Mods
# list. Folder names are best guesses for modes not installed yet - update here
# once the real plugin is added if the name differs.
GAME_MODE_MODS = {
    "retakes": "Retakes",
    "executes": "Executes",
    "gungame": "GG2",
    "kz": "KZ",
    "bhop": "Bhop",
}

GAMEMODE_CFG_RE = re.compile(r"^gamemode_[a-z0-9_]+\.cfg$")
DEFAULT_GAMEMODE_CFG = "gamemode_competitive.cfg"

# For 2v2/3v3/4v4 team sizes, which gamemode config to +exec at server launch based on the
# host's Defusal/Rush pick (see handler.py's /api/settings).
SMALL_TEAM_DEFUSAL_CFG = "gamemode_competitive2v2.cfg"
SMALL_TEAM_RUSH_CFG = "gamemode_rush.cfg"

# core/firewall.py runs Terraform (arch/tform/) as a sibling `docker run` via the host
# Docker socket, so this must be a HOST-absolute path (resolved by the host daemon), not
# a path inside the panel's own container - never read via os.path from in here.
TFORM_HOST_DIR = os.environ.get("TFORM_HOST_DIR", "")
TERRAFORM_IMAGE = "hashicorp/terraform:1.9.8"
SCW_ACCESS_KEY = os.environ.get("SCW_ACCESS_KEY", "")
SCW_SECRET_KEY = os.environ.get("SCW_SECRET_KEY", "")
SCW_DEFAULT_PROJECT_ID = os.environ.get("SCW_DEFAULT_PROJECT_ID", "")
