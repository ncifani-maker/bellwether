#!/usr/bin/env python3
"""
seed_status.py — approve, hold or retire seeds, with the reason written down.

The seed list is a gate: only `approved` rows run. Approving is Nicole's call;
this records it, with a date, so the file says who decided what and when.
Retiring always needs a reason, because why a seed was dropped is the part
worth keeping ("SERP is competitor service pages", "homonym: a Greek chant").

Usage:
  python3 scripts/seed_status.py covey approve --all-proposed
  python3 scripts/seed_status.py covey approve "best supplements for busy moms" "subscription vitamins for women"
  python3 scripts/seed_status.py covey retire "women's multivitamin reviews" --reason "retail-dominated SERP"
  python3 scripts/seed_status.py covey hold "Hungryroot reviews" --reason "waiting for the SerpAPI reset"
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = {"approve": "approved", "hold": "proposed", "retire": "retired"}


def main():
    ap = argparse.ArgumentParser(description="Approve, hold or retire seeds in briefs/<slug>/seeds.csv.")
    ap.add_argument("slug")
    ap.add_argument("action", choices=sorted(STATUS))
    ap.add_argument("keywords", nargs="*", help="exact seed text; quote each")
    ap.add_argument("--all-proposed", action="store_true", help="every `proposed` seed")
    ap.add_argument("--reason", default="", help="required for retire")
    ap.add_argument("--by", default="Nicole", help="who decided (default Nicole)")
    ap.add_argument("--seeds", type=Path, help="override the seeds file (for testing)")
    args = ap.parse_args()

    if args.action == "retire" and not args.reason:
        sys.exit("retire needs --reason: why a seed was dropped is the useful part")
    if not args.keywords and not args.all_proposed:
        sys.exit("name the seeds, or pass --all-proposed")

    path = args.seeds or ROOT / "briefs" / args.slug / "seeds.csv"
    with path.open() as fh:
        lines = fh.readlines()
    head = [l for l in lines if l.startswith("#")]
    rows = list(csv.DictReader(l for l in lines if not l.startswith("#")))
    fields = list(rows[0].keys())

    wanted = {k.strip().lower() for k in args.keywords}
    matched, missing = 0, set(wanted)
    today = date.today().isoformat()
    for r in rows:
        key = r["keyword"].strip().lower()
        hit = key in wanted or (args.all_proposed and r.get("status") == "proposed")
        if not hit:
            continue
        missing.discard(key)
        r["status"] = STATUS[args.action]
        verb = {"approve": "approved", "hold": "held", "retire": "retired"}[args.action]
        r["note"] = "{} by {} {}{}".format(verb, args.by, today, ": " + args.reason if args.reason else "")
        matched += 1

    if missing:
        print("not found, nothing changed for: " + "; ".join(sorted(missing)))
    with path.open("w", newline="") as fh:
        fh.writelines(head)
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    print("{} seed(s) {} · now: {}".format(matched, STATUS[args.action],
                                         dict(Counter(r["status"] for r in rows))))
    return 0 if matched else 1


if __name__ == "__main__":
    sys.exit(main())
