#!/usr/bin/env python3
"""
snowball_brands.py — what else have our reviewers reviewed? Brand ideas for seeds.

The logic the whole web lane runs on: a site that reviewed one brand in a
category is the likeliest to review the next. So the best seed brands are the
ones our reviewers already cover. This reads each review site's sitemap and RSS
feed, keeps the "[X] review(s)" and "[X] vs [Y]" posts, and counts how many
DIFFERENT sites cover each name. A name five creator blogs reviewed is a proven
seed; a name one site reviewed is a guess.

Free: public sitemaps and feeds only. No SerpAPI, no Hunter, no spend.

It counts; it does not judge. The output still holds ordinary words ("air",
"best"), retailers, legacy brands and closed companies, and some real brands are
ordinary words (a dictionary flag marks them, it does not drop them). Sorting
brands from noise is the /snowball command's next step, done in-session, and
nothing becomes a seed until Nicole approves it (CHANGELOG D22).

Starting sites, any CSV with a `domain` (or `website` / `url` / `site`) column:
  - a brief's own site-profiles.csv from /run-seeds (the default);
  - another brief's pool, when the categories overlap;
  - a client's existing affiliate or creator partners, exported from the network.

Writes outputs/<slug>/<slate>/snowball-names.csv: domains and counts only, no
addresses.

Usage:
  python3 scripts/snowball_brands.py affiliate-seo-creators
  python3 scripts/snowball_brands.py new-client --sites outputs/affiliate-seo-creators/2026-10/site-profiles.csv
  python3 scripts/snowball_brands.py new-client --sites ~/Downloads/partners.csv --dry-run
"""

from __future__ import annotations

import argparse
import collections
import csv
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import site_profile  # noqa: E402  (fetch: one user agent and timeout for every page read)

LOC = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*([^<\]\s]+)", re.I)
# Words around a reviewed name that are never the name itself.
FILLER = set("""my our an a the honest full detailed in depth indepth unbiased real independent hands on
tested test testing i we tried brutally after year years month months week weeks update updated new latest
is it worth buying buy should you complete ultimate expert dietitian dietitians mom moms review reviews
reviewed and of for with from by vs versus""".split())
# Never a brand on their own, whatever a dictionary says.
NEVER = set("""best top cheap budget how why what which when where who this that these those one two three
four five your all more most good great free online""".split())
DICT = Path("/usr/share/dict/words")
MAX_SITEMAPS = 12          # per site: an index plus its post sitemaps, not every image map


def domain_of(value):
    v = (value or "").strip().lower()
    if not v:
        return ""
    host = urllib.parse.urlparse(v if "//" in v else "https://" + v).netloc
    return host[4:] if host.startswith("www.") else host


def load_sites(path, include_media):
    """-> [(domain, tier)] from any CSV with a domain-like column."""
    with Path(path).expanduser().open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit("{} is empty".format(path))
    cols = {c.lower().strip(): c for c in rows[0]}
    col = next((cols[c] for c in ("domain", "website", "url", "site") if c in cols), None)
    if not col:
        sys.exit("{} needs a `domain` (or website / url / site) column".format(path))
    tier_col = cols.get("tier")
    out, seen = [], set()
    for r in rows:
        d = domain_of(r[col])
        tier = (r.get(tier_col) or "").strip() if tier_col else ""
        if not d or d in seen or (tier.startswith("media") and not include_media):
            continue
        seen.add(d)
        out.append((d, tier))
    return out


def review_pages(domain):
    """-> (post URLs from the sitemaps, titles from the RSS feed)."""
    base = "https://" + domain
    status, robots = site_profile.fetch(base + "/robots.txt")
    maps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots) if status == 200 else []
    maps = maps or [base + p for p in ("/sitemap_index.xml", "/sitemap.xml", "/wp-sitemap.xml")]
    seen, urls, todo = set(), set(), list(maps)
    while todo and len(seen) < MAX_SITEMAPS:
        m = todo.pop(0)
        if m in seen or m.endswith(".gz"):
            continue
        seen.add(m)
        status, xml = site_profile.fetch(m)
        if status != 200 or not xml:
            continue
        locs = LOC.findall(xml)
        if "<sitemapindex" in xml[:2000].lower():
            kids = [l for l in locs if re.search(r"post|blog|review|article|sitemap\d", l, re.I)] or locs
            todo.extend(k for k in kids if not re.search(r"image|video|author|tag|categor|product_cat", k, re.I))
        else:
            urls.update(locs)
    status, feed = site_profile.fetch(base + "/feed/")
    titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", feed or "", re.S)[1:]
    return urls, titles


