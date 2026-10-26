# match_end.py
# Purpose: Auto-stops the server shortly after a match finishes (a team has won).
#
# The end of a match is read from the server's log files (sv_logfile), not the console -
# CS2 doesn't echo log lines to stdout. "Game Over: competitive <map> score 13:7 after 31 min"
# is written once, when the final round ends. Only log files touched since the current
# container started are searched, so an earlier boot's finished match can't trigger a stop.

import os
import re
import time

from .constants import CONTAINER, LOGS_DIR
from .envfile import read_env
from .firewall import request_apply as request_firewall_apply
from .lobby import reset_in_match_lobbies
from .proc_status import container_started_at, container_status, parse_started_at
from .rcon import RconError, rcon_command
from .util import run

GAME_OVER_RE = re.compile(r": Game Over: ")
DEFAULT_SHUTDOWN_DELAY_SECONDS = 15
# Long enough for SourceTV to flush and close the demo after tv_stoprecord, so the
# download isn't a truncated file.
DEMO_FLUSH_SECONDS = 3


def _match_finished_since(started_epoch):
    if not os.path.isdir(LOGS_DIR):
        return False
    for name in os.listdir(LOGS_DIR):
        if not name.endswith(".log"):
            continue
        path = os.path.join(LOGS_DIR, name)
        try:
            if os.path.getmtime(path) < started_epoch:
                continue
            with open(path, errors="replace") as f:
                if any(GAME_OVER_RE.search(line) for line in f):
                    return True
        except OSError:
            continue
    return False


def _rcon_quietly(command):
    try:
        rcon_command(command)
    except (RconError, OSError):
        pass


def _shutdown_delay_seconds():
    """CS2_MATCH_END_SHUTDOWN_SEC in the compose .env - read per match like the idle
    settings, so changing it doesn't need a panel restart."""
    try:
        return max(0, int(read_env().get("CS2_MATCH_END_SHUTDOWN_SEC", DEFAULT_SHUTDOWN_DELAY_SECONDS)))
    except ValueError:
        return DEFAULT_SHUTDOWN_DELAY_SECONDS


def _shutdown_after_match(started_at):
    delay = _shutdown_delay_seconds()
    _rcon_quietly(f'say "Match over - server shutting down in {delay} seconds"')
    time.sleep(delay)
    # Someone may have stopped/restarted the server during the countdown - only stop the
    # same boot whose match just ended.
    if container_status() != "running" or container_started_at() != started_at:
        return
    _rcon_quietly("tv_stoprecord")
    time.sleep(DEMO_FLUSH_SECONDS)
    run(["docker", "stop", CONTAINER], timeout=60)
    request_firewall_apply(False)
    reset_in_match_lobbies()
    print("match end: match finished - server stopped")


def match_end_monitor(poll_seconds=5):
    handled_start = None
    while True:
        time.sleep(poll_seconds)
        if container_status() != "running":
            continue
        started_at = container_started_at()
        started = parse_started_at(started_at)
        if started is None or started_at == handled_start:
            continue
        if _match_finished_since(started.timestamp()):
            handled_start = started_at
            _shutdown_after_match(started_at)
