#!/usr/bin/env python
"""Score SERP research into a motion-tagged opportunities.csv (client-agnostic).

Usage: score_opportunities.py <client_dir>
Reads <client_dir>/serp_results.json + seeds.csv, aggregates the "who ranks"
data into unique domains, classifies each (review-target / retail / owned /
off-topic), scores fit by how many brands it covers, and writes
<client_dir>/opportunities.csv plus a refreshed full results.csv.

First-pass heuristic. The fine editorial-vs-affiliate split inside 'review-target'
is left for a human/agent pass (same as the Close run).
"""
import os
import sys
import csv
import json
import collections

RETAIL = {"amazon.com", "target.com", "walmart.com", "chewy.com", "ulta.com", "sephora.com", "spacenk.com",
          "ipsy.com", "costco.com", "ebay.com", "petco.com", "petsmart.com", "instacart.com", "kroger.com",
          "cvs.com", "walgreens.com", "bestbuy.com"}
NOISE = {"merriam-webster.com", "dictionary.cambridge.org", "en.wikipedia.org", "en.wiktionary.org",
         "dictionary.com", "collinsdictionary.com", "britannica.com", "quora.com"}
QUAL = {"dog", "food", "skincare", "skin", "beauty", "makeup", "hair", "haircare", "market", "foods",
        "company", "meals", "meal", "pet", "grocery", "the", "of", "and"}
AUTHORITY = {"forbes.com", "nytimes.com", "cnet.com", "businessinsider.com", "goodhousekeeping.com",
             "realsimple.com", "bonappetit.com", "byrdie.com", "whowhatwear.com", "purewow.com",
             "reviewed.com", "instyle.com", "refinery29.com", "coveteur.com", "theeverygirl.com"}


def brand_token(keyword):
    words = [w for w in keyword.lower().replace("'", "").replace("reviews", "").replace("review", "").split()
             if w not in QUAL]
    return "".join(ch for ch in "".join(words) if ch.isalnum())


def sld(domain):
    p = domain.split(".")
    return p[-2] if len(p) >= 2 else p[0]


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    with open(os.path.join(d, "seeds.csv")) as fh:
        seed_rows = list(csv.DictReader([ln for ln in fh if not ln.lstrip().startswith("#")]))
    keywords = [r["keyword"] for r in seed_rows
                if r.get("keyword") and r.get("status", "").strip().lower() != "retired"]
    vertical = {r["keyword"]: r.get("vertical", "") for r in seed_rows}
    tokens = {kw: brand_token(kw) for kw in keywords}
    results = json.load(open(os.path.join(d, "serp_results.json")))

    dom_brands = collections.defaultdict(set)
    dom_rank, dom_url = {}, {}
    dom_vert = collections.defaultdict(set)
    flat = []
    for kw in keywords:
        for it in results.get(kw, []):
            dom = it.get("domain")
            if not dom:
                continue
            dom_brands[dom].add(kw)
            r = it.get("rank") or 99
            if dom not in dom_rank or r < dom_rank[dom]:
                dom_rank[dom], dom_url[dom] = r, it.get("url")
            dom_vert[dom].add(vertical.get(kw, ""))
            flat.append({"keyword": kw, "rank": it.get("rank"), "domain": dom,
                         "url": it.get("url"), "title": it.get("title")})

    rows = []
    for dom, brands in dom_brands.items():
        nb = len(brands)
        tok = tokens.get(next(iter(brands)), "") if nb == 1 else ""
        if dom in NOISE:
            motion, fit = "off-topic", 0
        elif dom in RETAIL:
            motion, fit = "retail", 0
        elif nb == 1 and tok and tok in sld(dom):
            motion, fit = "owned", 0
        else:
            base = 40 + 12 * nb + (15 if dom in AUTHORITY else 0)
            fit = min(100, base + {1: 10, 2: 8, 3: 6}.get(dom_rank[dom], 3))
            motion = "review-target"
        rows.append({"domain": dom, "brands_covered": nb,
                     "brands": "; ".join(sorted(b.replace(" reviews", "").replace(" review", "") for b in brands)),
                     "verticals": "; ".join(sorted(v for v in dom_vert[dom] if v)),
                     "best_rank": dom_rank[dom], "motion": motion, "fit_score": fit,
                     "sample_url": dom_url.get(dom, "")})
    rows.sort(key=lambda x: (x["motion"] != "review-target", -x["fit_score"], -x["brands_covered"]))

    with open(os.path.join(d, "opportunities.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["domain", "brands_covered", "brands", "verticals",
                                           "best_rank", "motion", "fit_score", "sample_url"])
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(d, "results.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["keyword", "rank", "domain", "url", "title"])
        w.writeheader()
        w.writerows(flat)

    by = collections.Counter(r["motion"] for r in rows)
    sys.stderr.write("WROTE {}/opportunities.csv  ({} domains: {})\n".format(d, len(rows), dict(by)))
    sys.stderr.write("Top review-targets (domain | fit | brands | verticals):\n")
    for r in [x for x in rows if x["motion"] == "review-target"][:18]:
        sys.stderr.write("  {:<30} {:>3}  {:>2}  {}\n".format(
            r["domain"], r["fit_score"], r["brands_covered"], r["verticals"]))


if __name__ == "__main__":
    main()
