#!/usr/bin/env python3
"""
run_seeds.py — run a brief's approved seeds through to a tiered workbook.

One command for the web lane's research half, in order:

  1. serp_scan.py      approved seeds -> page-1 results (SerpAPI, budget-gated)
  2. review_sites.py   keep reviews, comparisons, product tests; skip the
                       brand's own site, forums, retailers, job sites, directories
  3. site_profile.py   tier each site (creator / niche review / media / check)
                       and capture any published email (CHANGELOG D18)

The budget gate in step 1 is respected, not worked around: exit code 3 means the
run is bigger than the confirm threshold and is waiting for Nicole; 2 means it
was refused (cap or reserve). Steps 2 and 3 cost nothing and only run after a
real scan, or with --skip-scan to rebuild from results already on disk.

A demo brief (one /reset-demo can reset) replays instead of going live: seeds
already searched come from the saved results, sites already profiled from their
saved profiles, so a run on stage takes seconds and spends nothing. Anything not
saved is listed and left out. --live runs it for real (CHANGELOG D27).

Usage:
  python3 scripts/run_seeds.py affiliate-seo-creators --dry-run
  python3 scripts/run_seeds.py affiliate-seo-creators --limit 5 --yes
  python3 scripts/run_seeds.py affiliate-seo-creators --skip-scan
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(cmd):
    shown = [Path(c).relative_to(ROOT) if isinstance(c, Path) else c for c in cmd]
    print("\n$ " + " ".join(str(c) for c in shown), file=sys.stderr)
    return subprocess.run([sys.executable] + [str(c) for c in cmd], cwd=str(ROOT)).returncode


def main():
    ap = argparse.ArgumentParser(description="Scan approved seeds, keep review sites, tier them.")
    ap.add_argument("slug")
    ap.add_argument("--slate", default=date.today().strftime("%Y-%m"))
    ap.add_argument("--depth", type=int, default=10,
                    help="results per seed; 10 = page 1 only, 1 search per seed (default)")
    ap.add_argument("--limit", type=int, help="run only the first N approved seeds")
    ap.add_argument("--dry-run", action="store_true", help="plan and budget only; spend nothing")
    ap.add_argument("--yes", action="store_true", help="approve a scan over the confirm threshold")
    ap.add_argument("--skip-scan", action="store_true",
                    help="no SerpAPI; rebuild the review list and tiers from results already on disk")
    ap.add_argument("--live", action="store_true",
                    help="on a demo brief, search and visit sites for real instead of replaying (D27)")
    args = ap.parse_args()
    live = ["--live"] if args.live else []

    if not args.skip_scan:
        cmd = [SCRIPTS / "serp_scan.py", args.slug, "--slate", args.slate, "--depth", args.depth] + live
        if args.limit:
            cmd += ["--limit", args.limit]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.yes:
            cmd.append("--yes")
        code = run(cmd)
        if code == 3:
            print("\nstopped at the confirm threshold: nothing spent. Re-run with --yes once approved.")
            return 3
        if code == 4:
            print("\ndemo brief: none of the approved seeds has saved results, so nothing ran and nothing "
                  "was spent. Before the talk, run with --live to search them.")
            return 4
        if code != 0:
            print("\nthe scan did not run (exit {}): see the lines above.".format(code))
            return code
        if args.dry_run:
            return 0

    import _paths
    results = _paths.raw_dir(args.slug) / "serp-results.json"
    if not results.exists():
        print("no results at {}: run the scan first".format(results.relative_to(ROOT)))
        return 1
    if args.dry_run:
        # --skip-scan --dry-run used to run the free steps anyway; a dry run
        # should never do anything, free or not.
        import json
        n = len(json.loads(results.read_text()))
        visits = ("reusing saved site profiles, no page visits" if _paths.is_demo(args.slug) and not args.live
                  else "No SerpAPI, no spend; just page visits")
        print("dry run: would rebuild from {} saved queries in {}, then profile every kept site. "
              "{}.".format(n, results.parent.relative_to(ROOT), visits))
        return 0
    for step in (["review_sites.py", args.slug, "--slate", args.slate],
                 ["site_profile.py", args.slug, "--slate", args.slate] + live):
        code = run([SCRIPTS / step[0]] + step[1:])
        if code != 0:
            print("\n{} failed (exit {})".format(step[0], code))
            return code

    print("\ndone. The results: {}".format(_paths.review_sites(args.slug).relative_to(ROOT)))
    print("Every skip, with its reason: {}".format(
        (_paths.raw_dir(args.slug) / "review-excluded.csv").relative_to(ROOT)))
    print("next: the team curates review-sites.csv (filter on tier); then /fetch-emails on their export.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
