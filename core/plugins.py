# plugins.py
# Purpose: Lists installed server plugins (Metamod plugins and CounterStrikeSharp plugins) with
# their installed/latest versions, and updates them in the background from their releases.
#
# Updating mirrors scripts/update-cs2-plugins.sh in the home-server repo:
# - Existing config files are never overwritten (anything under configs/ or cfg/, and
#   metaplugins.ini) - only missing ones are added. Installed files are swapped in with an
#   atomic rename, so a running server keeps its loaded copy and picks up the new one on the
#   next start.
# - CS2 runs on Steam Runtime 4 (glibc 2.41+), which refuses to load a .so flagged as needing
#   an executable stack - any plugin binary still carrying that flag gets it cleared.
# - The directories an update touches are backed up first (last BACKUPS_TO_KEEP kept).

import json
import os
import re
import shutil
import struct
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile

from .constants import (
    ADDONS_DIR,
    GAME_DIR,
    GAMEINFO_FILE,
    PLUGIN_BACKUPS_DIR,
    PLUGIN_LATEST_FILE,
    PLUGIN_VERSIONS_FILE,
)
from .proc_status import container_status
from .rcon import RconError, rcon_command

CSS_DIR = os.path.join(ADDONS_DIR, "counterstrikesharp")
CSS_PLUGINS_DIR = os.path.join(CSS_DIR, "plugins")
METAMOD_DIR = os.path.join(ADDONS_DIR, "metamod")

# The Check for updates button can't hit GitHub more often than this (its unauthenticated API
# allows 60 requests/hour per IP, and one check costs one request per GitHub plugin).
MIN_CHECK_INTERVAL_SECONDS = 60
HTTP_TIMEOUT = 60
BACKUPS_TO_KEEP = 3
USER_AGENT = "cs2-server-panel"

# Known plugins and where their releases come from. "kind" is just the tile label.
#   source: ("metamod",) for the AlliedMods dev-build drop, or ("github", repo, asset regex)
#   meta_name: the plugin's name in `meta list` output, used to read its live version
#   detect: a file-based version detector (see _detect_* below), for when the panel has no
#           record of installing it
KNOWN_PLUGINS = [
    {
        "id": "metamod",
        "name": "Metamod:Source",
        "kind": "Framework",
        "source": ("metamod",),
        "detect": "metamod",
        "note": "Update this first - CounterStrikeSharp releases often need a newer build.",
    },
    {
        "id": "counterstrikesharp",
        "name": "CounterStrikeSharp",
        "kind": "Framework",
        "source": ("github", "roflmuffin/CounterStrikeSharp", r"^counterstrikesharp-with-runtime-linux-.*\.zip$"),
        "detect": "css",
        "meta_name": "CounterStrikeSharp",
    },
    {
        "id": "multiaddonmanager",
        "name": "MultiAddonManager",
        "kind": "Metamod plugin",
        "source": ("github", "Source2ZE/MultiAddonManager", r"-steamrt4\.tar\.gz$"),
        "meta_name": "MultiAddonManager",
        "vdf": "multiaddonmanager.vdf",
    },
    {
        "id": "fake_rcon",
        "name": "Fake RCON",
        "kind": "Metamod plugin",
        "source": ("github", "Salvatore-Als/cs2-fake-rcon", r"^linux\.tar\.gz$"),
        "meta_name": "Fake RCON",
        "vdf": "fake_rcon.vdf",
    },
    {
        "id": "RollTheDice",
        "name": "RollTheDice",
        "kind": "CSS plugin",
        "source": ("github", "Kandru/cs2-roll-the-dice", r"\.zip$"),
        "detect": "css_plugin",
    },
    {
        "id": "FortniteEmotesNDances",
        "name": "FortniteEmotesNDances",
        "kind": "CSS plugin",
        "source": ("github", "Cruze03/FortniteEmotesNDances", r"\.zip$"),
        "detect": "css_plugin",
    },
]
KNOWN_BY_ID = {p["id"]: p for p in KNOWN_PLUGINS}
# Metamod .vdf files that belong to a known plugin (or to CSS itself) rather than being a
# separate plugin to discover.
KNOWN_VDFS = {p["vdf"] for p in KNOWN_PLUGINS if "vdf" in p} | {"counterstrikesharp.vdf"}

