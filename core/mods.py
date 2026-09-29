# mods.py
# Purpose: Lists/toggles CounterStrikeSharp mods and switches game-mode mods.

import os

from .cfg_sync import read_molotov_glass, write_molotov_glass
from .constants import GAME_MODE_MODS, PLUGINS_DIR

# Not a real CounterStrikeSharp plugin - just a server cvar (sv_molotov_broken_glass_trap)
# surfaced as a toggle in the same Mods list, since that's the closest existing UI for a
# simple on/off gameplay setting. Special-cased in list_mods()/toggle_mod() below.
MOLOTOV_GLASS_MOD_NAME = "Use molotov broken glass update?"


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
    enabled_path = os.path.join(PLUGINS_DIR, name)
    disabled_path = os.path.join(PLUGINS_DIR, ".disabled_" + name)
    if os.path.isdir(enabled_path):
        os.rename(enabled_path, disabled_path)
        return False
    if os.path.isdir(disabled_path):
        os.rename(disabled_path, enabled_path)
        return True
    raise FileNotFoundError(name)
