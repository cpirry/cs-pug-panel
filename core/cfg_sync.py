# cfg_sync.py
# Purpose: Mirrors panel settings (match format, team names, fake_rcon password) into game config files.

import os
import re

from .constants import FAKE_RCON_CFG, SERVER_CFG
from .util import sanitize_cvar_string


def read_match_format():
    if not os.path.exists(SERVER_CFG):
        return "bo1"
    overtime = "0"
    with open(SERVER_CFG) as f:
        for line in f:
            m = re.match(r"\s*mp_overtime_enable\s+(\d+)", line)
            if m:
                overtime = m.group(1)
    return "bo1" if overtime == "0" else "bo3"


def write_match_format(mode):
    maxrounds = "24"
    overtime = "0" if mode == "bo1" else "1"
    lines = []
    if os.path.exists(SERVER_CFG):
        with open(SERVER_CFG) as f:
            lines = f.read().splitlines()
    out = []
    seen_rounds = seen_ot = False
    for line in lines:
        if re.match(r"\s*mp_maxrounds\s+", line):
            out.append(f"mp_maxrounds {maxrounds}")
            seen_rounds = True
        elif re.match(r"\s*mp_overtime_enable\s+", line):
            out.append(f"mp_overtime_enable {overtime}")
            seen_ot = True
        else:
            out.append(line)
    if not seen_rounds or not seen_ot:
        out.append("")
        out.append("// Match format (set by control panel)")
        if not seen_rounds:
            out.append(f"mp_maxrounds {maxrounds}")
        if not seen_ot:
            out.append(f"mp_overtime_enable {overtime}")
    with open(SERVER_CFG, "w") as f:
        f.write("\n".join(out) + "\n")


def read_molotov_glass():
    if not os.path.exists(SERVER_CFG):
        return False
    enabled = False
    with open(SERVER_CFG) as f:
        for line in f:
            m = re.match(r"\s*sv_molotov_broken_glass_trap\s+(\d+)", line)
            if m:
                enabled = m.group(1) != "0"
    return enabled


def write_molotov_glass(enabled):
    value = "1" if enabled else "0"
    lines = []
    if os.path.exists(SERVER_CFG):
        with open(SERVER_CFG) as f:
            lines = f.read().splitlines()
    out = []
    seen = False
    for line in lines:
        if re.match(r"\s*sv_molotov_broken_glass_trap\s+", line):
            out.append(f"sv_molotov_broken_glass_trap {value}")
            seen = True
        else:
            out.append(line)
    if not seen:
        out.append("")
        out.append("// Molotov broken glass trap (set by control panel)")
        out.append(f"sv_molotov_broken_glass_trap {value}")
    with open(SERVER_CFG, "w") as f:
        f.write("\n".join(out) + "\n")


def read_team_names():
    ct_name = t_name = ""
    if not os.path.exists(SERVER_CFG):
        return ct_name, t_name
    with open(SERVER_CFG) as f:
        for line in f:
            m = re.match(r'\s*mp_teamname_2\s+"?([^"\r\n]*?)"?\s*$', line)
            if m:
                ct_name = m.group(1)
            m = re.match(r'\s*mp_teamname_1\s+"?([^"\r\n]*?)"?\s*$', line)
            if m:
                t_name = m.group(1)
    return ct_name, t_name


def write_team_names(ct_name, t_name):
    lines = []
    if os.path.exists(SERVER_CFG):
        with open(SERVER_CFG) as f:
            lines = f.read().splitlines()
    out = []
    seen_ct = seen_t = False
    for line in lines:
        if re.match(r"\s*mp_teamname_2\s+", line):
            out.append(f'mp_teamname_2 "{ct_name}"')
            seen_ct = True
        elif re.match(r"\s*mp_teamname_1\s+", line):
            out.append(f'mp_teamname_1 "{t_name}"')
            seen_t = True
        else:
            out.append(line)
    if not seen_ct or not seen_t:
        out.append("")
        out.append("// Team names (set by control panel)")
        if not seen_t:
            out.append(f'mp_teamname_1 "{t_name}"')
        if not seen_ct:
            out.append(f'mp_teamname_2 "{ct_name}"')
    with open(SERVER_CFG, "w") as f:
        f.write("\n".join(out) + "\n")


def write_fake_rcon_password(password):
    password = sanitize_cvar_string(password)
    if not os.path.isfile(FAKE_RCON_CFG):
        return
    with open(FAKE_RCON_CFG) as f:
        lines = f.read().splitlines()
    out = []
    seen = False
    for line in lines:
        if re.match(r'\s*"rcon_password"\s*"', line):
            out.append(f'\t"rcon_password"\t\t"{password}"')
            seen = True
        else:
            out.append(line)
    if not seen:
        for i in range(len(out) - 1, -1, -1):
            if out[i].strip() == "}":
                out.insert(i, f'\t"rcon_password"\t\t"{password}"')
                break
    with open(FAKE_RCON_CFG, "w") as f:
        f.write("\n".join(out) + "\n")