_lock = threading.Lock()
_jobs = {}  # plugin id -> {"state": "updating" | "done" | "error", "message": str}
# Latest-release lookups, checked once and saved to disk (so panel restarts don't re-check);
# after that only the Check for updates button refreshes them.
#   {"checkedAt": epoch | None, "results": {plugin id: {"version", "url"} | {"error"}}}
_latest_state = None
_check_lock = threading.Lock()  # one check at a time - concurrent callers share its result
_update_lock = threading.Lock()  # one update at a time - they can touch the same files


# --- installed versions ------------------------------------------------------------------


def _read_versions_file():
    try:
        with open(PLUGIN_VERSIONS_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _record_version(plugin_id, version):
    versions = _read_versions_file()
    versions[plugin_id] = version
    os.makedirs(os.path.dirname(PLUGIN_VERSIONS_FILE), exist_ok=True)
    with open(PLUGIN_VERSIONS_FILE, "w") as f:
        json.dump(versions, f, indent=2)


def _grep_file(path, pattern):
    try:
        with open(path, "rb") as f:
            m = re.search(pattern, f.read())
        return m.group(1).decode() if m else None
    except OSError:
        return None


def _detect_metamod():
    build = _grep_file(
        os.path.join(METAMOD_DIR, "bin", "linuxsteamrt64", "metamod.2.cs2.so"), rb"2\.0\.0-dev\+(\d+)"
    )
    return f"2.0.0-dev+{build}" if build else None


def _detect_css():
    return _grep_file(
        os.path.join(CSS_DIR, "api", "CounterStrikeSharp.API.deps.json"), rb'"CounterStrikeSharp\.API/([^"]+)"'
    )


def _css_plugin_dir(name):
    """A CSS plugin's folder - or its ".disabled_" one, if switched off via Mods and Options
    (mods.py disables plugins by renaming them). None if neither exists."""
    for folder in (name, ".disabled_" + name):
        path = os.path.join(CSS_PLUGINS_DIR, folder)
        if os.path.isdir(path):
            return path
    return None


def _detect_css_plugin(name):
    plugin_dir = _css_plugin_dir(name)
    if plugin_dir is None:
        return None
    version = _grep_file(os.path.join(plugin_dir, f"{name}.info"), rb"(?m)^version:\s*(\S+)")
    return version or _grep_file(os.path.join(plugin_dir, f"{name}.deps.json"), rb'"' + name.encode() + rb'/([^"]+)"')


def _detect_meta_so(vdf_name):
    """A Metamod plugin's version, read from its binary (located via its .vdf). Builds embed
    exactly one version string, e.g. "v1.6.2-0-gd6b4f4b", "1.3.1" or "v1.0.16 @ b6c81b3"."""
    rel = _grep_file(os.path.join(METAMOD_DIR, vdf_name), rb'"file"\s+"([^"]+)"')
    if not rel:
        return None
    return _grep_file(
        os.path.join(GAME_DIR, rel + ".so"), rb"\x00v?(\d+\.\d+\.\d+)(?:-[\w.-]+| @ \w+)?\x00"
    )


def _live_meta_versions():
    """{plugin name: version} from `meta list` - only while the server is running."""
    if container_status() != "running":
        return {}
    try:
        out = rcon_command("meta list")
    except (RconError, OSError):
        return {}
    # "  [02] RayTrace (v1.0.16 @ b6c81b3) by Slynx, contributors"
    return {
        m.group(1): m.group(2).lstrip("v")
        for m in re.finditer(r"\[\d+\]\s+(.+?)\s+\(([^)\s]+)[^)]*\)\s+by\b", out)
    }


def _installed_version(plugin, recorded, live):
    if plugin["id"] in recorded:
        return recorded[plugin["id"]]
    detect = plugin.get("detect")
    version = None
    if detect == "metamod":
        version = _detect_metamod()
    elif detect == "css":
        version = _detect_css()
    elif detect == "css_plugin":
        version = _detect_css_plugin(plugin["id"])
    if not version and plugin.get("vdf"):
        version = _detect_meta_so(plugin["vdf"])
    if not version and plugin.get("meta_name"):
        version = live.get(plugin["meta_name"])
    return version


def _is_installed(plugin):
    if plugin["id"] == "metamod":
        return os.path.isdir(METAMOD_DIR)
    if plugin["id"] == "counterstrikesharp":
        return os.path.isdir(CSS_DIR)
    if plugin.get("vdf"):
        return os.path.isfile(os.path.join(METAMOD_DIR, plugin["vdf"]))
    return _css_plugin_dir(plugin["id"]) is not None


def _is_disabled(plugin):
    return plugin["kind"] == "CSS plugin" and os.path.isdir(
        os.path.join(CSS_PLUGINS_DIR, ".disabled_" + plugin["name"])
    )


def _discover_unknown():
    """Installed plugins with no known update source, so they're still listed."""
    found = []
    if os.path.isdir(METAMOD_DIR):
        for name in sorted(os.listdir(METAMOD_DIR)):
            if not name.endswith(".vdf") or name in KNOWN_VDFS:
                continue
            alias = _grep_file(os.path.join(METAMOD_DIR, name), rb'"alias"\s+"([^"]+)"') or name[:-4]
            found.append(
                {"id": f"meta:{alias}", "name": alias, "kind": "Metamod plugin", "meta_name": alias, "vdf": name}
            )
    if os.path.isdir(CSS_PLUGINS_DIR):
        for folder in sorted(os.listdir(CSS_PLUGINS_DIR)):
            name = folder[len(".disabled_") :] if folder.startswith(".disabled_") else folder
            if name in KNOWN_BY_ID or not os.path.isdir(os.path.join(CSS_PLUGINS_DIR, folder)):
                continue
            found.append({"id": f"css:{name}", "name": name, "kind": "CSS plugin", "detect": "css_plugin_dir"})
    return found


# --- latest releases ---------------------------------------------------------------------


class RateLimited(Exception):
    pass


def _http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429) and exc.headers.get("X-RateLimit-Remaining") == "0":
            reset = exc.headers.get("X-RateLimit-Reset")
            when = time.strftime("%H:%M", time.localtime(int(reset))) if reset and reset.isdigit() else "later"
            raise RateLimited(f"GitHub rate limit reached - try again after {when}") from exc
        raise


