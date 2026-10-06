#!/usr/bin/env python3
"""
farm_flag.py - Bellwether Scout, content-farm screen.

Companion to youtube-scout (vendor/youtube-scout). scout.py ranks by
performance, and --sort breakout ranks by views-per-subscriber. On broad
consumer topics that sort is dominated by high-volume, low-baseline channels:
one lottery video standing against a four-figure average across hundreds of
uploads. The views/sub is an artifact of a tiny subscriber count, not audience
pull, and acting on it puts volume-spam at the top of a longlist.

This reads a scout workbook and writes a Farm Risk column onto the Videos and
Channels sheets, judged on the channel's own baseline rather than on the one
video that happened to surface.

  HIGH     >= 200 uploads and < 5,000 average views per video
  MEDIUM   >= 100 uploads and < 10,000 average views per video
  (blank)  everything else

The thresholds screen volume-spam, not small channels: 78 uploads averaging
357k views is untouched. Adjust with --min-uploads / --high-avg / --medium-avg.

Farm Risk is a screen, not a verdict, and it is blind to the other failure mode
on this data - channels that re-upload another brand's IP. Those show up as a
Channel Country that does not match the brand's home market; check that column
by eye before any outreach.

Reads Avg Views/Video and Channel Videos, both of which scout.py already
writes. No API calls, no quota, no network.

Writes in place after a timestamped .backup- copy, matching scout.py --into
behaviour. The file must be closed in Excel.

Usage:
  python3 farm_flag.py --from-scout outputs/_scratch/scout-rare-coins-2026-09-18.xlsx
  python3 farm_flag.py --from-scout <workbook> --high-avg 8000 --dry-run
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import Counter
from datetime import datetime

try:
    import openpyxl
except ImportError:
    sys.exit("farm_flag: openpyxl is not installed. pip install openpyxl")

COLUMN = "Farm Risk"
TARGET_SHEETS = ("Videos", "Channels")


def header_map(ws):
    return {c.value: i for i, c in enumerate(ws[1], start=1) if c.value}


def classify(uploads, avg_views, args):
    if not uploads or not avg_views:
        return ""
    if uploads >= args.min_uploads and avg_views < args.high_avg:
        return "HIGH"
    if uploads >= args.min_uploads // 2 and avg_views < args.medium_avg:
        return "MEDIUM"
    return ""


def num(v):
    return v if isinstance(v, (int, float)) else 0


def main():
    p = argparse.ArgumentParser(description="Flag likely content farms in a scout workbook.")
    p.add_argument("--from-scout", dest="workbook", required=True, help="scout .xlsx to annotate")
    p.add_argument("--min-uploads", type=int, default=200, help="uploads for HIGH (default 200; half of this for MEDIUM)")
    p.add_argument("--high-avg", type=int, default=5000, help="avg views/video below which HIGH applies (default 5000)")
    p.add_argument("--medium-avg", type=int, default=10000, help="avg views/video below which MEDIUM applies (default 10000)")
    p.add_argument("--dry-run", action="store_true", help="report counts, write nothing")
    args = p.parse_args()

    try:
        wb = openpyxl.load_workbook(args.workbook)
    except FileNotFoundError:
        sys.exit(f"farm_flag: no such workbook: {args.workbook}")

    tallies = {}
    flagged_handles = []

    for name in TARGET_SHEETS:
        if name not in wb.sheetnames:
            print(f"farm_flag: warning: no {name} sheet, skipped", file=sys.stderr)
            continue
        ws = wb[name]
        hdr = header_map(ws)
        for required in ("Channel Videos", "Avg Views/Video"):
            if required not in hdr:
                sys.exit(f"farm_flag: {name} sheet has no '{required}' column; is this a scout workbook?")

        col = hdr.get(COLUMN) or ws.max_column + 1
        ws.cell(row=1, column=col, value=COLUMN)

        counts = Counter()
        for r in range(2, ws.max_row + 1):
            verdict = classify(
                num(ws.cell(row=r, column=hdr["Channel Videos"]).value),
                num(ws.cell(row=r, column=hdr["Avg Views/Video"]).value),
                args,
            )
            ws.cell(row=r, column=col, value=verdict or None)
            counts[verdict or "clear"] += 1
            if verdict and name == "Channels":
                flagged_handles.append((ws.cell(row=r, column=hdr.get("Handle", 1)).value, verdict))
        tallies[name] = counts

    for name, counts in tallies.items():
        total = sum(counts.values())
        print(f"{name}: {counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['clear']} clear (of {total})")
    for handle, verdict in flagged_handles:
        print(f"  {verdict:<7} {handle}")

    if args.dry_run:
        print("farm_flag: dry run, nothing written")
        return

    backup = f"{args.workbook}.backup-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(args.workbook, backup)
    try:
        wb.save(args.workbook)
    except PermissionError:
        sys.exit(f"farm_flag: could not write {args.workbook} (is it open in Excel?)")
    print(f"farm_flag: wrote {COLUMN} to {args.workbook} (backup: {backup})")


if __name__ == "__main__":
    main()
