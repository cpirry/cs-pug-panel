# state.py
# Purpose: Builds the aggregated state payload served at /api/state.

from .cfg_sync import read_match_format, read_team_names
from .envfile import read_env
from .maps import list_maps
from .mods import list_mods, read_game_mode
from .proc_status import container_status


def build_state():
    env = read_env()
    ct_name, t_name = read_team_names()
    return {
        "running": container_status() == "running",
        "status": container_status(),
        "maps": list_maps(),
        "selectedMap": env.get("CS2_STARTMAP", ""),
        "mode": read_match_format(),
        "gameMode": read_game_mode(),
        "mods": list_mods(),
        "settings": {
            "serverName": env.get("CS2_SERVERNAME", ""),
            "password": env.get("CS2_PW", ""),
            "rconPassword": env.get("CS2_RCONPW", ""),
            "maxPlayers": env.get("CS2_MAXPLAYERS", ""),
            "ctTeamName": ct_name,
            "tTeamName": t_name,
        },
    }
