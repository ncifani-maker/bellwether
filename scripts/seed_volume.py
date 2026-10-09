#!/usr/bin/env python3
"""
seed_volume.py — Google search volume and cost-per-click for a brief's seeds.

Seeds are judged on intent first and volume second (docs/seed-list-framework.md):
we are not ranking for these words, we are using them to find who already ranks.
Cost-per-click is the better intent signal, because advertisers pay for clicks
that convert. Volume only sizes the opportunity and breaks ties.

DataForSEO, Google Ads search volume, one live request for up to 1,000
keywords. Pay-as-you-go: the balance is read first (free), the run stops before
spending if it would leave less than `min_balance_usd`, and asks (exit 3) if the
estimate is over `confirm_above_usd` (config/budgets.json). The real cost comes
back in the response and goes into the ledger.

Ported 2026-10-10 from close-demo's dataforseo_kw.py, which needs `requests`;
this is standard library only. Keyword difficulty is left out by default:
close-demo found that endpoint pending account verification.

Writes briefs/<slug>/seed-volume.csv (keyword, volume, cpc, competition,
checked). It sits beside seeds.csv rather than in it, so a re-import never
has to know about it.

Usage:
  python3 scripts/seed_volume.py covey --dry-run
  python3 scripts/seed_volume.py covey --status proposed
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _budget  # noqa: E402
from _keys import require  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.dataforseo.com/v3"
US, ENGLISH = 2840, "en"
ESTIMATE_PER_CALL = 0.10   # deliberately high; the real cost is read from the response


def call(path, auth, payload=None):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Basic " + auth,
                                                       "Content-Type": "application/json"},
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        return {"status_code": exc.code, "status_message": exc.read().decode("utf-8", "replace")[:200]}


def balance(auth):
    data = call("/appendix/user_data", auth)
    try:
        return float(data["tasks"][0]["result"][0]["money"]["balance"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description="Search volume and CPC for a brief's seeds (DataForSEO).")
    ap.add_argument("slug")
    ap.add_argument("--status", default="proposed",
                    help="which seeds: proposed (default), approved, or all")
    ap.add_argument("--dry-run", action="store_true", help="balance and plan only; spend nothing")
    ap.add_argument("--yes", action="store_true", help="approve a run over the confirm threshold")
    args = ap.parse_args()

    seeds_path = ROOT / "briefs" / args.slug / "seeds.csv"
    with seeds_path.open() as fh:
        rows = list(csv.DictReader(l for l in fh if not l.startswith("#")))
    pick = [r["keyword"] for r in rows if args.status == "all" or r.get("status") == args.status]
    if not pick:
        sys.exit("no `{}` seeds in {}".format(args.status, seeds_path.relative_to(ROOT)))
    pick = pick[:1000]

    login, password = require("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")
    auth = base64.b64encode("{}:{}".format(login, password).encode()).decode()
    cfg = _budget.budgets().get("dataforseo") or {}
    have = balance(auth)
    est = ESTIMATE_PER_CALL
    print("Seed volume · {} · {} `{}` seeds · one DataForSEO request".format(args.slug, len(pick), args.status))
    print("  balance: {} · estimate: up to ${:.2f}".format("${:.2f}".format(have) if have is not None else "unknown", est))
    if have is not None and have - est < (cfg.get("min_balance_usd") or 0):
        print("  REFUSED: would go under the minimum balance of ${:.2f}. Top up DataForSEO.".format(
            cfg.get("min_balance_usd")))
        return 2
    if args.dry_run:
        print("\ndry run, nothing spent")
        return 0
    if est > (cfg.get("confirm_above_usd") or 1e9) and not args.yes:
        print("  STOPPED before spending: over the ${:.2f} confirm threshold. Re-run with --yes.".format(
            cfg.get("confirm_above_usd")))
        return 3

    data = call("/keywords_data/google_ads/search_volume/live", auth,
                [{"keywords": pick, "location_code": US, "language_code": ENGLISH}])
    cost = data.get("cost") or 0
    _budget.log("dataforseo", cost, "usd", "seed-volume", args.slug, "", "{} keywords".format(len(pick)))
    if data.get("status_code") != 20000:
        sys.exit("DataForSEO: {} {}".format(data.get("status_code"), data.get("status_message")))
    found = {}
    for task in data.get("tasks") or []:
        for item in task.get("result") or []:
            found[(item.get("keyword") or "").lower()] = item

    out_path = seeds_path.parent / "seed-volume.csv"
    existing = {}
    if out_path.exists():
        with out_path.open() as fh:
            existing = {r["keyword"].lower(): r for r in csv.DictReader(fh)}
    today = date.today().isoformat()
    for kw in pick:
        v = found.get(kw.lower(), {})
        existing[kw.lower()] = {"keyword": kw, "volume": v.get("search_volume") if v else "",
                                "cpc": v.get("cpc") if v else "", "competition": v.get("competition") if v else "",
                                "checked": today}
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["keyword", "volume", "cpc", "competition", "checked"])
        w.writeheader(); w.writerows(existing.values())

    print("\n{:>8} {:>7}  {}".format("volume", "cpc", "seed"))
    for kw in sorted(pick, key=lambda k: -(found.get(k.lower(), {}).get("cpc") or 0)):
        v = found.get(kw.lower(), {})
        print("{:>8} {:>7}  {}".format(v.get("search_volume") if v.get("search_volume") is not None else "n/a",
                                       "${:.2f}".format(v["cpc"]) if v.get("cpc") is not None else "n/a", kw))
    print("\nsorted by cost-per-click: the intent signal. Volume only breaks ties.")
    print("spent ${:.4f} · wrote {}".format(cost, out_path.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
