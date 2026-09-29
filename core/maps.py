# maps.py
# Purpose: Lists local maps and fetches/stores Workshop maps.

import json
import os
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .constants import CORE_MAPS, MAP_RE, MAPS_DIR, WINGMAN_MAPS, WORKSHOP_MAPS_FILE

WORKSHOP_ID_RE = re.compile(r"^\d+$")
WORKSHOP_URL_ID_RE = re.compile(r"[?&]id=(\d+)")


def list_maps():
    if not os.path.isdir(MAPS_DIR):
        return {"core": [], "wingman": [], "extra": [], "workshop": []}
    installed = sorted(
        f[:-4]
        for f in os.listdir(MAPS_DIR)
        if MAP_RE.match(f) and not f.endswith("_vanity.vpk")
    )
    core = [m for m in CORE_MAPS if m in installed]
    wingman = [m for m in WINGMAN_MAPS if m in installed]
    extra = [m for m in installed if m not in CORE_MAPS and m not in WINGMAN_MAPS]
    return {"core": core, "wingman": wingman, "extra": extra, "workshop": read_workshop_maps()}


def parse_workshop_id(raw):
    raw = raw.strip()
    if WORKSHOP_ID_RE.match(raw):
        return raw
    m = WORKSHOP_URL_ID_RE.search(raw)
    return m.group(1) if m else None


def fetch_workshop_details(workshop_id):
    body = urlencode({"itemcount": "1", "publishedfileids[0]": workshop_id}).encode()
    req = Request(
        "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
        data=body,
        method="POST",
    )
    with urlopen(req, timeout=10) as resp:
        payload = json.loads(resp.read())
    details = payload.get("response", {}).get("publishedfiledetails", [])
    if not details or details[0].get("result") != 1:
        return None
    d = details[0]
    return {
        "id": workshop_id,
        "title": d.get("title") or f"Workshop Map {workshop_id}",
        "thumbnail": d.get("preview_url", ""),
        "app_id": d.get("consumer_app_id"),
    }


def read_workshop_maps():
    if not os.path.isfile(WORKSHOP_MAPS_FILE):
        return []
    with open(WORKSHOP_MAPS_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_workshop_map(entry):
    maps = [m for m in read_workshop_maps() if m["id"] != entry["id"]]
    maps.append(entry)
    os.makedirs(os.path.dirname(WORKSHOP_MAPS_FILE), exist_ok=True)
    with open(WORKSHOP_MAPS_FILE, "w") as f:
        json.dump(maps, f, indent=2)
    return maps
