# gamemode_cfg.py
# Purpose: Reads/writes gamemode config files and their saved presets.

import os
import re

from .constants import CONFIG_PRESETS_DIR, DEFAULT_GAMEMODE_CFG, GAME_DIR, GAMEMODE_CFG_RE


def list_gamemode_configs():
    cfg_dir = os.path.join(GAME_DIR, "cfg")
    if not os.path.isdir(cfg_dir):
        return []
    return sorted(f for f in os.listdir(cfg_dir) if GAMEMODE_CFG_RE.match(f))


def resolve_gamemode_cfg(name):
    files = list_gamemode_configs()
    if name in files:
        return name
    if DEFAULT_GAMEMODE_CFG in files:
        return DEFAULT_GAMEMODE_CFG
    return files[0] if files else None


def read_gamemode_cfg(name):
    path = os.path.join(GAME_DIR, "cfg", name)
    if not os.path.isfile(path):
        return ""
    with open(path, errors="replace") as f:
        return f.read()


def write_gamemode_cfg(name, content):
    with open(os.path.join(GAME_DIR, "cfg", name), "w") as f:
        f.write(content)


def sanitize_preset_name(name):
    return re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()[:64]


def preset_dir_for(file):
    return os.path.join(CONFIG_PRESETS_DIR, os.path.splitext(file)[0])


def list_presets(file):
    d = preset_dir_for(file)
    if not os.path.isdir(d):
        return []
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".cfg"))


def read_preset(file, name):
    safe = sanitize_preset_name(name)
    path = os.path.join(preset_dir_for(file), safe + ".cfg")
    if not safe or not os.path.isfile(path):
        return None
    with open(path, errors="replace") as f:
        return f.read()


def save_preset(file, name, content):
    safe = sanitize_preset_name(name)
    if not safe:
        raise ValueError("invalid preset name")
    d = preset_dir_for(file)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, safe + ".cfg"), "w") as f:
        f.write(content)
    return safe


def delete_preset(file, name):
    safe = sanitize_preset_name(name)
    path = os.path.join(preset_dir_for(file), safe + ".cfg")
    if safe and os.path.isfile(path):
        os.remove(path)
        return True
    return False
