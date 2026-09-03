# envfile.py
# Purpose: Reads and writes the compose project's .env file.

import os
import re

from .constants import ENV_PATH


def read_env():
    values = {}
    if not os.path.exists(ENV_PATH):
        return values
    with open(ENV_PATH) as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, rest = stripped.partition("=")
            val = re.split(r"\s+#", rest, maxsplit=1)[0].strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            values[key.strip()] = val
    return values


def write_env(updates):
    updates = dict(updates)
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            lines = f.read().splitlines()
    out = []
    for line in lines:
        matched_key = None
        for key in updates:
            if line.startswith(key + "=") or line.startswith("#" + key + "="):
                matched_key = key
                break
        if matched_key is None:
            out.append(line)
            continue
        eq_idx = line.index("=")
        rest = line[eq_idx + 1 :]
        comment_match = re.search(r"(\s+#.*)$", rest)
        comment = comment_match.group(1) if comment_match else ""
        out.append(f"{matched_key}={updates.pop(matched_key)}{comment}")
    for key, val in updates.items():
        out.append(f"{key}={val}")
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(out) + "\n")
