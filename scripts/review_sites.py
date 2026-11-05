#!/usr/bin/env python3
"""
review_sites.py — turn "[brand] review" SERPs into a list of review sites.

serp_scan.py answers "who ranks". For a brand-review prospecting list the
question is narrower: which of those results is a REVIEW of the brand, by
someone who is not the brand, and who keeps doing it across a category. A site
that reviewed four mattress brands is a mattress reviewer; that is the person to
pitch the fifth.

Rules come from the brief, not from here (CHANGELOG D4). The defaults below are
the ones in the source sheet's Instructions tab:

  keep     a review, a reviews page, a comparison review, a product-testing article
  skip     the brand's own site (listed, so a human can re-add one with
           third-party reviews worth having)
  skip     forums and community threads, unless UGC is tracked deliberately
  skip     retailers: a product page with reviews is a shop, not a reviewer

Every skip lands in raw/review-excluded.csv with its reason. Nothing is dropped
silently, because the screen is a heuristic and will be wrong sometimes.

Reads  briefs/<slug>/seeds.csv                 (keyword -> category, brand, form)
       briefs/<slug>/raw/serp-results.json
Writes briefs/<slug>/raw/review-results.csv      every result kept
       briefs/<slug>/raw/review-excluded.csv     every result skipped, with the reason
The sites themselves, one row each, go in briefs/<slug>/review-sites.csv (site_profile.py).

Usage:
  python3 scripts/review_sites.py affiliate-seo-creators --slate 2026-10
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import OrderedDict, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORUM_HOSTS = ("forum.", "forums.", "community.", "boards.", "discuss.", "discussion.")
FORUM_DOMAINS = {"quora.com", "reddit.com", "answers.com", "justanswer.com", "tiktok.com", "lemon8-app.com",
                 "facebook.com", "instagram.com", "youtube.com", "pinterest.com"}
RETAIL = {"amazon.com", "walmart.com", "target.com", "costco.com", "bestbuy.com", "wayfair.com",
          "homedepot.com", "lowes.com", "macys.com", "kohls.com", "ebay.com", "etsy.com",
          "chewy.com", "petco.com", "petsmart.com", "sephora.com", "ulta.com", "qvc.com",
          "samsclub.com", "bjs.com", "kroger.com", "staples.com", "overstock.com",
          "bedbathandbeyond.com", "crateandbarrel.com", "potterybarn.com", "williams-sonoma.com",
          "thrivemarket.com", "instacart.com", "cvs.com", "walgreens.com", "iherb.com"}

# For franchise and service brands, "[brand] review" is full of EMPLOYEE reviews of
# working there. That is the supply side reviewing the brand, not its customers,
# and it put Indeed and Glassdoor at the top of the first run.
EMPLOYER_REVIEWS = {"indeed.com", "glassdoor.com", "comparably.com", "ziprecruiter.com",
                    "careerbliss.com", "simplyhired.com", "kununu.com", "payscale.com", "salary.com"}

# Marketplaces and local directories list the PROVIDERS of a service with their
# own reviews. homeadvisor.com and reviews.birdeye.com ranked for franchise
# brands on 2026-10-06; they are the supply side's storefront, not a reviewer.
DIRECTORIES = {"homeadvisor.com", "angi.com", "angieslist.com", "thumbtack.com", "birdeye.com",
               "porch.com", "nextdoor.com", "houzz.com", "taskrabbit.com", "yellowpages.com",
               "mapquest.com", "chamberofcommerce.com", "manta.com", "bark.com"}
# A forum on its own domain (smokingmeatforums.com, weberkettleclub.com) shows
# itself in the name or in the thread URL (Braise, 2026-11-04).
FORUM_URL = ("/threads/", "/forums/", "/forum/", "/topic/", "/viewtopic", "showthread")


def is_forum_page(domain, row):
    url = (row.get("url") or "").lower()
    return "forum" in root_domain(domain) or any(m in url for m in FORUM_URL)


# The SERP Tracker's noise list, matched on the ROOT domain so country
# subdomains (ie.trustpilot.com, nz.trustpilot.com) are caught here too.
NOISE_ROOTS = {"trustpilot.com", "yelp.com", "bbb.org", "reddit.com",
               "google.com"}   # a Google-hosted copy of someone else's review (Braise, 2026-11-04)

# An app listing has reviews, but it is a store page, not a reviewer.
APP_STORES = {"play.google.com", "apps.apple.com", "itunes.apple.com", "chrome.google.com"}

# Result type, in priority order: the first match labels the row.
# Two mislabels found on the Saatva test SERPs fixed the patterns below:
#   "honest review" is a review, not a test, so "honest" moved to review;
#   "Review (2026)" is a year, not a review count, so the bracketed-number rule went.
# "Does it hold up over time?" is a long-term test, so "hold up" and "over time" joined testing.
TYPES = [
    ("product testing", r"\btested\b|we tried|i tried|tried it|lived with|"
                        r"after (?:a |one |\d+ )?(?:days?|weeks?|months?|years?)|\d+[- ]year|"
                        r"hands[- ]on|my experience|months? later|long[- ]term|hold up|over time"),
    ("comparison",      r"\bvs\.?\b|versus|compar|alternatives?"),
    ("reviews page",    r"ratings? (?:&|and) reviews|customer reviews|\d[\d,]* reviews"),
    ("review",          r"review|honest|worth it|pros and cons|is it worth|rating"),
]
TYPES = [(name, re.compile(rx, re.I)) for name, rx in TYPES]


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def root_domain(domain: str) -> str:
    parts = domain.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain


def classify(row: dict, brand: str):
    """-> (kept: bool, label). Label is the result type if kept, else the reason."""
    domain = row["domain"].lower()
    text = "{} {}".format(row.get("title") or "", row.get("url") or "")
    # The brand's own site. Brands pad their name: helixsleep.com, bearmattress.com,
    # hiyahealth.com, getsunday.com. An exact match missed the first three, which
    # then showed up as "reviews" of themselves. The check runs only inside that
    # brand's own SERP, so a prefix is safe: "bear" will not meet a stray
    # bearcreek.com on a Bear mattress results page.
    b = squash(brand)
    d = squash(root_domain(domain).split(".")[0])
    if b and (d.startswith(b) or any(d == pre + b for pre in ("get", "try", "shop", "hey", "hello", "my"))
              or (len(b) >= 6 and b in d)):
        return False, "brand's own site"
    if root_domain(domain) in EMPLOYER_REVIEWS:
        return False, "employer reviews (job site)"
    if domain.startswith(FORUM_HOSTS) or root_domain(domain) in FORUM_DOMAINS or is_forum_page(domain, row):
        return False, "forum / community"
    if root_domain(domain) in NOISE_ROOTS:
        return False, "on the tracker's noise list"
    if root_domain(domain) in DIRECTORIES:
        return False, "marketplace / local directory"
    if root_domain(domain) in RETAIL:
        return False, "retailer"
    if domain in APP_STORES:
        return False, "app store listing"
    for name, rx in TYPES:
        if rx.search(text):
            return True, name
    return False, "not a review result"


def load_seeds(slug: str) -> dict:
    path = ROOT / "briefs" / slug / "seeds.csv"
    with path.open() as fh:
        return {r["keyword"]: r for r in csv.DictReader(l for l in fh if not l.startswith("#"))}


def build(slug: str, slate: str) -> Path:
    raw_path, raw, ranked, results, excluded = collect(slug, slate)
    write_csvs(raw_path.parent, results, excluded)
    return raw_path.parent


def collect(slug: str, slate: str):
    """The kept sites, ranked. One definition, shared with site_profile.py."""
    seeds = load_seeds(slug)
    import _paths
    raw_path = _paths.raw_dir(slug) / "serp-results.json"
    raw = json.loads(raw_path.read_text())

    results, excluded = [], []
    sites = OrderedDict()
    for query, rows in raw.items():
        meta = seeds.get(query, {})
        brand = meta.get("brand") or query.rsplit(" review", 1)[0]
        category = meta.get("category", "")
        for r in rows:
            kept, label = classify(r, brand)
            rec = {"category": category, "brand": brand, "query": query, "form": meta.get("form", ""),
                   "rank": r.get("rank"), "domain": r["domain"], "label": label,
                   "title": r.get("title") or "", "url": r.get("url") or ""}
            if not kept:
                excluded.append(rec)
                continue
            results.append(rec)
            s = sites.setdefault(r["domain"], {"brands": OrderedDict(), "categories": OrderedDict(),
                                                "types": OrderedDict(), "best": 99, "example": rec})
            s["brands"][brand] = 1
            s["categories"][category] = 1
            s["types"][label] = 1
            if (r.get("rank") or 99) < s["best"]:
                s["best"], s["example"] = r["rank"], rec

    ranked = sorted(sites.items(), key=lambda kv: (-len(kv[1]["brands"]), -len(kv[1]["categories"]),
                                                  kv[1]["best"]))
    return raw_path, raw, ranked, results, excluded


def write_csvs(out_dir, results, excluded):
    """The detail behind the one results file: every result kept and every result
    thrown out, with the reason (D24, D25). The sites themselves go in the brief's
    review-sites.csv, written by site_profile.py."""
    def write(name, headers, rows):
        with (out_dir / name).open("w", newline="") as fh:
            w = csv.writer(fh); w.writerow(headers); w.writerows(rows)

    write("review-results.csv",
          ["category", "brand", "query", "rank", "domain", "type", "title", "url"],
          [[r["category"], r["brand"], r["query"], r["rank"], r["domain"], r["label"], r["title"], r["url"]]
           for r in sorted(results, key=lambda r: (r["category"], r["brand"], r["rank"] or 99))])
    write("review-excluded.csv",
          ["domain", "reason", "brand", "query", "rank", "title", "url"],
          [[r["domain"], r["label"], r["brand"], r["query"], r["rank"], r["title"], r["url"]]
           for r in sorted(excluded, key=lambda r: (r["label"], r["domain"]))])


def main():
    ap = argparse.ArgumentParser(description="Review sites from brand-review SERPs.")
    ap.add_argument("slug", help="brief slug")
    ap.add_argument("--slate", default=date.today().strftime("%Y-%m"))
    args = ap.parse_args()
    out = build(args.slug, args.slate)
    for name in ("review-results.csv", "review-excluded.csv"):
        print("wrote {}".format((out / name).relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