def _fetch_latest(plugin):
    source = plugin["source"]
    if source[0] == "metamod":
        filename = _http_get("https://mms.alliedmods.net/mmsdrop/2.0/mmsource-latest-linux").decode().strip()
        build = re.search(r"git(\d+)", filename).group(1)
        return {"version": f"2.0.0-dev+{build}", "url": f"https://mms.alliedmods.net/mmsdrop/2.0/{filename}"}
    _, repo, asset_re = source
    release = json.loads(_http_get(f"https://api.github.com/repos/{repo}/releases/latest"))
    for asset in release.get("assets", []):
        if re.search(asset_re, asset["name"]):
            return {"version": release["tag_name"].lstrip("v"), "url": asset["browser_download_url"]}
    raise ValueError(f"no release asset matching {asset_re} in {repo} {release['tag_name']}")


def _load_latest_state():
    global _latest_state
    if _latest_state is None:
        try:
            with open(PLUGIN_LATEST_FILE) as f:
                _latest_state = json.load(f)
        except (OSError, ValueError):
            _latest_state = {"checkedAt": None, "results": {}}
    return _latest_state


def _save_latest_state():
    os.makedirs(os.path.dirname(PLUGIN_LATEST_FILE), exist_ok=True)
    with open(PLUGIN_LATEST_FILE, "w") as f:
        json.dump(_latest_state, f, indent=2)


