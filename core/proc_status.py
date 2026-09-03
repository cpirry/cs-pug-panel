# proc_status.py
# Purpose: Container status, uptime, console tail, and log tail helpers.

import os
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


def server_uptime_seconds():
    code, out, _ = run(["docker", "inspect", "-f", "{{.State.StartedAt}}", CONTAINER])
    raw = out.strip()
    if code != 0 or not raw or raw.startswith("0001-01-01"):
        return None
    try:
        started = datetime.strptime(raw.split(".")[0], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
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
