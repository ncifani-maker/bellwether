#!/usr/bin/env python3
"""
yt_scan.py — Bellwether Scout, YouTube lane. One command for the whole chain.

The pieces already existed and had to be run by hand, in the right order, with
the right flags. This runs them in that order and stops you spending quota by
accident:

  1. scout.py         topic search -> ranked workbook with a Channels sheet
  2. geo prefilter    screened BEFORE the donor scan, never after (CLAUDE.md)
  3. donor_trail.py   full-description donor-brand counting per channel
  4. farm_flag.py     content-farm screen on the workbook
  5. report.md        ranked markdown + the donor-scan CSV

Steps 1-3 and 5 are run_study.py, which already caches workbooks and resumes, so
this builds a study config from the arguments and hands off to it rather than
reimplementing any of it. The config is written to briefs/studies/ so a run stays
reproducible: the same file re-runs the same study.

Quota is estimated and gated before anything is spent (config/budgets.json).
YouTube has no "how much is left" endpoint, so the ledger (data/api-usage.csv) is
the only count there is — which is why every run logs to it.

Usage:
  python3 scripts/yt_scan.py homeaglow "clean with me routine" --max 50
  python3 scripts/yt_scan.py homeaglow --study briefs/studies/homeaglow-hellofresh.json
  python3 scripts/yt_scan.py rarity7 "rare coin collecting" --geo US --no-donors --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _budget  # noqa: E402
from _keys import CANONICAL, require  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]  # bellwether/
SCOUT = ROOT / "vendor" / "youtube-scout" / "scripts" / "scout.py"
RUN_STUDY = ROOT / "scripts" / "run_study.py"
FARM_FLAG = ROOT / "scripts" / "farm_flag.py"

SEARCH_UNITS = 100  # one search.list call covers 50 videos
DONOR_UNITS_PER_CHANNEL = 4
DEDUPE_FACTOR = 0.5  # channels per video collected, observed across past studies


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def brand_channel_pattern(donors_path):
    """Drop the donor brands' own channels from candidates.

    run_study's default pattern is the meal-kit list, which is wrong for every
    brand that is not Homeaglow. Build it from the brand's own donor config.
    """
    try:
        cfg = json.loads(donors_path.read_text())
    except (OSError, ValueError):
        return None
    names = []
    primary = cfg.get("primary") or {}
    if primary.get("name"):
        names.append(primary["name"])
    for sec in cfg.get("secondary") or []:
        if sec.get("name"):
            names.append(sec["name"])
    if not names:
        return None
    return "|".join(re.escape(n.lower().replace(" ", "")) for n in names)


def estimate_units(topics, max_videos, donors):
    """Rough, and deliberately on the high side. Reported before spending."""
    pages = max(1, -(-max_videos // 50))
    search = len(topics) * pages * SEARCH_UNITS
    detail = len(topics) * pages * 2  # videos.list + channels.list, 1 unit each
    donor = 0
    if donors:
        donor = int(len(topics) * max_videos * DEDUPE_FACTOR * DONOR_UNITS_PER_CHANNEL)
    return search + detail + donor


def run(cmd, label, env_file=None):
    import os
    env = dict(os.environ)
    # scout.py and donor_trail.py both resolve keys via SCOUT_ENV_FILE, so the
    # canonical file is handed over by path. The key is never on the command line.
    env["SCOUT_ENV_FILE"] = str(env_file or CANONICAL)
    print("\n$ {}".format(" ".join(str(c) for c in cmd)), file=sys.stderr)
    result = subprocess.run([str(c) for c in cmd], cwd=str(ROOT), env=env)
    if result.returncode != 0:
        sys.exit("yt-scan: {} failed with exit code {}".format(label, result.returncode))


def main():
    ap = argparse.ArgumentParser(description="YouTube scan: scout, geo screen, donor trail, farm flag.")
    ap.add_argument("brand", help="brand slug, e.g. homeaglow")
    ap.add_argument("topics", nargs="*", help="one or more topics (quote each)")
    ap.add_argument("--study", help="use an existing study config instead of building one")
    ap.add_argument("--slate", default=date.today().strftime("%Y-%m"))
    ap.add_argument("--max", type=int, default=50, help="videos per topic (default 50)")
    ap.add_argument("--sort", default="views", help="views|engagement|likes|recent|momentum|breakout")
    ap.add_argument("--since", default="any", help="hour|today|week|month|year|any")
    ap.add_argument("--length", help="short|medium|long — Shorts lanes want short")
    ap.add_argument("--geo", default="US", help="geography target screened before the donor scan")
    ap.add_argument("--depth", type=int, default=90, help="uploads scanned per channel (default 90)")
    ap.add_argument("--no-donors", action="store_true", help="scout + farm flag only, no donor scan")
    ap.add_argument("--refresh", action="store_true", help="re-run scout even if workbooks are cached")
    ap.add_argument("--dry-run", action="store_true", help="plan and quota only; spend nothing")
    ap.add_argument("--yes", action="store_true", help="approve a run over the confirm threshold")
    ap.add_argument("--live", action="store_true", help="on a demo brief, allow the spend (D27)")
    args = ap.parse_args()

    require("YOUTUBE_API_KEY")  # fail early with a fix hint, not mid-run

    out_dir = ROOT / "outputs" / args.brand / args.slate
    donors_path = ROOT / "briefs" / args.brand / "donors.json"
    use_donors = donors_path.exists() and not args.no_donors

    # 1. The study config: an existing one, or one built from these arguments.
    if args.study:
        study_path = Path(args.study)
        if not study_path.is_absolute():
            study_path = ROOT / study_path
        if not study_path.exists():
            sys.exit("no study config at {}".format(study_path))
        study = json.loads(study_path.read_text())
        topics = study.get("topics", [])
    else:
        if not args.topics:
            sys.exit("give at least one topic, or --study <config.json>")
        topics = args.topics
        study = {
            "name": "{} — {}".format(args.brand, ", ".join(topics)[:60]),
            "donor_label": donors_path.stem if use_donors else "",
            "geo_target": args.geo.upper(),
            "geo_prefilter": {"target": args.geo.upper(), "keep_unknown": True},
            "depth": args.depth,
            "min_count": 1,
            "out_dir": str(out_dir.relative_to(ROOT)),
            "scan_csv": "data/donor-scans-api.csv",
            "scout": {"max": args.max, "sort": args.sort, "since": args.since},
            "topics": topics,
        }
        if use_donors:
            study["donors"] = str(donors_path.relative_to(ROOT))
            pattern = brand_channel_pattern(donors_path)
            if pattern:
                study["brand_channel_pattern"] = pattern
        study_path = ROOT / "briefs" / args.brand / "studies" / "{}.json".format(slug(topics[0]))

    # 2. Quota, before anything is spent.
    planned = estimate_units(topics, study.get("scout", {}).get("max", args.max), use_donors)
    code, lines = _budget.gate("youtube", planned, remaining=None, yes=args.yes, unit="units",
                               brand=args.brand, live=args.live)

    print("YouTube scan · {} · slate {}".format(args.brand, args.slate))
    print("topics: {}".format(len(topics)))
    for topic in topics:
        print("  · {}".format(topic))
    print("donor scan: {}".format(
        "yes ({})".format(donors_path.relative_to(ROOT)) if use_donors
        else "no donor config at {} — scout + farm flag only".format(donors_path.relative_to(ROOT))
        if not args.no_donors else "skipped (--no-donors)"))
    print("geo screen: {} (before the donor scan)".format(args.geo.upper()))
    for line in lines:
        print("  " + line)

    if args.dry_run:
        print("\ndry run — nothing spent. Study config would be {}".format(
            study_path.relative_to(ROOT)))
        return 0
    if code != _budget.OK:
        return code

    out_dir.mkdir(parents=True, exist_ok=True)

    # 3. Run. With donors, run_study does scout + geo screen + donor scan + report.
    #    Without, scout alone — there is nothing to screen for and nothing to scan.
    books = []
    if use_donors:
        if not args.study:
            study_path.parent.mkdir(parents=True, exist_ok=True)
            study_path.write_text(json.dumps(study, indent=2) + "\n")
            print("\nstudy config: {}".format(study_path.relative_to(ROOT)))
        cmd = [sys.executable, RUN_STUDY, "--study", study_path]
        if args.refresh:
            cmd.append("--refresh")
        run(cmd, "study")
        books = [out_dir / "scout-{}.xlsx".format(slug(t)) for t in topics]
    else:
        for topic in topics:
            book = out_dir / "scout-{}.xlsx".format(slug(topic))
            if book.is_file() and not args.refresh:
                print("  cached: {}".format(book.name), file=sys.stderr)
                books.append(book)
                continue
            cmd = [sys.executable, SCOUT] + topic.split() + [
                "--max", str(args.max), "--sort", args.sort, "--since", args.since,
                "--out", book,
            ]
            if args.length:
                cmd += ["--length", args.length]
            run(cmd, "scout '{}'".format(topic))
            books.append(book)

    # 4. Farm screen on every workbook — free, no API calls.
    for book in books:
        if book.is_file():
            run([sys.executable, FARM_FLAG, "--from-scout", book], "farm flag")

    _budget.log("youtube", planned, "units", "yt-scan", args.brand, args.slate,
                "{} topics, estimated".format(len(topics)))

    print("\noutputs in {}".format(out_dir.relative_to(ROOT)))
    for book in books:
        if book.is_file():
            print("  · {}".format(book.name))
    if use_donors:
        print("  · report.md, and rows appended to data/donor-scans-api.csv")
    print("\nestimated {:,} quota units of 10,000/day. Check the Farm Risk and Channel Country"
          " columns before any outreach.".format(planned))
    return 0


if __name__ == "__main__":
    sys.exit(main())