def check_for_updates(force=False):
    """Looks up the latest release of every known plugin. Without force, only runs if nothing
    has ever been checked. A failed lookup keeps the plugin's previous good result (with the
    error attached), and a rate limit stops the rest of the check rather than burning more
    requests. Returns an error string if the check was refused, else None."""
    with _check_lock:
        state = _load_latest_state()
        if not force and state["checkedAt"] is not None:
            return None
        if force and state["checkedAt"] and time.time() - state["checkedAt"] < MIN_CHECK_INTERVAL_SECONDS:
            return "checked less than a minute ago - try again shortly"
        results = state["results"]
        rate_limited = None
        for plugin in KNOWN_PLUGINS:
            previous = results.get(plugin["id"], {})
            if rate_limited and plugin["source"][0] == "github":
                results[plugin["id"]] = {**previous, "error": rate_limited}
                continue
            try:
                results[plugin["id"]] = _fetch_latest(plugin)
            except RateLimited as exc:
                rate_limited = str(exc)
                results[plugin["id"]] = {**previous, "error": rate_limited}
            except Exception as exc:  # network, unexpected release layout
                results[plugin["id"]] = {**previous, "error": str(exc)}
        state["checkedAt"] = time.time()
        _save_latest_state()
    return None


def _latest(plugin):
    """The cached lookup for one plugin ({} if never checked)."""
    with _check_lock:
        return dict(_load_latest_state()["results"].get(plugin["id"], {}))


def _version_key(version):
    return tuple(int(n) for n in re.findall(r"\d+", version or ""))


# --- listing -----------------------------------------------------------------------------


def list_plugins():
    check_for_updates()  # first time only - after that, the button refreshes
    recorded = _read_versions_file()
    live = _live_meta_versions()
    with _lock:
        jobs = {k: dict(v) for k, v in _jobs.items()}
    plugins = []
    # Known plugins are always listed (so an uninstalled one can be installed again);
    # discovered ones only exist because they're on disk.
    for plugin in KNOWN_PLUGINS + _discover_unknown():
        is_installed = _is_installed_entry(plugin)
        if not is_installed:
            installed = None
        elif plugin.get("detect") == "css_plugin_dir":
            installed = _detect_css_plugin(plugin["name"])
        else:
            installed = _installed_version(plugin, recorded, live)
        entry = {
            "id": plugin["id"],
            "name": plugin["name"],
            "kind": plugin["kind"],
            "isInstalled": is_installed,
            "installed": installed,
            "latest": None,
            "updateAvailable": False,
            "canUpdate": "source" in plugin,
            "canUninstall": is_installed and plugin["kind"] != "Framework",
            "source": None,
            "note": plugin.get("note"),
            "disabled": is_installed and _is_disabled(plugin),
            "error": None,
            "job": jobs.get(plugin["id"]),
        }
        if "source" in plugin:
            src = plugin["source"]
            entry["source"] = "AlliedMods dev builds" if src[0] == "metamod" else f"github.com/{src[1]}"
            latest = _latest(plugin)
            if "error" in latest:
                entry["error"] = f"Couldn't check for updates: {latest['error']}"
            if latest.get("version"):
                entry["latest"] = latest["version"]
                entry["updateAvailable"] = is_installed and (
                    installed is None or _version_key(latest["version"]) > _version_key(installed)
                )
        plugins.append(entry)
    return {
        "plugins": plugins,
        "serverRunning": container_status() == "running",
        "checkedAt": _load_latest_state()["checkedAt"],
    }


# --- updating ----------------------------------------------------------------------------


def _set_job(plugin_id, state, message=""):
    with _lock:
        _jobs[plugin_id] = {"state": state, "message": message}


