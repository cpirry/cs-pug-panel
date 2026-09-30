# firewall.py
# Purpose: Opens/closes CS2's ports on the Scaleway security group (via arch/tform's
# Terraform config) whenever the server starts/stops.
#
# Runs terraform as a sibling `docker run` through the host Docker socket the panel
# already uses for `docker compose`/`docker stop` - keeps the panel image thin and makes
# the Terraform version a one-line constant bump instead of a rebuild. Because it's a
# sibling-container call, TFORM_HOST_DIR must be a host-absolute path (resolved by the
# host daemon), not a path inside the panel's own container.
#
# One long-lived worker thread (started from app.py, same pattern as idle.py's
# idle_monitor) always converges on the *latest* requested state rather than queuing every
# request in arrival order - a start-click and an idle-timeout-close can race, and what
# matters is which one is true now, not which one was asked for first. request_apply()
# also no-ops if the last known result already matches what's being asked for, so the
# common "already running, someone just readied up" path costs nothing - but a previously
# failed apply (bad creds, transient Scaleway error) still isn't "open"/"closed" yet, so
# it gets retried automatically on the next call instead of staying silently wrong.

import threading
import time

from .constants import (
    SCW_ACCESS_KEY,
    SCW_DEFAULT_PROJECT_ID,
    SCW_SECRET_KEY,
    TERRAFORM_IMAGE,
    TFORM_HOST_DIR,
)
from .util import run

RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
APPLY_TIMEOUT = 120
CHECK_TIMEOUT = 20

_lock = threading.Lock()
_wake = threading.Event()
_state = {
    "desired": None,  # True (open) / False (closed) / None (never requested)
    "lastResult": None,  # "open" / "closed" / "error" / None
    "message": "",
}


def get_status():
    with _lock:
        return dict(_state)


def request_apply(open_ports):
    """Asks the worker to converge the security group toward open_ports. Returns
    immediately - never blocks the caller (HTTP request handlers, the idle monitor)."""
    with _lock:
        already_settled = _state["desired"] == open_ports and _state["lastResult"] == (
            "open" if open_ports else "closed"
        )
        if already_settled:
            return
        _state["desired"] = open_ports
    _wake.set()


def _docker_terraform(args, timeout=APPLY_TIMEOUT):
    return run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{TFORM_HOST_DIR}:/workspace",
            "-w",
            "/workspace",
            "-e",
            f"SCW_ACCESS_KEY={SCW_ACCESS_KEY}",
            "-e",
            f"SCW_SECRET_KEY={SCW_SECRET_KEY}",
            "-e",
            f"SCW_DEFAULT_PROJECT_ID={SCW_DEFAULT_PROJECT_ID}",
            TERRAFORM_IMAGE,
            *args,
        ],
        timeout=timeout,
    )


def _apply_once(open_ports):
    # A wrong/stale TFORM_HOST_DIR would otherwise fail confusingly: `docker run -v`
    # silently auto-creates an empty directory at that host path rather than erroring, so
    # check the real config is actually there before trusting anything past this point.
    code, out, err = run(
        ["docker", "run", "--rm", "-v", f"{TFORM_HOST_DIR}:/workspace", "-w", "/workspace", "alpine", "test", "-f", "main.tf"],
        timeout=CHECK_TIMEOUT,
    )
    if code != 0:
        return False, f"TFORM_HOST_DIR ({TFORM_HOST_DIR!r}) doesn't contain main.tf - check the path"

    code, out, err = _docker_terraform(["init", "-input=false"])
    if code != 0:
        return False, "terraform init failed"

    code, out, err = _docker_terraform(
        ["apply", "-auto-approve", "-input=false", f"-var=cs2_server_running={'true' if open_ports else 'false'}"]
    )
    if code != 0:
        return False, "terraform apply failed"
    return True, ""


def firewall_worker():
    while True:
        _wake.wait()
        _wake.clear()
        with _lock:
            desired = _state["desired"]
        if desired is None:
            continue

        ok, message = False, ""
        for attempt in range(RETRY_ATTEMPTS):
            ok, message = _apply_once(desired)
            if ok:
                break
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY_SECONDS)

        with _lock:
            if _state["desired"] != desired:
                # Something newer came in while this apply was running - go again
                # immediately instead of settling on a now-stale result.
                _wake.set()
                continue
            _state["lastResult"] = ("open" if desired else "closed") if ok else "error"
            _state["message"] = message

        label = "open" if desired else "closed"
        print(f"firewall: ports {label}" if ok else f"firewall: failed to set ports {label} - {message}")
