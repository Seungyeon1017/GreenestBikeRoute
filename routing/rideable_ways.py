"""OSM ways we ride although OSM doesn't say bikes may (footways without a bicycle tag).

Checked by hand, one per entry with why, in data/custom/rideable_ways.json. Routing treats them like footways tagged
bicycle=yes. Users report such ways in the app (POST /reports/mapping); once checked, `python -m backend.reports
approve` adds them here. The graph in cache/ is rebuilt on the next start when the list changed (routing.graph).
"""
import json
from pathlib import Path

RIDEABLE_WAYS_PATH = Path(__file__).resolve().parent.parent / "data" / "custom" / "rideable_ways.json"


def load_rideable_ways(path=RIDEABLE_WAYS_PATH):
    """{OSM way id: why it is rideable}, or {} if the file is missing."""
    path = Path(path)
    return {int(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()} if path.exists() else {}


def add_rideable_way(way_id, reason, path=RIDEABLE_WAYS_PATH):
    """Add (or re-word) one way in the list file; returns the new list."""
    ways = {**load_rideable_ways(path), int(way_id): reason}
    Path(path).write_text(json.dumps({str(k): v for k, v in sorted(ways.items())}, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    return ways


RIDEABLE_WAYS = load_rideable_ways()
