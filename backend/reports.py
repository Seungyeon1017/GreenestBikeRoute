"""Crowdsourced reports: streets that are temporarily closed, and mapping mistakes in OSM.

Closures: Heilbronn publishes no live data on closed streets, so riders report them. A report is put on the street
segment (graph edge between two junctions) nearest to it. A segment with CLOSED_AT independent reports within
WINDOW_S is closed: routes don't use it. With fewer, it is only "reported" and costs more (routing.route
REPORTED_CLOSED_FACTOR), since with few users the third report may never come. Reports older than WINDOW_S drop out,
so a closure ends by itself unless riders keep reporting it. Independent means from different reporters (the app's
anonymous `reporter_id`) and from different networks (salted hash of the client IP): one person can't close a street
alone by changing their id. This is a light guard, not protection against a determined attacker.

Mapping reports: footways that bikes ride on although OSM doesn't say so, or other mistakes. They are kept for a
maintainer to check; approving a "rideable" one adds its way to routing/rideable_ways.py's list:

    python -m backend.reports list
    python -m backend.reports approve 7 --way 286359672 --reason "footway next to the tram lane, cyclists use it"
    python -m backend.reports reject 8
"""
import argparse
import hashlib
import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone

from download_data import DATA_DIR
from routing.rideable_ways import RIDEABLE_WAYS_PATH, add_rideable_way