def _extract(archive_path, url, stage):
    """Extracts into stage, refusing any member that would land outside it."""
    stage_real = os.path.realpath(stage)

    def safe(name):
        target = os.path.realpath(os.path.join(stage, name))
        if target != stage_real and not target.startswith(stage_real + os.sep):
            raise ValueError(f"archive member escapes the extract dir: {name}")

    if url.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as z:
            for name in z.namelist():
                safe(name)
            z.extractall(stage)
    else:
        with tarfile.open(archive_path) as t:
            for member in t.getmembers():
                safe(member.name)
                if member.issym() or member.islnk():
                    raise ValueError(f"archive contains a link: {member.name}")
            t.extractall(stage)


def _install_root(stage):
    """Works out where an archive's contents belong, from its layout:
    - addons/... at the top        -> the game dir (Metamod, CSS, most Metamod plugins)
    - one folder containing plugins/ -> addons/counterstrikesharp (mirrors CSS's own layout)
    - one folder (a CSS plugin)    -> addons/counterstrikesharp/plugins/<folder>
    Returns (source dir inside stage, destination dir)."""
    top = [n for n in os.listdir(stage) if not n.startswith("__MACOSX")]
    if "addons" in top:
        return stage, GAME_DIR
    if len(top) == 1 and os.path.isdir(os.path.join(stage, top[0])):
        inner = os.path.join(stage, top[0])
        if os.path.isdir(os.path.join(inner, "plugins")):
            return inner, CSS_DIR
        return inner, _css_plugin_dir(top[0]) or os.path.join(CSS_PLUGINS_DIR, top[0])
    raise ValueError(f"unrecognised archive layout (top level: {', '.join(sorted(top)) or 'empty'})")


def _is_config(rel):
    parts = rel.split(os.sep)
    return "configs" in parts or parts[0] == "cfg" or parts[-1] == "metaplugins.ini"


def _planned_writes(src_root, dest_root):
    """(source, destination) for every file the update will write - existing configs excluded."""
    writes = []
    for root, _, files in os.walk(src_root):
        for name in files:
            src = os.path.join(root, name)
            rel = _redirect_disabled(os.path.relpath(src, src_root), dest_root)
            dst = os.path.join(dest_root, rel)
            if _is_config(rel) and os.path.exists(dst):
                continue
            writes.append((src, dst))
    return writes


def _backup(writes, plugin_id):
    """Backs up exactly the existing files the update is about to replace."""
    existing = [dst for _, dst in writes if os.path.isfile(dst)]
    if not existing:
        return None
    os.makedirs(PLUGIN_BACKUPS_DIR, exist_ok=True)
    path = os.path.join(PLUGIN_BACKUPS_DIR, f"{plugin_id}-{time.strftime('%Y%m%d-%H%M%S')}.tar.gz")
    with tarfile.open(path, "w:gz", compresslevel=1) as t:
        for dst in existing:
            t.add(dst, arcname=os.path.relpath(dst, GAME_DIR))
    backups = sorted(
        (f for f in os.listdir(PLUGIN_BACKUPS_DIR) if f.startswith(f"{plugin_id}-")), reverse=True
    )
    for old in backups[BACKUPS_TO_KEEP:]:
        os.remove(os.path.join(PLUGIN_BACKUPS_DIR, old))
    return path


def _redirect_disabled(rel, dest_root):
    """plugins/<Name>/... -> plugins/.disabled_<Name>/... when only the disabled folder exists,
    so updating a switched-off plugin doesn't install a second, enabled copy beside it."""
    parts = rel.split(os.sep)
    if os.path.realpath(dest_root) == os.path.realpath(CSS_DIR) and len(parts) > 2 and parts[0] == "plugins":
        enabled = os.path.join(CSS_PLUGINS_DIR, parts[1])
        disabled = os.path.join(CSS_PLUGINS_DIR, ".disabled_" + parts[1])
        if not os.path.exists(enabled) and os.path.isdir(disabled):
            parts[1] = ".disabled_" + parts[1]
    return os.path.join(*parts)


