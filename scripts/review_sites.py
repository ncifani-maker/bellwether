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

Every skip lands in the Excluded sheet with its reason. Nothing is dropped
silently, because the screen is a heuristic and will be wrong sometimes.

Reads  briefs/<slug>/seeds.csv            (keyword -> category, brand, form)
       outputs/<slug>/<slate>/serp-results.json
Writes outputs/<slug>/<slate>/review-sites.xlsx

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
FORUM_DOMAINS = {"quora.com", "reddit.com", "answers.com", "justanswer.com", "tiktok.com",
                 "facebook.com", "instagram.com", "youtube.com", "pinterest.com"}
RETAIL = {"amazon.com", "walmart.com", "target.com", "costco.com", "bestbuy.com", "wayfair.com",
          "homedepot.com", "lowes.com", "macys.com", "kohls.com", "ebay.com", "etsy.com",
          "chewy.com", "petco.com", "petsmart.com", "sephora.com", "ulta.com", "qvc.com",
          "bedbathandbeyond.com", "crateandbarrel.com", "potterybarn.com", "williams-sonoma.com",
          "thrivemarket.com", "instacart.com", "cvs.com", "walgreens.com", "iherb.com"}

# For franchise and service brands, "[brand] review" is full of EMPLOYEE reviews of
# working there. That is the supply side reviewing the brand, not its customers,
# and it put Indeed and Glassdoor at the top of the first run.
EMPLOYER_REVIEWS = {"indeed.com", "glassdoor.com", "comparably.com", "ziprecruiter.com",
                    "careerbliss.com", "simplyhired.com", "kununu.com", "payscale.com", "salary.com"}

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
    if domain.startswith(FORUM_HOSTS) or root_domain(domain) in FORUM_DOMAINS:
        return False, "forum / community"
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
    seeds = load_seeds(slug)
    raw_path = ROOT / "outputs" / slug / slate / "serp-results.json"
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
    out = raw_path.parent / "review-sites.xlsx"
    write_workbook(out, slug, slate, raw, ranked, results, excluded)
    return out


def write_workbook(out, slug, slate, raw, ranked, results, excluded):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    navy, band = "1F3864", "D9E2F3"
    head_font = Font(name="Arial", bold=True, color=navy, size=10)
    body_font = Font(name="Arial", size=10)
    link_font = Font(name="Arial", size=10, color="1155CC", underline="single")
    fill = PatternFill("solid", fgColor=band)

    def sheet(wb, title, headers, rows, widths, link_cols=()):
        ws = wb.create_sheet(title)
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill = head_font, fill
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for row in rows:
            ws.append(row)
        for r in ws.iter_rows(min_row=2):
            for c in r:
                c.font = body_font
                c.alignment = Alignment(vertical="top", wrap_text=False)
            for i in link_cols:
                cell = r[i]
                if cell.value and str(cell.value).startswith("http"):
                    cell.hyperlink, cell.font = cell.value, link_font
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        return ws

    wb = Workbook()
    wb.remove(wb.active)
    sheet(wb, "Sites",
          ["Domain", "Brands reviewed", "Categories", "Brands", "Best rank", "Result types",
           "Example title", "Example URL"],
          [[d, len(s["brands"]), ", ".join(s["categories"]), ", ".join(s["brands"]), s["best"],
            ", ".join(s["types"]), s["example"]["title"], s["example"]["url"]] for d, s in ranked],
          [30, 10, 30, 44, 9, 22, 60, 60], link_cols=(7,))
    sheet(wb, "Results",
          ["Category", "Brand", "Query", "Rank", "Domain", "Type", "Title", "URL"],
          [[r["category"], r["brand"], r["query"], r["rank"], r["domain"], r["label"], r["title"], r["url"]]
           for r in sorted(results, key=lambda r: (r["category"], r["brand"], r["rank"] or 99))],
          [24, 22, 30, 6, 30, 16, 60, 60], link_cols=(7,))
    sheet(wb, "Excluded",
          ["Domain", "Reason", "Brand", "Query", "Rank", "Title", "URL"],
          [[r["domain"], r["label"], r["brand"], r["query"], r["rank"], r["title"], r["url"]]
           for r in sorted(excluded, key=lambda r: (r["label"], r["domain"]))],
          [30, 20, 22, 30, 6, 60, 60], link_cols=(6,))

    reasons = defaultdict(int)
    for r in excluded:
        reasons[r["label"]] += 1
    method = [
        ["What this is", "Review sites pulled from page 1 of Google for \"[brand] review\" queries."],
        ["Brief", "briefs/{}/".format(slug)],
        ["Slate", slate],
        ["Built", date.today().isoformat()],
        ["Queries run", len(raw)],
        ["Results kept", len(results)],
        ["Unique sites", len(ranked)],
        ["Excluded", "; ".join("{} {}".format(v, k) for k, v in sorted(reasons.items(), key=lambda x: -x[1]))],
        ["Kept", "A review, a reviews page, a comparison review, or a product-testing article, labelled "
                 "by title and URL."],
        ["Skipped", "The brand's own site (including padded domains like helixsleep.com), forums and "
                    "community threads, retailers, app-store listings, and job sites: for franchise and "
                    "service brands, \"[brand] review\" is full of employee reviews on Indeed and Glassdoor, "
                    "which is the supply side reviewing the brand, not its customers. Every skip is on the "
                    "Excluded sheet with its reason: the screen is a heuristic, so check it."],
        ["Not yet run", "The plural \"[brand] reviews\" for 61 brands. A 3-brand test showed it adds about "
                        "87% more usable sites; held for this month's SerpAPI budget."],
        ["Ranking", "Sites are sorted by how many brands they reviewed. A site that reviewed four "
                    "brands in a category is a category reviewer: the person to pitch the fifth."],
        ["Not a measure of", "Traffic, authority, or whether the site takes affiliate placements. "
                             "Those come at the qualify step."],
        ["Source", "SerpAPI, google.com, desktop, San Francisco, page 1, no cache."],
    ]
    ws = wb.create_sheet("Method")
    for row in method:
        ws.append(row)
    for r in ws.iter_rows():
        r[0].font = head_font
        r[1].font = body_font
        r[1].alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 100
    wb.save(out)


def main():
    ap = argparse.ArgumentParser(description="Review sites from brand-review SERPs.")
    ap.add_argument("slug", help="brief slug")
    ap.add_argument("--slate", default=date.today().strftime("%Y-%m"))
    args = ap.parse_args()
    out = build(args.slug, args.slate)
    print("wrote {}".format(out.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
