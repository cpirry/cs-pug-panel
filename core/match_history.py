# match_history.py
# Purpose: SQLite-backed match history - ingests server logs into a database and serves
# them back out to the panel's API.
#
# Ingestion is driven entirely by log file content (see match_log_parser.py), not by any
# live "a match started/stopped" bookkeeping from the lobby - scan_and_ingest() just looks
# at every log file in LOGS_DIR and inserts whichever ones aren't already in the database
# yet. That makes it work identically whether it's called right after a match ends or run
# once, later, over a backlog of log files nobody was tracking - there's no difference
# between "live" and "retroactive" ingestion.

import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta

from .constants import DEMOS_DIR, LOGS_DIR, MATCHES_DB_FILE
from .match_log_parser import parse_log_file

DEMO_FILENAME_RE = re.compile(r"^auto-(\d{8})-(\d{4})-(.+)-[^-]+\.dem$")
DEMO_MATCH_SLACK = timedelta(minutes=10)


def _connect():
    conn = sqlite3.connect(MATCHES_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    os.makedirs(os.path.dirname(MATCHES_DB_FILE), exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY,
                log_file TEXT UNIQUE NOT NULL,
                demo_file TEXT,
                map TEXT NOT NULL,
                score_ct INTEGER NOT NULL,
                score_t INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS match_players (
                match_id TEXT NOT NULL REFERENCES matches(id),
                steam_id TEXT NOT NULL,
                name TEXT NOT NULL,
                team TEXT NOT NULL,
                kills INTEGER NOT NULL,
                deaths INTEGER NOT NULL,
                assists INTEGER NOT NULL,
                headshots INTEGER NOT NULL,
                damage_dealt INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # No migration framework here - CREATE TABLE IF NOT EXISTS is a no-op on a table
        # that already exists, so a column added to the statement above never reaches a
        # database that predates it. Patch existing databases up by hand instead.
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(match_players)")}
        if "damage_dealt" not in existing_cols:
            conn.execute("ALTER TABLE match_players ADD COLUMN damage_dealt INTEGER NOT NULL DEFAULT 0")


def _find_demo(map_name, started_at, ended_at):
    if not os.path.isdir(DEMOS_DIR):
        return None
    window_start = started_at - DEMO_MATCH_SLACK
    window_end = ended_at + DEMO_MATCH_SLACK
    # A session can produce more than one demo file sharing the same minute-level
    # timestamp - e.g. a brief "_empty_" recording from the few seconds before the real map
    # finishes loading, immediately followed by the real match's recording. Timestamp alone
    # can't tell those apart, so prefer a filename whose embedded map name matches this
    # match's actual map; only fall back to timestamp-only if nothing matches by name.
    fallback = None
    for name in sorted(os.listdir(DEMOS_DIR)):
        dm = DEMO_FILENAME_RE.match(name)
        if not dm:
            continue
        try:
            demo_ts = datetime.strptime(dm.group(1) + dm.group(2), "%Y%m%d%H%M")
        except ValueError:
            continue
        if not (window_start <= demo_ts <= window_end):
            continue
        if dm.group(3) == map_name:
            return name
        if fallback is None:
            fallback = name
    return fallback


def scan_and_ingest():
    """Parses any log file not already recorded, inserting a new match row (with a fresh
    UUID) for each one that actually contains a real match. Safe to call repeatedly - already
    seen log files are skipped via the UNIQUE constraint on log_file, checked up front."""
    if not os.path.isdir(LOGS_DIR):
        return
    with _connect() as conn:
        known = {row[0] for row in conn.execute("SELECT log_file FROM matches")}

    log_files = sorted(f for f in os.listdir(LOGS_DIR) if f.endswith(".log"))
    for log_file in log_files:
        if log_file in known:
            continue
        result = parse_log_file(os.path.join(LOGS_DIR, log_file))
        if result is None:
            continue  # no real match in this file (empty boot, abandoned false start, etc.)

        demo_file = _find_demo(result["map"], result["started_at"], result["ended_at"])
        match_id = str(uuid.uuid4())
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO matches (id, log_file, demo_file, map, score_ct, score_t, started_at, ended_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    log_file,
                    demo_file,
                    result["map"],
                    result["score_ct"],
                    result["score_t"],
                    result["started_at"].isoformat(),
                    result["ended_at"].isoformat(),
                ),
            )
            conn.executemany(
                """
                INSERT INTO match_players (match_id, steam_id, name, team, kills, deaths, assists, headshots, damage_dealt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        match_id,
                        p["steam_id"],
                        p["name"],
                        p["team"],
                        p["kills"],
                        p["deaths"],
                        p["assists"],
                        p["headshots"],
                        p["damage_dealt"],
                    )
                    for p in result["players"]
                ],
            )


def list_matches():
    scan_and_ingest()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.map, m.score_ct, m.score_t, m.started_at,
                   (SELECT COUNT(*) FROM match_players WHERE match_id = m.id) AS player_count
            FROM matches m
            ORDER BY m.started_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _with_derived_stats(player, rounds_played):
    """K/D, ADR and headshot % are computed here rather than stored, so they can never drift
    out of sync with the raw counts they're based on."""
    p = dict(player)
    p["kd_ratio"] = round(p["kills"] / p["deaths"], 2) if p["deaths"] else float(p["kills"])
    p["headshot_pct"] = round(100 * p["headshots"] / p["kills"], 1) if p["kills"] else 0.0
    p["adr"] = round(p["damage_dealt"] / rounds_played, 1) if rounds_played else 0.0
    return p


def get_match(match_id):
    scan_and_ingest()
    with _connect() as conn:
        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if match is None:
            return None
        players = conn.execute(
            "SELECT steam_id, name, team, kills, deaths, assists, headshots, damage_dealt FROM match_players WHERE match_id = ? ORDER BY kills DESC",
            (match_id,),
        ).fetchall()
    result = dict(match)
    rounds_played = result["score_ct"] + result["score_t"]
    result["players"] = [_with_derived_stats(dict(p), rounds_played) for p in players]
    return result


def demo_download_name(match):
    """The on-disk demo filename (auto-<timestamp>-<map>-<servername>.dem) stays as-is in
    the filesystem - this is just the friendlier name offered to the browser on download."""
    started = datetime.fromisoformat(match["started_at"])
    return f"shedserver_{started:%y%m%d}_{started:%H%M}_{match['map']}.dem"


def get_match_file_path(match_id, kind):
    """kind is 'log' or 'demo'. Returns the absolute file path, or None if there's no such
    match or no file recorded for it."""
    column = "log_file" if kind == "log" else "demo_file"
    base_dir = LOGS_DIR if kind == "log" else DEMOS_DIR
    with _connect() as conn:
        row = conn.execute(f"SELECT {column} FROM matches WHERE id = ?", (match_id,)).fetchone()
    if row is None or row[0] is None:
        return None
    return os.path.join(base_dir, row[0])
