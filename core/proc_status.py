# proc_status.py
# Purpose: Container status, uptime, console tail, and log tail helpers.

import os
import re
import threading
from datetime import datetime, timezone

from .constants import CONTAINER, LOGS_DIR
from .util import run


def container_status():
    code, out, _ = run(["docker", "inspect", "-f", "{{.State.Status}}", CONTAINER])
    if code != 0:
        return "not created"
    return out.strip()


def tail_console(n=200):
    code, out, err = run(["docker", "logs", "--tail", str(n), CONTAINER])
    if code != 0:
        return err.strip() or "container has not been launched yet"
    return out


# Console milestones a fresh CS2 boot passes through - each label is what's shown while still
# waiting on that milestone. Steam logon and the GC session come up in parallel with the map
# load and their order relative to it varies between boots, so each is matched anywhere in
# the console. The one real ordering is "Starting map" (ss_active) having to follow the real
# map's spawn (flagged with after_previous=True) - the initial "Spawn Server: <empty>"
# placeholder load also goes ss_active, and mustn't count. Players can't connect until both
# the map is active and the GC session is up, so all stages done = joinable.
#
# The first stage is the image's steamcmd app_update on boot - a no-op "already up to date"
# most of the time, but a real CS2 patch can take minutes, so its progress lines are parsed
# for a more useful label (and partial progress) than a bar sat on "Checking for updates".
# A failed update is retried by the entrypoint (up to 3 attempts, then the container exits),
# so only "Success!" clears the stage.
READY_STAGES = [
    ("Checking for updates...", re.compile(r"Success! App '\d+'"), False),
    ("Connecting to Steam...", re.compile(r"Gameserver logged on to Steam"), False),
    ("Loading map...", re.compile(r"Spawn Server: (?!<empty>)\S+"), False),
    ("Starting map...", re.compile(r"ss_loading -> ss_active"), True),
    ("Connecting to matchmaking...", re.compile(r"activated session on GC"), False),
]

# steamcmd updating itself, before it touches the game: "[ 45%] Downloading update (...)"
STEAMCMD_SELF_UPDATE_RE = re.compile(r"^\[\s*(\d+)%\] Downloading update", re.MULTILINE)
# The game update: " Update state (0x61) downloading, progress: 45.23 (123 / 456)"
APP_UPDATE_RE = re.compile(r"Update state \(0x[0-9a-fA-F]+\) ([a-z ]+), progress: ([\d.]+)")
# The entrypoint's own retry message after a failed steamcmd run
UPDATE_RETRY_RE = re.compile(r"Retrying SteamCMD, attempt (\d+)")

_ready_lock = threading.Lock()
_ready_started_at = None  # container StartedAt the cached "all stages done" belongs to


def container_started_at():
    """The running container's raw StartedAt - also identifies one particular boot."""
    return _container_started_at()


def _container_started_at():
    code, out, _ = run(["docker", "inspect", "-f", "{{.State.StartedAt}}", CONTAINER])
    raw = out.strip()
    if code != 0 or not raw or raw.startswith("0001-01-01"):
        return None
    return raw


def _update_progress(console):
    """While the boot-time update is still running: (label, fraction 0-1) from the latest
    steamcmd progress line, or None if nothing beyond the initial check has been printed."""
    latest = None
    for pattern in (APP_UPDATE_RE, STEAMCMD_SELF_UPDATE_RE, UPDATE_RETRY_RE):
        for match in pattern.finditer(console):
            if latest is None or match.start() > latest.start():
                latest = match
    if latest is None:
        return None
    if latest.re is APP_UPDATE_RE:
        state, pct = latest.group(1, 2)
        return f"Updating server - {state.strip()} {float(pct):.0f}%", float(pct) / 100
    if latest.re is STEAMCMD_SELF_UPDATE_RE:
        return f"Updating SteamCMD {int(latest.group(1))}%", 0.0
    return f"Update failed - retrying (attempt {latest.group(1)} of 3)", 0.0


def console_ready_stages():
    """How many READY_STAGES the running container has passed, plus the label of the first
    pending one (None once all are done). The count is fractional while a game update is
    downloading, so the progress bar moves through it instead of stalling. Reads the console since the container's current
    start, so a `docker restart` (which keeps old logs) can't count a previous boot's
    milestones. A fully-ready result is cached per start, so steady-state polling doesn't
    re-read the whole console every few seconds."""
    global _ready_started_at
    started_at = _container_started_at()
    if started_at is None:
        return 0, READY_STAGES[0][0]
    with _ready_lock:
        if _ready_started_at == started_at:
            return len(READY_STAGES), None

    code, out, _ = run(["docker", "logs", "--since", started_at, CONTAINER])
    if code != 0:
        return 0, READY_STAGES[0][0]
    done = 0
    pending_label = None
    prev_end = 0
    for label, pattern, after_previous in READY_STAGES:
        match = pattern.search(out, prev_end if after_previous else 0)
        if match:
            done += 1
            prev_end = match.end()
        else:
            prev_end = len(out)
            pending_label = pending_label or label
    if pending_label == READY_STAGES[0][0]:
        update = _update_progress(out)
        if update:
            label, fraction = update
            return done + fraction, label
    if pending_label:
        return done, pending_label

    with _ready_lock:
        _ready_started_at = started_at
    return len(READY_STAGES), None


def container_env():
    """The running container's environment as {key: value} - i.e. the .env values it was
    actually booted with, which can lag behind .env once settings change mid-run."""
    code, out, _ = run(["docker", "inspect", "-f", "{{range .Config.Env}}{{println .}}{{end}}", CONTAINER])
    if code != 0:
        return {}
    env = {}
    for line in out.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            env[key] = value
    return env


def parse_started_at(raw):
    """Docker's StartedAt string (UTC, nanosecond precision) as an aware datetime, or None."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def server_uptime_seconds():
    started = parse_started_at(_container_started_at())
    if started is None:
        return None
    return int((datetime.now(timezone.utc) - started).total_seconds())


def tail_logs(n=200):
    if not os.path.isdir(LOGS_DIR):
        return "no log file found (enable sv_logfile 1 in server.cfg to write logs to disk)"
    logs = sorted(
        (f for f in os.listdir(LOGS_DIR) if f.endswith(".log")),
        key=lambda f: os.path.getmtime(os.path.join(LOGS_DIR, f)),
    )
    if not logs:
        return "no log file found (enable sv_logfile 1 in server.cfg to write logs to disk)"
    path = os.path.join(LOGS_DIR, logs[-1])
    with open(path, errors="replace") as f:
        return "".join(f.readlines()[-n:])
