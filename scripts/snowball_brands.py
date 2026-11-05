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

Writes briefs/<slug>/snowball.csv, beside the brief (CHANGELOG D25): domains and counts only, no
addresses. Each site's read is kept in snowball-reads.json beside it and reused
for 24 hours, so a run on stage doesn't depend on the wifi (CHANGELOG D23).

Usage:
  python3 scripts/snowball_brands.py affiliate-seo-creators
  python3 scripts/snowball_brands.py braise                 (starts from briefs/braise/review-sites.csv)
  python3 scripts/snowball_brands.py braise --refresh       (read every site again)
  python3 scripts/snowball_brands.py new-client --sites briefs/affiliate-seo-creators/review-sites.csv
  python3 scripts/snowball_brands.py new-client --sites ~/Downloads/partners.csv --dry-run
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
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
        # Editors such as Nimbalyst keep their view settings on a "# ..." first line.
        rows = list(csv.DictReader(line for line in fh if not line.startswith("#")))
    if not rows:
        sys.exit("{} is empty".format(path))
    cols = {c.lower().strip(): c for c in rows[0]}
    col = next((cols[c] for c in ("domain", "website", "url", "site") if c in cols), None)
    if not col:
        sys.exit("{} needs a `domain` (or website / url / site) column".format(path))
    # A hand-set "site type" (Nicole's categories) beats the tool's own "tier" guess.
    # A list someone categorized by hand is already curated, so its media sites stay
    # in; only the tool's own media guess is skipped by default (Nicole, 2026-11-04).
    hand = cols.get("site type")
    tier_col = hand or cols.get("tier")
    out, seen = [], set()
    for r in rows:
        d = domain_of(r[col])
        tier = (r.get(tier_col) or "").strip().lower() if tier_col else ""
        if tier in ("competitor brand", "wrong match"):
            continue
        if not d or d in seen or (tier.startswith("media") and not (include_media or hand)):
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


def edges(words):
    """Filler off the two ends only. Brands carry filler words inside them (Made In,
    The Farmer's Dog), so stripping every "in" turned Made In into "made"."""
    i, j = 0, len(words)
    while i < j and words[i] in FILLER:
        i += 1
    while j > i and words[j - 1] in FILLER:
        j -= 1
    return words[i:j]


def reviewed_names(tokens):
    """Words before "review", or each side of "vs" -> [name tokens]."""
    t = [x for x in tokens if x and not x.isdigit()]
    out = []

    def add(raw, keep_tail):
        core = edges(raw)
        core = edges(core[-keep_tail:] if keep_tail > 0 else core[:-keep_tail])
        if not core:
            return
        out.append(core)
        # A brand that starts with a filler word (Our Place) is one word once the
        # filler goes, so keep the filler word and that word together as well.
        if len(core) == 1:
            k = raw.index(core[0])
            if k > 0 and raw[k - 1] in FILLER:
                out.append(raw[k - 1:k + 1])

    for vs in ("vs", "versus"):
        if vs in t:
            i = t.index(vs)
            add(t[:i][-4:], 3)
            add(t[i + 1:i + 5], -3)
            break
    for k in ("review", "reviews", "reviewed"):
        if k in t:
            i = t.index(k)
            add(t[:i][-6:], 5) if edges(t[:i]) else add(t[i + 1:i + 5], -3)
            break
    return [p for p in out if p and p[0] not in NEVER]


def name_forms(p):
    """The names one parsed phrase stands for: its first word, its first two words,
    and for "X and Y" brands (Tuft & Needle, Boll & Branch) both "x and y" and "x y",
    since sites write the slug both ways."""
    forms = {p[0], " ".join(p[:2])}
    if len(p) >= 3 and p[1] in ("and", "n"):
        forms |= {" ".join(p[:3]), p[0] + " " + p[2]}
    return forms


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
                found.update(name_forms(p))
    for t in titles:
        if re.search(r"review|\bvs\b", t, re.I):
            for p in reviewed_names(re.findall(r"[a-z0-9']+", t.lower())):
                found.update(name_forms(p))
    return domain, found, bool(urls or titles)


def seeded_names(slug):
    path = ROOT / "briefs" / slug / "seeds.csv"
    if not path.exists():
        return set()
    with path.open() as fh:
        brands = {re.sub(r"[^a-z0-9 ]", "", (r.get("brand") or "").lower()).strip() for r in csv.DictReader(fh)}
    return {b for b in brands if b} | {b.split()[0] for b in brands if b}


REUSE_HOURS = 24           # a read this recent is reused unless --refresh (demo-safe on bad wifi)