REPORTS_PATH = DATA_DIR / "reports.sqlite3"
WINDOW_S = 2 * 3600  # a closure report counts this long
CLOSED_AT = 3        # independent reports within WINDOW_S that close a segment
SNAP_M = 50          # a closure report further than this from every street is refused
MAPPING_KINDS = ("rideable", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS closure_reports (
    id INTEGER PRIMARY KEY, created REAL NOT NULL, u INTEGER NOT NULL, v INTEGER NOT NULL, osm_way_ids TEXT NOT NULL,
    lon REAL NOT NULL, lat REAL NOT NULL, reporter TEXT NOT NULL, client TEXT NOT NULL, note TEXT);
CREATE INDEX IF NOT EXISTS closure_reports_created ON closure_reports (created);
CREATE TABLE IF NOT EXISTS mapping_reports (
    id INTEGER PRIMARY KEY, created REAL NOT NULL, kind TEXT NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL,
    osm_way_id INTEGER, note TEXT, reporter TEXT NOT NULL, client TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', resolved REAL);
"""


class ReportError(ValueError):
    """The report can't be taken (off the map, unknown id, ...)."""


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")


class Reports:
    """The report store, an SQLite file (default REPORTS_PATH; ":memory:" in tests). `clock` returns Unix time (tests
    pass a fake)."""

    def __init__(self, path=None, clock=time.time):
        path = REPORTS_PATH if path is None else path
        self.clock = clock
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self.lock, self.db:
            self.db.executescript(SCHEMA)
            self.db.execute("INSERT OR IGNORE INTO meta VALUES ('salt', ?)", (secrets.token_hex(16),))
            self.salt = self.db.execute("SELECT value FROM meta WHERE key = 'salt'").fetchone()[0]

    def _client(self, ip):
        """The client IP, salted and hashed: enough to tell networks apart without storing addresses."""
        return hashlib.sha256(f"{self.salt}:{ip}".encode()).hexdigest()[:16]

    # --- closures ---------------------------------------------------------------------------------------------

    def report_closure(self, u, v, osm_way_ids, lonlat, reporter_id, ip, note=None):
        """Store one report that segment u-v is closed; returns that segment's state (see closure_state)."""
        client = self._client(ip)
        u, v = min(u, v), max(u, v)
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO closure_reports (created, u, v, osm_way_ids, lon, lat, reporter, client, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (self.clock(), u, v, json.dumps(list(osm_way_ids)), *lonlat, reporter_id or client, client, note))
        return self.closure_states()[(u, v)]

    def closure_states(self):
        """{(u, v): state} of every segment with a report within WINDOW_S, u < v. A state has `reports` (independent
        ones: the fewer of distinct reporters and distinct networks), `status` ("closed" from CLOSED_AT reports, else
        "reported"), `osm_way_ids`, `last_report` and `expires` (ISO 8601 UTC, when its last report drops out)."""
        since = self.clock() - WINDOW_S
        with self.lock:
            rows = self.db.execute("SELECT * FROM closure_reports WHERE created >= ? ORDER BY created", (since,)).fetchall()
        segments = {}
        for r in rows:
            segments.setdefault((r["u"], r["v"]), []).append(r)
        states = {}
        for key, reports in segments.items():
            n = min(len({r["reporter"] for r in reports}), len({r["client"] for r in reports}))
            last = reports[-1]["created"]
            states[key] = {"status": "closed" if n >= CLOSED_AT else "reported", "reports": n,
                           "osm_way_ids": json.loads(reports[-1]["osm_way_ids"]),
                           "last_report": _iso(last), "expires": _iso(last + WINDOW_S)}
        return states

    def closures(self):
        """{(u, v): "closed" | "reported"}, for routing.route.set_closures."""
        return {key: s["status"] for key, s in self.closure_states().items()}

    # --- mapping mistakes ---------------------------------------------------------------------------------------

    def report_mapping(self, kind, lonlat, reporter_id, ip, osm_way_id=None, note=None):
        """Store one mapping report (pending until a maintainer checks it); returns it as from mapping_reports."""
        if kind not in MAPPING_KINDS:
            raise ReportError(f"kind must be one of {', '.join(MAPPING_KINDS)}")
        client = self._client(ip)
        with self.lock, self.db:
            cur = self.db.execute(
                "INSERT INTO mapping_reports (created, kind, lon, lat, osm_way_id, note, reporter, client) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (self.clock(), kind, *lonlat, osm_way_id, note, reporter_id or client, client))
        return self.mapping_report(cur.lastrowid)

    def mapping_reports(self, status="pending"):
        """The mapping reports with `status` (pending, approved, rejected, or all), oldest first."""
        query = "SELECT * FROM mapping_reports" + ("" if status == "all" else " WHERE status = ?") + " ORDER BY id"
        with self.lock:
            rows = self.db.execute(query, () if status == "all" else (status,)).fetchall()
        return [self._mapping(r) for r in rows]

    def mapping_report(self, report_id):
        with self.lock:
            row = self.db.execute("SELECT * FROM mapping_reports WHERE id = ?", (report_id,)).fetchone()
        if row is None:
            raise ReportError(f"no mapping report {report_id}")
        return self._mapping(row)

    @staticmethod
    def _mapping(r):
        return {"id": r["id"], "kind": r["kind"], "lon": r["lon"], "lat": r["lat"], "osm_way_id": r["osm_way_id"],
                "note": r["note"], "status": r["status"], "created": _iso(r["created"]),
                "resolved": None if r["resolved"] is None else _iso(r["resolved"])}

    def approve_mapping(self, report_id, way_id=None, reason=None, rideable_path=RIDEABLE_WAYS_PATH):
        """Mark a mapping report approved. A "rideable" one adds its way (`way_id`, or the one the reporter gave) to
        the RIDEABLE_WAYS list with `reason` (default: the report's note); routing picks it up on the next start."""
        report = self.mapping_report(report_id)
        if report["kind"] == "rideable":
            way_id = way_id or report["osm_way_id"]
            if way_id is None:
                raise ReportError(f"report {report_id} names no OSM way: give one")
            reason = reason or report["note"]
            if not reason:
                raise ReportError(f"report {report_id} has no note: give a reason why the way is rideable")
            add_rideable_way(way_id, f"{reason} (user report {report_id})", rideable_path)
        self._resolve(report_id, "approved", way_id)
        return self.mapping_report(report_id)

    def reject_mapping(self, report_id):
        self.mapping_report(report_id)
        self._resolve(report_id, "rejected")
        return self.mapping_report(report_id)

    def _resolve(self, report_id, status, way_id=None):
        with self.lock, self.db:
            self.db.execute("UPDATE mapping_reports SET status = ?, resolved = ?, osm_way_id = COALESCE(?, osm_way_id) "
                            "WHERE id = ?", (status, self.clock(), way_id, report_id))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the users' mapping reports.")
    sub = parser.add_subparsers(dest="command", required=True)
    ls = sub.add_parser("list", help="list mapping reports")
    ls.add_argument("--status", default="pending", choices=["pending", "approved", "rejected", "all"])
    ok = sub.add_parser("approve", help="approve a report; a 'rideable' one is added to data/custom/rideable_ways.json")
    ok.add_argument("id", type=int)
    ok.add_argument("--way", type=int, help="the OSM way id, if the reporter gave none or the wrong one")
    ok.add_argument("--reason", help="why bikes may ride it (default: the reporter's note)")
    no = sub.add_parser("reject", help="reject a report")
    no.add_argument("id", type=int)
    args = parser.parse_args(argv)

    reports = Reports()
    try:
        if args.command == "list":
            for r in reports.mapping_reports(args.status):
                print(f"{r['id']:>4} {r['status']:<8} {r['kind']:<8} {r['lat']:.6f},{r['lon']:.6f} "
                      f"way {r['osm_way_id'] or '?'}  {r['note'] or ''}")
        elif args.command == "approve":
            r = reports.approve_mapping(args.id, args.way, args.reason)
            print(f"approved {r['id']}" + (f": way {r['osm_way_id']} is rideable from the next server start"
                                           if r["kind"] == "rideable" else ""))
        else:
            print(f"rejected {reports.reject_mapping(args.id)['id']}")
    except ReportError as e:
        parser.exit(1, f"error: {e}\n")


if __name__ == "__main__":
    main()