def reviewed_names(tokens):
    """Words before "review", or each side of "vs" -> [name tokens]."""
    t = [x for x in tokens if x and not x.isdigit()]
    out = []
    for vs in ("vs", "versus"):
        if vs in t:
            i = t.index(vs)
            out += [[x for x in t[:i] if x not in FILLER][-3:], [x for x in t[i + 1:] if x not in FILLER][:3]]
            break
    for k in ("review", "reviews", "reviewed"):
        if k in t:
            i = t.index(k)
            before = [x for x in t[:i] if x not in FILLER]
            out.append(before[-4:] if before else [x for x in t[i + 1:] if x not in FILLER][:3])
            break
    return [p for p in out if p and p[0] not in NEVER]


def names_on(domain):
    """Every name one site has reviewed, once per site: a site with 40 posts on a
    brand counts the same as a site with one, so coverage means breadth."""
    try:
        urls, titles = review_pages(domain)
    except Exception:
        return domain, set(), False
    found = set()
    for u in urls:
        slug = urllib.parse.urlparse(u).path.lower().strip("/").split("/")[-1]
        if re.search(r"review|-vs-|versus", slug):
            for p in reviewed_names(re.split(r"[-_]+", re.sub(r"\.html?$", "", slug))):
                found.update({p[0], " ".join(p[:2])})
    for t in titles:
        if re.search(r"review|\bvs\b", t, re.I):
            for p in reviewed_names(re.findall(r"[a-z0-9']+", t.lower())):
                found.update({p[0], " ".join(p[:2])})
    return domain, found, bool(urls or titles)


def seeded_names(slug):
    path = ROOT / "briefs" / slug / "seeds.csv"
    if not path.exists():
        return set()
    with path.open() as fh:
        brands = {re.sub(r"[^a-z0-9 ]", "", (r.get("brand") or "").lower()).strip() for r in csv.DictReader(fh)}
    return {b for b in brands if b} | {b.split()[0] for b in brands if b}


def main():
    ap = argparse.ArgumentParser(description="Count what our review sites have reviewed: brand ideas for seeds.")
    ap.add_argument("slug", help="the brief the seeds are for; also where the output goes")
    ap.add_argument("--sites", help="starting sites CSV (default: this brief's site-profiles.csv for the slate)")
    ap.add_argument("--slate", default=date.today().strftime("%Y-%m"))
    ap.add_argument("--include-media", action="store_true", help="also read media / publisher sites (noisy)")
    ap.add_argument("--min-sites", type=int, default=2, help="keep names covered by at least this many sites")
    ap.add_argument("--limit", type=int, help="read only the first N sites (a quick test)")
    ap.add_argument("--dry-run", action="store_true", help="show what would be read; fetch nothing")
    args = ap.parse_args()

    sites_path = Path(args.sites).expanduser() if args.sites else \
        ROOT / "outputs" / args.slug / args.slate / "site-profiles.csv"
    if not sites_path.exists():
        sys.exit("no starting sites at {}. Run /run-seeds {} first, or pass --sites with another brief's "
                 "site-profiles.csv or a partner list.".format(sites_path, args.slug))
    sites = load_sites(sites_path, args.include_media)[:args.limit or None]
    print("Snowball · {} · {} starting sites from {}".format(args.slug, len(sites), sites_path.name))
    print("  free: sitemaps and RSS feeds only, no paid API")
    if args.dry_run:
        print("dry run — nothing fetched.")
        return 0

    tier = dict(sites)
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda s: names_on(s[0]), sites))
    cover, creators = collections.defaultdict(set), collections.defaultdict(set)
    readable = 0
    for d, names, ok in results:
        readable += ok
        for n in names:
            cover[n].add(d)
            if tier.get(d) == "creator blog":
                creators[n].add(d)

    seeded = seeded_names(args.slug)
    words = {w.strip().lower() for w in DICT.open()} if DICT.exists() else set()
    keep = sorted(((n, ds) for n, ds in cover.items() if len(ds) >= args.min_sites),
                  key=lambda kv: (-len(creators[kv[0]]), -len(kv[1]), kv[0]))
    out_dir = ROOT / "outputs" / args.slug / args.slate
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "snowball-names.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "sites", "creator_sites", "seeded", "common_word", "example_sites"])
        for n, ds in keep:
            w.writerow([n, len(ds), len(creators[n]), "yes" if (n in seeded or n.split()[0] in seeded) else "",
                        "yes" if n in words else "", " ".join(sorted(ds)[:8])])

    print("  read {} of {} sites (the rest have no sitemap or feed, or refused the fetch)".format(
        readable, len(sites)))
    print("  {} names covered by {}+ sites".format(len(keep), args.min_sites))
    print("\nTop names not already seeded (creator blogs / all sites):")
    shown = 0
    for n, ds in keep:
        if n in seeded or n.split()[0] in seeded or n in words or n in NEVER:
            continue
        print("  {:>2} / {:<3} {}".format(len(creators[n]), len(ds), n))
        shown += 1
        if shown == 40:
            break
    print("\nwrote {}".format(out.relative_to(ROOT)))
    print("next: sort brands from noise, then propose seeds (the /snowball command does this).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
