#!/usr/bin/env python3
"""
serp_scan.py — Bellwether Scout, web-partner lane.

Where /yt-scan asks "which creators does a comparable brand rebook", this asks
"who already ranks in front of this brand's buyers". Approved seed keywords in,
a ranked list of candidate partner domains out.

Ported 2026-09-23 from close-demo/scripts/serp_research.py (~/Desktop/serp-tracker),
which ran live for Close, Rarity7, NAC and dtc-reviews. Changes made in the port:

  * stdlib urllib instead of requests — nac's python3 (3.7.2) has no requests,
    and donor_trail.py already set the no-dependency precedent.
  * seeds come from briefs/seeds/<brand>.csv and only rows marked `approved`.
    That file IS the seed gate; the script refuses to invent its own list.
  * spend is capped before the first call (see _budget.py). SerpAPI is on the
    free plan and is shared with the SERP Tracker's client rank checks.
  * output is aggregated per domain, not per result row, because the unit of
    decision is a partner, not a link.
  * candidates already in creators.csv or outreach.csv are flagged, not dropped:
    an existing partner ranking for a new seed is a signal, not a duplicate.

Two behaviours carried over deliberately, both learned the expensive way:

  1. no_cache=true on every call. On 2026-07-30 SerpAPI served cached results for
     the FIRST WORD of several multi-word queries ("reputable rare coin dealers"
     came back as dictionary pages for "reputable"). A wrong SERP silently
     corrupts the whole shortlist.
  2. Every page is checked for that same truncation and retried up to 3 times,
     then dropped with a warning rather than kept.

Usage:
  python3 scripts/serp_scan.py rarity7 --dry-run
  python3 scripts/serp_scan.py rarity7 --depth 20 --yes
  python3 scripts/serp_scan.py homeaglow --keywords "best house cleaning service review"
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _budget  # noqa: E402
from _keys import require  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]  # bellwether/
ENDPOINT = "https://serpapi.com/search.json"
ACCOUNT = "https://serpapi.com/account.json"
TIMEOUT = 60

# Mirror of nacww_serp_tracker.py NOISE_DOMAINS. Keep in sync; the tracker is the
# source of truth and must not be edited from here.
NOISE_DOMAINS = {
    "reddit.com", "bbb.org", "yelp.com", "trustpilot.com", "youtube.com",
    "tiktok.com", "facebook.com", "m.youtube.com", "m.facebook.com",
    "m.yelp.com", "instagram.com", "twitter.com", "x.com", "pinterest.com",
    "linkedin.com",
}

# Reference domains that flood a SERP when only the query's first word was
# actually searched — the tell for the truncation failure above.
DEFINITION_DOMAINS = {
    "merriam-webster.com", "dictionary.cambridge.org", "dictionary.com",
    "vocabulary.com", "collinsdictionary.com", "thesaurus.com",
    "en.wiktionary.org", "oxfordlearnersdictionaries.com", "britannica.com",
}
STOPWORDS = {"a", "an", "the", "to", "for", "of", "in", "on", "vs", "and", "or", "is", "are"}
# Commercial qualifiers: they lead the query but are not its subject, and a
# roundup rarely repeats them verbatim.
QUALIFIERS = {"best", "top", "good", "great", "cheap", "cheapest", "new", "most", "how"}


# --- http ---------------------------------------------------------------------

def _get_json(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": "bellwether-serp-scan/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def searches_left(key):
    """What SerpAPI says is left this month, or None if it cannot be read."""
    try:
        data = _get_json(ACCOUNT, {"api_key": key})
    except Exception:
        return None
    left = data.get("total_searches_left")
    return left if isinstance(left, int) else data.get("plan_searches_left")


def is_noise(domain):
    """True for a noise domain or any subdomain of one. Exact matching let
    ie.trustpilot.com and nz.trustpilot.com through on 2026-10-06."""
    parts = domain.split(".")
    return any(".".join(parts[i:]) in NOISE_DOMAINS for i in range(len(parts) - 1))


def domain_of(url):
    netloc = urllib.parse.urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


# Every request sent, counted at the moment it is sent. The per-seed tally this
# replaced lost a seed's spend whenever the seed errored: on 2026-10-06 the
# Hungryroot retries and every charged timeout vanished from the ledger. A
# request that times out may or may not be billed, so this errs high, which is
# the right direction for a budget.
SENT = {"n": 0}


def fetch(key, query, start):
    SENT["n"] += 1
    data = _get_json(ENDPOINT, {
        "engine": "google", "q": query, "api_key": key,
        "num": 10, "start": start,
        "location": "San Francisco, California, United States",
        "google_domain": "google.com", "gl": "us", "hl": "en", "device": "desktop",
        "no_cache": "true",
    })
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


def looks_off_query(query, results):
    """True if these results answer something other than the query.

    Two ways a SERP comes back wrong, and both have been seen in production:

      first word only   2026-07-30, SerpAPI cache: "reputable rare coin dealers"
                        returned dictionary pages for "reputable". Caught by the
                        tail check: none of the later words appear anywhere.
      last word only    2026-10-02: "magnesium glycinate benefits for women"
                        returned UN Women, Wikipedia's "Woman", healthcare.gov and
                        the NCAA women's tournament. The tail check PASSED, because
                        "women" is a tail word and it was everywhere. Nothing about
                        magnesium. Hence the head check below.

    The anchor is the query's most distinctive word, approximated by its longest
    one. A real SERP for "magnesium glycinate benefits for women" says glycinate
    somewhere; one that does not is answering a different question. Anchoring on
    the FIRST word instead was tried and was wrong: "how to choose a women's
    multivitamin" returns pages that never say "choose", and flagging those threw
    away a perfectly real SERP.
    """
    top = results[:6]
    if not top:
        return False
    if sum(1 for r in top if r["domain"] in DEFINITION_DOMAINS) >= 2:
        return True
    blob = re.sub(r"[^a-z0-9 ]+", " ",
                  " ".join((r.get("title") or "") + " " + r["url"] for r in top).lower())
    words = [w for w in re.sub(r"[^a-z0-9 ]+", " ", query.lower()).split()
             if w not in STOPWORDS and len(w) > 2]
    if not words:
        return False
    subject = [w for w in words if w not in QUALIFIERS] or words
    anchor = max(subject, key=len)
    # Match loosely on form, strictly on subject. "hungryroot reviews" was flagged
    # twice on 2026-10-06 for two reasons at once: reviewers write "Hungry Root"
    # as two words, and titles say "Review", not "reviews". Neither means the
    # SERP is about something else, so spacing and a plural s are ignored.
    nospace = blob.replace(" ", "")

    def present(word):
        forms = {word, word[:-1] if len(word) > 3 and word.endswith("s") else word}
        return any(f in blob or f in nospace for f in forms)

    if not present(anchor):
        return True
    tail = words[1:]
    return bool(tail) and not any(present(w) for w in tail)


def scan_query(key, query, pages):
    """Organic results for one seed, noise-filtered. -> (results, searches_spent)"""
    out, seen, spent, dropped = [], set(), 0, 0
    for page in range(pages):
        start = page * 10
        rows = []
        for attempt in range(3):
            data = fetch(key, query, start)
            spent += 1
            rows = []
            for item in data.get("organic_results", []):
                url = item.get("link", "")
                if not url or is_noise(domain_of(url)) or url in seen:
                    continue
                rows.append({
                    "rank": item.get("position"),
                    "url": url,
                    "domain": domain_of(url),
                    "title": item.get("title"),
                    "snippet": item.get("snippet", ""),
                })
            if not looks_off_query(query, rows):
                break
            sys.stderr.write("  [{}] start={} does not answer the query (attempt {}/3)\n".format(
                query, start, attempt + 1))
            rows = []
            time.sleep(3)
        if rows:
            for r in rows:
                seen.add(r["url"])
            out.extend(rows)
        else:
            dropped += 1
            sys.stderr.write("  [{}] WARNING: start={} still contaminated after 3 tries; dropped\n".format(
                query, start))
        time.sleep(1)
    if dropped:
        sys.stderr.write("  [{}] {} of {} pages dropped as contaminated\n".format(query, dropped, pages))
    return out, spent


# --- inputs -------------------------------------------------------------------

def mark_scanned(path, scanned, slate, replayed=False):
    """Seeds this run searched successfully go from `approved` to `done`, so the
    next run doesn't pay for them again (2026-11-04: a dry run re-planned two
    brands searched that morning). To search one again, approve it again with
    seed_status.py: approving is the permission to spend. On a demo brief a seed
    replayed from saved results is marked done the same way (D27). -> how many changed."""
    lines = path.read_text().splitlines(keepends=True)
    head = [l for l in lines if l.lstrip().startswith("#")]
    rows = list(csv.DictReader([l for l in lines if not l.lstrip().startswith("#")]))
    if not rows:
        return 0
    stamp = "{} {} (slate {})".format("replayed from saved results" if replayed else "searched",
                                      date.today().isoformat(), slate)
    n = 0
    for r in rows:
        if r.get("keyword") in scanned and (r.get("status") or "").strip().lower() == "approved":
            r["status"] = "done"
            r["note"] = stamp + ("; " + r["note"] if r.get("note") else "")
            n += 1
    with path.open("w", newline="") as fh:
        fh.writelines(head)
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    return n


def read_seeds(path):
    """Approved rows only. -> (approved, counts_by_status)"""
    with path.open() as fh:
        rows = list(csv.DictReader([ln for ln in fh if not ln.lstrip().startswith("#")]))
    counts = {}
    approved = []
    for row in rows:
        keyword = (row.get("keyword") or "").strip()
        status = (row.get("status") or "").strip().lower() or "proposed"
        if not keyword:
            continue
        counts[status] = counts.get(status, 0) + 1
        if status == "approved":
            approved.append(keyword)
    return approved, counts


def read_exclusions(path):
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            out.add(line[4:] if line.startswith("www.") else line)
    return out


def read_column(path, column, where=None):
    """A set of lowercased values from one CSV column, optionally filtered."""
    if not path.exists():
        return set()
    out = set()
    with path.open() as fh:
        for row in csv.DictReader(fh):
            if where and not where(row):
                continue
            val = (row.get(column) or "").strip().lower()
            if val:
                out.add(val[4:] if val.startswith("www.") else val)
    return out


# --- main ---------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="SERP scan for a brand's approved seed keywords.")
    ap.add_argument("brand", help="brief slug: reads briefs/<slug>/seeds.csv")
    ap.add_argument("--slate", default=date.today().strftime("%Y-%m"), help="slate, default this month")
    ap.add_argument("--depth", type=int, default=20, choices=[10, 20, 30, 40, 50],
                    help="organic results per seed (1 search per 10), default 20")
    ap.add_argument("--seeds", help="override the seeds CSV path")
    ap.add_argument("--keywords", nargs="*", help="ad-hoc keywords instead of the seeds file")
    ap.add_argument("--limit", type=int, metavar="N",
                    help="run only the first N approved seeds. For trying a new seed list "
                         "cheaply, or for a demo that has to fit in a minute.")
    ap.add_argument("--dry-run", action="store_true", help="plan and budget only; spend nothing")
    ap.add_argument("--yes", action="store_true", help="approve a run over the confirm threshold")
    ap.add_argument("--live", action="store_true",
                    help="on a demo brief, search for real instead of replaying saved results (D27)")
    args = ap.parse_args()

    key = require("SERP_API_KEY")
    pages = max(1, args.depth // 10)
    import _paths
    out_dir = _paths.raw_dir(args.brand)   # one folder per brand (CHANGELOG D25)
    seeds_path = Path(args.seeds) if args.seeds else ROOT / "briefs" / args.brand / "seeds.csv"

    # 1. Seeds — the gate. Ad-hoc keywords are allowed because Nicole typed them.
    if args.keywords:
        seeds, source = args.keywords, "--keywords (ad-hoc)"
    else:
        if not seeds_path.exists():
            sys.exit("no seed list at {}\n"
                     "  create briefs/{}/ from briefs/_template/ first, or pass --keywords for a one-off."
                     .format(seeds_path, args.brand))
        seeds, counts = read_seeds(seeds_path)
        source = str(seeds_path.relative_to(ROOT))
        if not seeds:
            tally = ", ".join("{} {}".format(v, k) for k, v in sorted(counts.items())) or "none"
            sys.exit("no seeds marked `approved` in {} ({}).\n"
                     "  The seed list is a gate: mark the ones to run as `approved` first."
                     .format(source, tally))

    # A slice of the approved list, not a way around it: the seeds still come
    # from the file, so the gate still decided which ones were allowed to run.
    if args.limit and args.limit < len(seeds):
        source += " (--limit {} of {})".format(args.limit, len(seeds))
        seeds = seeds[:args.limit]

    # 1b. A demo brief replays a seed searched before instead of paying for it
    # again (D27: a rehearsal reset the seeds, and the next run re-bought 6 of
    # its 10 searches). A seed with nothing saved is left approved, not searched.
    demo = _paths.is_demo(args.brand) and not args.live
    replay = []
    if demo:
        saved_path = out_dir / "serp-results.json"
        try:
            saved = json.loads(saved_path.read_text()) if saved_path.exists() else {}
        except ValueError:
            saved = {}
        replay = [s for s in seeds if s in saved]
        missing = [s for s in seeds if s not in saved]
        print("SERP scan · {} · slate {}".format(args.brand, args.slate))
        print("  " + _paths.DEMO_LINE)
        print("  replaying {} of {} seed(s) from saved results: 0 searches".format(len(replay), len(seeds)))
        if missing:
            print("  not saved, so not searched (still approved; --live searches them): {}".format(
                ", ".join(missing)))
        if args.dry_run:
            print("\ndry run — nothing spent, nothing changed.")
            return 0
        if not replay:
            return _budget.DEMO
        seeds = []

    # 2. Budget, before anything is spent.
    planned = len(seeds) * pages
    remaining = None if demo else searches_left(key)
    code, lines = (_budget.OK, []) if demo else _budget.gate(
        "serpapi", planned, remaining, yes=args.yes, brand=args.brand, live=args.live)

    if not demo:
        print("SERP scan · {} · slate {}".format(args.brand, args.slate))
        print("seeds: {} from {} · depth {} ({} pages each)".format(len(seeds), source, args.depth, pages))
    for line in lines:
        print("  " + line)

    if args.dry_run:
        print("\ndry run — nothing spent. Seeds:")
        for s in seeds:
            print("  · {}".format(s))
        return 0
    if code != _budget.OK:
        return code

    # 3. Scan.
    known_sites = read_column(ROOT / "data" / "creators.csv", "handle",
                              where=lambda r: (r.get("platform") or "").lower() == "web")
    contacted = read_column(ROOT / "data" / "outreach.csv", "domain")
    excluded = read_exclusions(ROOT / "briefs" / args.brand / "exclusions.txt")

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "serp-results.json"
    raw = {}
    if raw_path.exists():
        try:
            raw = json.loads(raw_path.read_text())
        except ValueError:
            raw = {}

    failed, stopped_at = [], None
    latest = {}
    reserve = (_budget.budgets().get("serpapi") or {}).get("reserve") or 0
    # Balance as of the last account reading, and how much had been sent then.
    # Between readings the estimate is that balance minus what this run has sent
    # since; each fresh reading re-bases it, so spend from elsewhere (the tracker)
    # is never forgotten again after it has been seen once.
    base_left, base_sent = remaining, 0
    try:
        for i, seed in enumerate(seeds, 1):
            # The up-front gate cannot see retries and timeouts, so check again
            # before every seed. Re-ask the account every 10 seeds (free) to
            # catch anything else spending from it in parallel, e.g. the tracker.
            if remaining is not None:
                if i % 10 == 1 and i > 1:
                    fresh = searches_left(key)
                    if fresh is not None:
                        base_left, base_sent = fresh, SENT["n"]
                left = base_left - (SENT["n"] - base_sent)
                if left - pages < reserve:
                    stopped_at = i
                    sys.stderr.write("  STOPPED at {}/{}: {} searches left, the next seed would go under "
                                     "the reserve of {}\n".format(i, len(seeds), left, reserve))
                    break
            sys.stderr.write("[{}/{}] {}\n".format(i, len(seeds), seed))
            try:
                rows, _ = scan_query(key, seed, pages)
            except Exception as exc:
                failed.append(seed)
                sys.stderr.write("  ERROR: {}\n".format(str(exc)[:160]))
                continue
            latest[seed] = rows
            raw[seed] = rows
            sys.stderr.write("  {} results\n".format(len(rows)))
    finally:
        # Log whatever was sent, even if the run died halfway.
        spent = SENT["n"]
        if spent:
            _budget.log("serpapi", spent, "searches", "serp-scan", args.brand, args.slate,
                        "{} of {} seeds x {} pages{}{}".format(
                            len(latest), len(seeds), pages,
                            "; {} failed".format(len(failed)) if failed else "",
                            "; stopped at reserve" if stopped_at else ""))
        if not demo:
            raw_path.write_text(json.dumps(raw, indent=2))
        done_now = set(replay) if demo else set(latest)
        if done_now and not args.keywords:
            n = mark_scanned(seeds_path, done_now, args.slate, replayed=demo)
            if n:
                sys.stderr.write("  {} seed(s) marked done in {}\n".format(n, seeds_path.relative_to(ROOT)))

    # 4. Aggregate per domain — the unit of decision is a partner, not a link.
    # Aggregate over EVERY seed known for this brand and slate, not just the ones
    # this run touched. Re-running one seed used to rewrite the file from that
    # seed alone, silently dropping the other thirteen from the deliverable.
    agg, dropped = {}, []
    for seed, rows in raw.items():
        for row in rows:
            dom = row["domain"]
            if dom in excluded:
                dropped.append({"domain": dom, "reason": "brief exclusion list",
                                "seed": seed, "url": row["url"]})
                continue
            rec = agg.setdefault(dom, {
                "domain": dom, "seeds_covered": 0, "best_rank": 999,
                "seeds": [], "urls": [], "titles": [],
            })
            rec["seeds_covered"] += 1
            rec["seeds"].append(seed)
            rec["urls"].append(row["url"])
            rec["titles"].append(row.get("title") or "")
            if row.get("rank") and row["rank"] < rec["best_rank"]:
                rec["best_rank"] = row["rank"]
                rec["best_url"] = row["url"]

    ranked = sorted(agg.values(), key=lambda r: (-r["seeds_covered"], r["best_rank"]))
    today = date.today().isoformat()
    with (out_dir / "serp-domains.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["domain", "status", "seeds_covered", "best_rank", "best_url",
                         "seeds", "titles", "first_seen"])
        for rec in ranked:
            if rec["domain"] in contacted:
                status = "contacted"
            elif rec["domain"] in known_sites:
                status = "known"
            else:
                status = "new"
            writer.writerow([
                rec["domain"], status, rec["seeds_covered"],
                rec["best_rank"] if rec["best_rank"] < 999 else "",
                rec.get("best_url", rec["urls"][0]),
                " | ".join(rec["seeds"][:6]),
                " | ".join(t[:80] for t in rec["titles"][:3]),
                today,
            ])
    if dropped:
        with (out_dir / "serp-excluded.csv").open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["domain", "reason", "seed", "url"])
            writer.writeheader()
            writer.writerows(dropped)

    # 5. Report.
    print("\n{} domains from {} seeds on file ({} {} now) · {} searches spent".format(
        len(ranked), len(raw), len(replay) if demo else len(latest), "replayed" if demo else "run", spent))
    if failed:
        print("failed seeds ({}): {}".format(len(failed), ", ".join(failed)))
    if stopped_at:
        print("stopped at seed {} of {} to keep the reserve of {}; the rest did not run".format(
            stopped_at, len(seeds), reserve))
    if dropped:
        print("excluded: {} results on the brief's exclusion list".format(len(dropped)))
    print()
    print("{:<34} {:>6} {:>5}  {}".format("DOMAIN", "SEEDS", "RANK", "STATUS"))
    for rec in ranked[:20]:
        status = ("contacted" if rec["domain"] in contacted
                  else "known" if rec["domain"] in known_sites else "")
        print("{:<34} {:>6} {:>5}  {}".format(
            rec["domain"][:34], rec["seeds_covered"],
            rec["best_rank"] if rec["best_rank"] < 999 else "-", status))
    left = None if demo else searches_left(key)
    print("\nwrote {}".format((out_dir / "serp-domains.csv").relative_to(ROOT)))
    if left is not None:
        print("SerpAPI: {:,} searches left this month".format(left))
    print("next: /score-partners {}".format(args.brand))
    return 0


if __name__ == "__main__":
    sys.exit(main())
