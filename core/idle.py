# idle.py
# Purpose: Auto-shuts down the server after a period of inactivity.

import threading
import time

from .constants import CONTAINER
from .envfile import read_env
from .match_state import real_players
from .proc_status import container_status
from .util import run

_idle_lock = threading.Lock()
_idle_state = {"last_active": time.time()}


def mark_activity():
    with _idle_lock:
        _idle_state["last_active"] = time.time()


def idle_monitor(poll_seconds=60):
    while True:
        time.sleep(poll_seconds)
        env = read_env()
        if env.get("CS2_AUTOSHUTDOWN", "0") != "1":
            mark_activity()
            continue
        try:
            idle_minutes = float(env.get("CS2_AUTOSHUTDOWN_IDLE_MIN", "20"))
        except ValueError:
            idle_minutes = 20
        if container_status() != "running":
            mark_activity()
            continue
        if real_players():
            mark_activity()
            continue
        with _idle_lock:
            idle_for = time.time() - _idle_state["last_active"]
        if idle_for >= idle_minutes * 60:
            run(["docker", "stop", CONTAINER], timeout=30)
            mark_activity()
