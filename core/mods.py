# mods.py
# Purpose: Lists/toggles CounterStrikeSharp mods and switches game-mode mods.

import os

from .cfg_sync import read_bot_fill, read_molotov_glass, write_bot_fill, write_molotov_glass
from .constants import GAME_MODE_MODS, PLUGINS_DIR
from .envfile import player_slots, read_env, sourcetv_slots
from .proc_status import container_status
from .rcon import RconError, rcon_command

# Not a real CounterStrikeSharp plugin - just a server cvar (sv_molotov_broken_glass_trap)
# surfaced as a toggle in the same Mods list, since that's the closest existing UI for a
# simple on/off gameplay setting. Special-cased in list_mods()/toggle_mod() below.
MOLOTOV_GLASS_MOD_NAME = "Use molotov broken glass update?"

# Same idea - bot_quota_mode/bot_quota in gamemode_competitive_server.cfg, not a plugin.
BOT_FILL_MOD_NAME = "Fill empty slots with bots"
# What gamemode_competitive.cfg sets - restored live when the toggle is switched off.
DEFAULT_BOT_QUOTA_MODE = "competitive"
DEFAULT_BOT_QUOTA = 1


def bot_fill_quota():
    """fill mode counts SourceTV towards bot_quota (it's a bot client), so this is one per
    player slot plus SourceTV's - i.e. a full lobby never has a bot left in it."""
    env = read_env()
    return player_slots(env) + sourcetv_slots(env)


def sync_bot_fill(apply_live=True):
    """Rewrites the bot settings for the current team size (if the toggle is on) and, when
    the server is up, pushes them over RCON too - the cfg file itself is only read on the
    next map load."""
    enabled = read_bot_fill()
    if enabled:
        write_bot_fill(True, bot_fill_quota())
    if not apply_live or container_status() != "running":
        return
    mode, quota = ("fill", bot_fill_quota()) if enabled else (DEFAULT_BOT_QUOTA_MODE, DEFAULT_BOT_QUOTA)
    try:
        rcon_command(f"bot_quota_mode {mode}")
        rcon_command(f"bot_quota {quota}")
    except (RconError, OSError):
        pass


def list_mods():
    mods = []
    if os.path.isdir(PLUGINS_DIR):
        game_mode_mod_names = set(GAME_MODE_MODS.values())
        for name in sorted(os.listdir(PLUGINS_DIR)):
            full = os.path.join(PLUGINS_DIR, name)
            if not os.path.isdir(full):
                continue
            if name.startswith(".disabled_"):
                real_name = name[len(".disabled_") :]
                if real_name in game_mode_mod_names:
                    continue
                mods.append({"name": real_name, "enabled": False})
            else:
                if name in game_mode_mod_names:
                    continue
                mods.append({"name": name, "enabled": True})
    mods.append({"name": MOLOTOV_GLASS_MOD_NAME, "enabled": read_molotov_glass()})
    mods.append({"name": BOT_FILL_MOD_NAME, "enabled": read_bot_fill()})
    return mods


def set_mod_enabled(name, enabled):
    enabled_path = os.path.join(PLUGINS_DIR, name)
    disabled_path = os.path.join(PLUGINS_DIR, ".disabled_" + name)
    if enabled and os.path.isdir(disabled_path):
        os.rename(disabled_path, enabled_path)
    elif not enabled and os.path.isdir(enabled_path):
        os.rename(enabled_path, disabled_path)


def read_game_mode():
    for mode, mod_name in GAME_MODE_MODS.items():
        if os.path.isdir(os.path.join(PLUGINS_DIR, mod_name)):
            return mode
    return "versus"


def write_game_mode(mode):
    for m, mod_name in GAME_MODE_MODS.items():
        set_mod_enabled(mod_name, enabled=(m == mode))


def toggle_mod(name):
    if name == MOLOTOV_GLASS_MOD_NAME:
        enabled = not read_molotov_glass()
        write_molotov_glass(enabled)
        return enabled
    if name == BOT_FILL_MOD_NAME:
        enabled = not read_bot_fill()
        write_bot_fill(enabled, bot_fill_quota())
        sync_bot_fill()
        return enabled
    enabled_path = os.path.join(PLUGINS_DIR, name)
    disabled_path = os.path.join(PLUGINS_DIR, ".disabled_" + name)
    if os.path.isdir(enabled_path):
        os.rename(enabled_path, disabled_path)
        return False
    if os.path.isdir(disabled_path):
        os.rename(disabled_path, enabled_path)
        return True
    raise FileNotFoundError(name)
