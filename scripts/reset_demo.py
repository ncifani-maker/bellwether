#!/usr/bin/env python3
"""
reset_demo.py — put a demo brief's seed list back the way it started.

A rehearsal changes a demo: approving /snowball's picks adds seeds, and a scan
marks seeds done, so the next run on stage would see a different list. A demo
brief keeps a snapshot, briefs/<slug>/raw/seeds.baseline.csv, and this copies it back
over seeds.csv. Nothing else is touched: the morning's /snowball read is kept, so
the stage run still reuses it (CHANGELOG D23).

Only briefs with a baseline can be reset. A real brief has none, so a real seed
list can never be reset by accident.

Usage:
  python3 scripts/reset_demo.py braise --dry-run
  python3 scripts/reset_demo.py braise
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def statuses(path):
    with path.open() as fh:
        rows = list(csv.DictReader(l for l in fh if not l.startswith("#")))
    return {r["keyword"]: r["status"] for r in rows}


def main():
    ap = argparse.ArgumentParser(description="Restore a demo brief's seeds.csv from its baseline.")
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true", help="show what would change; change nothing")
    args = ap.parse_args()

    folder = ROOT / "briefs" / args.slug
    seeds = folder / "seeds.csv"
    base = folder / "raw" / "seeds.baseline.csv"
    if not base.exists():
        base = folder / "seeds.baseline.csv"     # where it lived before CHANGELOG D25
    if not base.exists():
        sys.exit("briefs/{}/ has no raw/seeds.baseline.csv, so it isn't a demo brief. Nothing reset.".format(args.slug))

    now = statuses(seeds) if seeds.exists() else {}
    then = statuses(base)
    added = sorted(set(now) - set(then))
    changed = sorted(k for k in set(now) & set(then) if now[k] != then[k])
    print("Reset · {} · seeds.csv back to its baseline".format(args.slug))
    print("  removes {} seed(s) added since: {}".format(len(added), ", ".join(added) or "-"))
    print("  restores {} status(es): {}".format(
        len(changed), ", ".join("{} ({} -> {})".format(k, now[k], then[k]) for k in changed) or "-"))
    if args.dry_run:
        print("dry run — nothing changed.")
        return 0
    shutil.copyfile(base, seeds)
    print("  now: {}".format(dict(Counter(then.values()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
