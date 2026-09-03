# mods.py
# Purpose: Lists/toggles CounterStrikeSharp mods and switches game-mode mods.

import os

from .constants import GAME_MODE_MODS, PLUGINS_DIR


def list_mods():
    if not os.path.isdir(PLUGINS_DIR):
        return []
    game_mode_mod_names = set(GAME_MODE_MODS.values())
    mods = []
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
    enabled_path = os.path.join(PLUGINS_DIR, name)
    disabled_path = os.path.join(PLUGINS_DIR, ".disabled_" + name)
    if os.path.isdir(enabled_path):
        os.rename(enabled_path, disabled_path)
        return False
    if os.path.isdir(disabled_path):
        os.rename(disabled_path, enabled_path)
        return True
    raise FileNotFoundError(name)
