"""Crowdsourced reports: streets that are temporarily closed, and mapping mistakes in OSM.

Closures: Heilbronn publishes no live data on closed streets, so riders report them. A report is put on the street
segment (graph edge between two junctions) nearest to it. A segment with CLOSED_AT live independent reports is
closed: routes don't use it. With fewer, it is only "reported" and costs more (routing.route REPORTED_CLOSED_FACTOR),
since with few users the third report may never come.

Once a street shows as closed, nobody reports it again and routes send nobody past it, so reports can't simply
expire after a fixed time. Instead:
- the reporter can say until when it is closed (the date on the sign); the report lives that long, at most MAX_S,
  else DEFAULT_S;
- riders confirm with one tap ("still closed", which counts as a new report) or say it is open again: OPEN_AT
  independent "open" answers lift it, and a later "still closed" voids earlier "open" answers;
- when all reports have lapsed it stays "unconfirmed" for GRACE_S: routes still avoid it and the app asks riders
  whose trip starts or ends nearby, rather than sending them into the building site.

Independent means from different reporters (the app's anonymous `reporter_id`) and from different networks (salted
hash of the client IP): one person can't close or open a street alone by changing their id. This is a light guard,
not protection against a determined attacker.

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
from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from download_data import DATA_DIR
from routing.rideable_ways import RIDEABLE_WAYS_PATH, add_rideable_way

REPORTS_PATH = DATA_DIR / "reports.sqlite3"
DEFAULT_S = 24 * 3600    # a closed report without an end date lives this long
MAX_S = 30 * 24 * 3600   # and one with an end date at most this long
GRACE_S = 3 * 24 * 3600  # after the last report lapses, the closure stays "unconfirmed" this long
CLOSED_AT = 3            # live independent reports that close a segment
OPEN_AT = 2              # independent "open again" answers that lift a closure
LOCAL_TZ = ZoneInfo("Europe/Berlin")  # end dates are Heilbronn days
SNAP_M = 50          # a closure report further than this from every street is refused
MAPPING_KINDS = ("rideable", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS closure_reports (
    id INTEGER PRIMARY KEY, created REAL NOT NULL, u INTEGER NOT NULL, v INTEGER NOT NULL, osm_way_ids TEXT NOT NULL,
    lon REAL NOT NULL, lat REAL NOT NULL, reporter TEXT NOT NULL, client TEXT NOT NULL, note TEXT,
    kind TEXT NOT NULL DEFAULT 'closed', until REAL);
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


def _independent(reports):
    """How many of `reports` are independent: the fewer of distinct reporters and distinct networks."""
    return min(len({r["reporter"] for r in reports}), len({r["client"] for r in reports}))


def _lapses(r):
    """When a closed report stops counting: its end date, else DEFAULT_S after it came in; at most MAX_S."""
    return min(r["until"] or r["created"] + DEFAULT_S, r["created"] + MAX_S)


def _segment_state(reports, now):
    """The state of one segment (see Reports.closure_states) from its reports, oldest first; status "open" if riders
    lifted it, None if it has nothing left to show."""
    closed, opened = [], []
    for r in reports:
        if r["kind"] == "closed":
            closed.append(r)
            opened = []  # "still closed" voids earlier "open" answers
        else:
            opened.append(r)
            if _independent(opened) >= OPEN_AT:
                closed, opened = [], []
    last = reports[-1]
    open_reports = _independent(opened) if opened else 0
    if not closed:
        return {"status": "open", "reports": 0, "open_reports": open_reports,
                "osm_way_ids": json.loads(last["osm_way_ids"]), "note": None,
                "last_report": _iso(last["created"]), "expires": _iso(last["created"])}
    expires = max(_lapses(r) for r in closed)
    live = [r for r in closed if _lapses(r) > now]
    if not live and now >= expires + GRACE_S:
        return None
    n = _independent(live) if live else 0
    return {"status": "unconfirmed" if not live else "closed" if n >= CLOSED_AT else "reported",
            "reports": n, "open_reports": open_reports,
            "osm_way_ids": json.loads(closed[-1]["osm_way_ids"]),
            "note": next((r["note"] for r in reversed(closed) if r["note"]), None),
            "last_report": _iso(last["created"]), "expires": _iso(expires)}


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
            # Files made before closures had end dates and "open again" answers.
            columns = {c[1] for c in self.db.execute("PRAGMA table_info(closure_reports)")}
            if "kind" not in columns:
                self.db.execute("ALTER TABLE closure_reports ADD COLUMN kind TEXT NOT NULL DEFAULT 'closed'")
            if "until" not in columns:
                self.db.execute("ALTER TABLE closure_reports ADD COLUMN until REAL")
            self.db.execute("INSERT OR IGNORE INTO meta VALUES ('salt', ?)", (secrets.token_hex(16),))
            self.salt = self.db.execute("SELECT value FROM meta WHERE key = 'salt'").fetchone()[0]

    def _client(self, ip):
        """The client IP, salted and hashed: enough to tell networks apart without storing addresses."""
        return hashlib.sha256(f"{self.salt}:{ip}".encode()).hexdigest()[:16]

    # --- closures ---------------------------------------------------------------------------------------------

    def report_closure(self, u, v, osm_way_ids, lonlat, reporter_id, ip, note=None, until=None, still_closed=True):
        """Store one report on segment u-v: closed (a new report, or "still closed" on a known closure), or open again
        with still_closed=False. `until` is the date the reporter expects it to end (e.g. from the sign), Heilbronn
        time; the closure then lasts through that day, at most MAX_S. Returns the segment's state (see
        closure_states), with status "open" if the closure was lifted."""
        now = self.clock()
        end = None
        if until is not None:
            end = datetime.combine(until + timedelta(days=1), dt_time(), LOCAL_TZ).timestamp()
            if end <= now:
                raise ReportError("until is in the past")
        client = self._client(ip)
        u, v = min(u, v), max(u, v)
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO closure_reports (created, u, v, osm_way_ids, lon, lat, reporter, client, note, kind, until) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (now, u, v, json.dumps(list(osm_way_ids)), *lonlat, reporter_id or client, client, note,
                 "closed" if still_closed else "open", end))
        return self._states(include_open=True)[(u, v)]

    def closure_states(self):
        """{(u, v): state} of every segment riders say is closed, u < v. A state has:

        - `status`: "closed" with CLOSED_AT or more live reports (routes don't use it), "reported" with fewer (routes
          avoid it), "unconfirmed" when all reports have lapsed but less than GRACE_S ago (routes still avoid it,
          and the app asks riders whether it is still closed).
        - `reports`: live closed reports, independent ones only (the fewer of distinct reporters and networks). A
          report lives until the date its reporter gave, else DEFAULT_S, at most MAX_S. "Still closed" counts as one.
        - `open_reports`: independent riders who said it is open again since the last closed report; OPEN_AT lift it.
        - `osm_way_ids`, `note` (the latest one), `last_report` and `expires` (when the last report lapses), ISO 8601 UTC.
        """
        return self._states()

    def _states(self, include_open=False):
        now = self.clock()
        with self.lock:
            rows = self.db.execute("SELECT * FROM closure_reports WHERE created >= ? ORDER BY created, id",
                                   (now - MAX_S - GRACE_S,)).fetchall()
        segments = {}
        for r in rows:
            segments.setdefault((r["u"], r["v"]), []).append(r)
        states = {}
        for key, reports in segments.items():
            state = _segment_state(reports, now)
            if state is not None and (include_open or state["status"] != "open"):
                states[key] = state
        return states

    def closures(self):
        """{(u, v): "closed" | "reported" | "unconfirmed"}, for routing.route.set_closures."""
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
