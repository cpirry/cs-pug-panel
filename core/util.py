# util.py
# Purpose: Small shared helpers (subprocess runner, cvar string sanitizing).

import subprocess


def run(cmd, timeout=20):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timed out"
    except FileNotFoundError as exc:
        return -1, "", str(exc)


def sanitize_cvar_string(value):
    return str(value).replace('"', "").replace("\n", " ").replace("\r", "").strip()