def _apply(writes):
    """Swaps each file in with an atomic rename, so a running server keeps its loaded copy."""
    for src, dst in writes:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".update-tmp"
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)


PT_GNU_STACK, PF_X = 0x6474E551, 0x1


def _clear_exec_stack_flags():
    """What `execstack -c` does: clear PF_X on the PT_GNU_STACK header of 64-bit ELF .so files."""
    fixed = []
    for root, _, files in os.walk(ADDONS_DIR):
        for name in files:
            if not name.endswith(".so"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "r+b") as f:
                    ident = f.read(16)
                    if ident[:4] != b"\x7fELF" or ident[4] != 2:
                        continue
                    f.seek(0x20)
                    (phoff,) = struct.unpack("<Q", f.read(8))
                    f.seek(0x36)
                    phentsize, phnum = struct.unpack("<HH", f.read(4))
                    for i in range(phnum):
                        off = phoff + i * phentsize
                        f.seek(off)
                        p_type, p_flags = struct.unpack("<II", f.read(8))
                        if p_type == PT_GNU_STACK and p_flags & PF_X:
                            f.seek(off + 4)
                            f.write(struct.pack("<I", p_flags & ~PF_X))
                            fixed.append(os.path.relpath(path, GAME_DIR))
            except (OSError, struct.error):
                continue
    return fixed


def _ensure_gameinfo_metamod():
    """CS2 updates can replace gameinfo.gi and drop Metamod's search path."""
    try:
        with open(GAMEINFO_FILE) as f:
            lines = f.read().splitlines()
    except OSError:
        return False
    if any(re.match(r"\s*Game\s+csgo/addons/metamod\b", line) for line in lines):
        return False
    for i, line in enumerate(lines):
        if re.match(r"\s*Game_LowViolence\s", line):
            lines.insert(i + 1, "\t\t\tGame\tcsgo/addons/metamod")
            with open(GAMEINFO_FILE, "w") as f:
                f.write("\n".join(lines) + "\n")
            return True
    return False


def _run_update(plugin):
    plugin_id = plugin["id"]
    with _update_lock:
        try:
            was_installed = _is_installed(plugin)
            _set_job(plugin_id, "updating", "Checking latest release...")
            latest = _latest(plugin)
            if not latest.get("url"):
                latest = _fetch_latest(plugin)
            with tempfile.TemporaryDirectory() as work:
                _set_job(plugin_id, "updating", f"Downloading {latest['version']}...")
                archive = os.path.join(work, "download")
                with open(archive, "wb") as f:
                    f.write(_http_get(latest["url"]))
                stage = os.path.join(work, "stage")
                os.makedirs(stage)
                _extract(archive, latest["url"], stage)
                src_root, dest_root = _install_root(stage)

                writes = _planned_writes(src_root, dest_root)
                total = sum(len(files) for _, _, files in os.walk(src_root))
                _set_job(plugin_id, "updating", "Backing up current files...")
                _backup(writes, plugin_id)

                _set_job(plugin_id, "updating", "Installing...")
                _apply(writes)
                copied, kept = len(writes), total - len(writes)
            fixed = _clear_exec_stack_flags()
            gameinfo_fixed = plugin_id == "metamod" and _ensure_gameinfo_metamod()
            _record_version(plugin_id, latest["version"])

            verb = "Updated to" if was_installed else "Installed"
            parts = [f"{verb} {latest['version']} ({copied} files, {kept} configs kept)"]
            if fixed:
                parts.append(f"cleared executable-stack flag on {len(fixed)} file(s)")
            if gameinfo_fixed:
                parts.append("re-added Metamod to gameinfo.gi")
            if container_status() == "running":
                parts.append("restart the server to load it")
            _set_job(plugin_id, "done", " - ".join(parts))
        except Exception as exc:
            _set_job(plugin_id, "error", f"Update failed: {exc}")