def load_reads(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def main():
    ap = argparse.ArgumentParser(description="Count what our review sites have reviewed: brand ideas for seeds.")
    ap.add_argument("slug", help="the brief the seeds are for; also where the output goes")
    ap.add_argument("--sites", help="starting sites CSV (default: briefs/<slug>/starting-sites.csv, else "
                                    "briefs/<slug>/review-sites.csv; "
                                    "else this brief's site-profiles.csv for the slate)")
    ap.add_argument("--slate", default=date.today().strftime("%Y-%m"))
    ap.add_argument("--include-media", action="store_true", help="also read media / publisher sites (noisy)")
    ap.add_argument("--min-sites", type=int, default=2, help="keep names covered by at least this many sites")
    ap.add_argument("--limit", type=int, help="read only the first N sites (a quick test)")
    ap.add_argument("--refresh", action="store_true",
                    help="read every site again, even if it was read in the last {} hours".format(REUSE_HOURS))
    ap.add_argument("--dry-run", action="store_true", help="show what would be read; fetch nothing")
    ap.add_argument("--live", action="store_true",
                    help="on a demo brief, read sites as usual instead of only replaying saved reads (D27)")
    args = ap.parse_args()

    # A brief can keep its own hand-curated starting list (an input, so it lives
    # with the brief). Otherwise: the review sites the brief already has.
    import _paths
    own = _paths.brief_dir(args.slug) / "starting-sites.csv"
    sites_path = Path(args.sites).expanduser() if args.sites else \
        own if own.exists() else _paths.review_sites(args.slug)
    if not sites_path.exists():
        sys.exit("no starting sites at {}. Run /run-seeds {} first, add briefs/{}/starting-sites.csv, or pass "
                 "--sites with another brief's site-profiles.csv or a partner list.".format(
                     sites_path, args.slug, args.slug))
    sites = load_sites(sites_path, args.include_media)[:args.limit or None]
    shown_path = sites_path.relative_to(ROOT) if ROOT in sites_path.parents else sites_path.name

    # Each site's read is kept, so a run later the same day (on stage, say) reuses
    # it instead of reading every sitemap again, and only new sites get read.
    reads_path = _paths.raw_dir(args.slug) / "snowball-reads.json"
    reads = {} if args.refresh else load_reads(reads_path)
    now = datetime.now()
    # A demo brief reuses every saved read, whatever its age, and reads nothing new,
    # so the stage run matches the rehearsal and takes a second (D27).
    demo = _paths.is_demo(args.slug) and not (args.live or args.refresh)
    fresh = {d: r for d, r in reads.items()
             if demo or now - datetime.fromisoformat(r["at"]) < timedelta(hours=REUSE_HOURS)}
    print("Snowball · {} · {} starting sites from {}".format(args.slug, len(sites), shown_path))
    if demo:
        unread = [s for s in sites if s[0] not in fresh]
        sites = [s for s in sites if s[0] in fresh]
        print("  " + _paths.DEMO_LINE)
        if unread:
            print("  {} site(s) never read, so left out (--live reads them)".format(len(unread)))
        if not sites:
            print("  no saved reads for this brief: run /snowball {} --live first.".format(args.slug))
            return 4
    to_read = [s for s in sites if s[0] not in fresh]
    print("  free: sitemaps and RSS feeds only, no paid API")
    if len(to_read) < len(sites):
        oldest = min(datetime.fromisoformat(fresh[s[0]]["at"]) for s in sites if s[0] in fresh)
        print("  reusing the read from {} for {} site(s); reading {} now (--refresh to read all again)".format(
            oldest.strftime("%b %d %H:%M"), len(sites) - len(to_read), len(to_read)))
    if args.dry_run:
        print("dry run — nothing fetched.")
        return 0

    with ThreadPoolExecutor(max_workers=12) as pool:
        for d, names, ok in pool.map(lambda s: names_on(s[0]), to_read):
            fresh[d] = {"at": now.isoformat(timespec="seconds"), "ok": ok, "names": sorted(names)}
    reads_path.write_text(json.dumps(fresh, indent=1))

    tier = dict(sites)
    cover, creators = collections.defaultdict(set), collections.defaultdict(set)
    readable = 0
    for d, _ in sites:
        readable += fresh[d]["ok"]
        for n in fresh[d]["names"]:
            cover[n].add(d)
            if tier.get(d) == "creator blog":
                creators[n].add(d)

    seeded = seeded_names(args.slug)
    words = {w.strip().lower() for w in DICT.open()} if DICT.exists() else set()
    keep = sorted(((n, ds) for n, ds in cover.items() if len(ds) >= args.min_sites),
                  key=lambda kv: (-len(creators[kv[0]]), -len(kv[1]), kv[0]))
    out = _paths.brief_dir(args.slug) / "snowball.csv"
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
        if shown == 60:
            break
    print("\nwrote {}".format(out.relative_to(ROOT)))
    print("next: sort brands from noise, then propose seeds (the /snowball command does this).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