def start_update(plugin_id):
    """Kicks off a background update. Returns an error string, or None if it started."""
    plugin = KNOWN_BY_ID.get(plugin_id)
    if plugin is None:
        return "no update source for that plugin"
    with _lock:
        job = _jobs.get(plugin_id)
        if job and job["state"] == "updating":
            return "already updating"
        if any(j["state"] == "updating" for j in _jobs.values()):
            # Queued behind the running one via _update_lock - say so rather than look stuck.
            _jobs[plugin_id] = {"state": "updating", "message": "Waiting for another update to finish..."}
    threading.Thread(target=_run_update, args=(plugin,), daemon=True).start()
    return None


# --- uninstalling ------------------------------------------------------------------------


def _resolve(plugin_id):
    """A plugin entry by id - known ones plus discovered "meta:"/"css:" ones."""
    for plugin in KNOWN_PLUGINS + _discover_unknown():
        if plugin["id"] == plugin_id and _is_installed_entry(plugin):
            return plugin
    return None


def _is_installed_entry(plugin):
    if plugin["id"] in KNOWN_BY_ID:
        return _is_installed(plugin)
    return True  # discovered entries only exist because they're on disk


def _uninstall_paths(plugin):
    """What to delete: a CSS plugin's folder, or a Metamod plugin's .vdf plus its own
    addons/<name>/ folder (taken from the .vdf's "file" path). Configs (configs/, cfg/) and
    CSS shared/ libraries are deliberately left - other plugins may use them, and keeping
    configs means a reinstall picks up the old settings."""
    if plugin["kind"] == "CSS plugin":
        folder = _css_plugin_dir(plugin["name"])
        return [folder] if folder else []
    vdf = plugin.get("vdf")
    if not vdf:
        return []
    paths = [os.path.join(METAMOD_DIR, vdf)]
    rel = _grep_file(os.path.join(METAMOD_DIR, vdf), rb'"file"\s+"([^"]+)"') or ""
    parts = rel.split("/")
    # addons/<name>/bin/... -> addons/<name>, but never the shared Metamod/CSS folders
    if len(parts) > 2 and parts[0] == "addons" and parts[1] not in ("metamod", "counterstrikesharp", "configs"):
        own_dir = os.path.join(ADDONS_DIR, parts[1])
        if os.path.isdir(own_dir):
            paths.append(own_dir)
    return [p for p in paths if os.path.exists(p)]


def uninstall(plugin_id):
    """Removes a plugin after backing it up. Returns (message, error) - one of them None."""
    plugin = _resolve(plugin_id)
    if plugin is None:
        return None, "plugin not found"
    if plugin["kind"] == "Framework":
        return None, f"{plugin['name']} can't be uninstalled from here - every plugin depends on it"
    if not _update_lock.acquire(blocking=False):
        return None, "an update is running - try again once it's finished"
    try:
        paths = _uninstall_paths(plugin)
        if not paths:
            return None, "couldn't work out which files belong to that plugin"
        files = []
        for path in paths:
            if os.path.isdir(path):
                files.extend(os.path.join(root, name) for root, _, names in os.walk(path) for name in names)
            else:
                files.append(path)
        backup_id = plugin_id.replace(":", "_")
        _backup([(None, f) for f in files], f"{backup_id}-uninstall")
        for path in paths:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        versions = _read_versions_file()
        if versions.pop(plugin_id, None) is not None:
            with open(PLUGIN_VERSIONS_FILE, "w") as f:
                json.dump(versions, f, indent=2)
        with _lock:
            _jobs.pop(plugin_id, None)
        message = f"Uninstalled {plugin['name']} (backup kept, configs left in place)"
        if container_status() == "running":
            message += " - it stays loaded until the server restarts"
        return message, None
    except OSError as exc:
        return None, f"uninstall failed: {exc}"
    finally:
        _update_lock.release()
