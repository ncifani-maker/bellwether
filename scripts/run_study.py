#!/usr/bin/env python3
"""
run_study.py — end-to-end donor-trail study.

Chains the two tools described in docs/predictive-discovery-spec.md sec 6:

  1. vendor/youtube-scout/scripts/scout.py   topic search -> ranked workbooks + Channels sheets
  2. scripts/donor_trail.py                  channel-scoped donor scan on FULL descriptions

and writes a ranked markdown report plus the CSV.

The study is defined by a config file, not by arguments, so a run is
reproducible and a second brand is a new config rather than new code:

    python3 scripts/run_study.py --study briefs/studies/homeaglow-hellofresh.json

Resumable: scout workbooks and the merged channel list are cached under the
study's output directory. Re-running skips topics already fetched unless
--refresh is passed, so a failed donor scan does not re-spend search quota
(search.list is 100 units per call; everything else is 1).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _brief  # noqa: E402
from build_workbook import (  # noqa: E402
    build as build_workbook,
    months_since,
    score_and_tier,
)

ROOT = Path(__file__).resolve().parent.parent
SCOUT = ROOT / "vendor" / "youtube-scout" / "scripts" / "scout.py"
DONOR_TRAIL = ROOT / "scripts" / "donor_trail.py"

# Channels that are the scanned brands' own, or obvious non-creator surfaces.
# A study may override this with "brand_channel_pattern": the meal-kit default
# below is wrong for any study that is not the HelloFresh one.
DEFAULT_BRAND_CHANNEL = r"hellofresh|blueapron|homechef|everyplate|factor|hungryroot"


def brand_channel_re(study: dict):
    return re.compile(study.get("brand_channel_pattern") or DEFAULT_BRAND_CHANNEL, re.I)


def exclude_channel_re(study: dict):
    """Optional supply-side screen, off unless a study sets it.

    A marketplace brand behaves differently from a consumer brand. HelloFresh
    appears in a description because someone was paid to put it there. Angi,
    Thumbtack and TaskRabbit also appear in their *providers'* descriptions —
    a contractor citing the platform they are rated on — which is the supply
    side of the marketplace and the exact inverse of the audience we are
    sourcing. This is a title heuristic, so it is deliberately conservative
    and the channels it drops are logged rather than silently discarded.
    """
    pat = study.get("exclude_channel_pattern")
    return re.compile(pat, re.I) if pat else None


def noise_channel_re(study: dict):
    """Topic-homonym screen. Unlike the supply-side screen, this one DROPS.

    A search term can collide with something unrelated, and then the pool fills
    with channels that never had any chance of being a partner. #AngiPartner
    collides with "Agni Parthene", a Greek Orthodox chant: two chant channels
    with 20M views between them entered the Sept 24 pool, and one of them
    outranked every real Angi placement on views.

    Flagging is the right call for the supply-side screen, because a contractor
    channel is a judgment call and the screen can be wrong about it. A homonym
    is not a judgment call. Scanning it is ~4 quota units spent to confirm that
    a Byzantine chant is not sponsored by Angi, so these are dropped before the
    scan and named in candidates.txt so a wrong drop is still visible.
    """
    pat = study.get("noise_channel_pattern")
    return re.compile(pat, re.I) if pat else None


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def run(cmd: list[str], label: str) -> None:
    print(f"\n$ {' '.join(str(c) for c in cmd)}", file=sys.stderr)
    result = subprocess.run([str(c) for c in cmd], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"run_study: {label} failed with exit code {result.returncode}")


def scout_topic(topic, opts: dict, out_dir: Path, refresh: bool) -> Path:
    """A topic is a query string, or {"q": ..., "length": short|medium|long}.

    The length split matters more than it looks. The API orders search results
    by relevance, and a Short puts the brand and the partnership hashtag in its
    TITLE, while a long-form integration is usually titled after the project and
    names the brand only in the description. So a brand query ranks Shorts above
    long-form and, against a 100-result cap, can crowd long-form out entirely.
    Running the same query once per duration band gives each format its own cap
    instead of making them compete.
    """
    if isinstance(topic, dict):
        query, length = topic.get("q", ""), topic.get("length", "any")
    else:
        query, length = topic, "any"
    tag = slug(query) + ("" if length == "any" else f"-{length}")
    book = out_dir / f"scout-{tag}.xlsx"
    if book.is_file() and not refresh:
        print(f"  cached: {book.name}", file=sys.stderr)
        return book
    cmd = [sys.executable, SCOUT] + query.split() + [
        "--max", str(opts.get("max", 100)),
        "--sort", opts.get("sort", "views"),
        "--since", opts.get("since", "any"),
        "--length", length,
        "--out", book,
    ]
    run(cmd, f"scout '{query}' [{length}]")
    return book


def channels_from_workbook(path: Path) -> list[tuple[str, str, str, str]]:
    """Return (ref, title, country, best_video) from a scout workbook's Channels sheet.

    best_video is carried because a channel's name often says nothing about what
    it publishes. The homonym noise on #AngiPartner is the case in point: "May
    All Be One" and "Adoration of the Cross" are unreadable as names, and only
    their best video ("Agni Parthene") shows why they matched.
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        sys.exit("run_study: needs openpyxl. python3 -m pip install --user openpyxl")
    if not path.is_file():
        return []
    wb = load_workbook(path, read_only=True, data_only=True)
    if "Channels" not in wb.sheetnames:
        return []
    rows = wb["Channels"].iter_rows(values_only=True)
    header = [str(c or "").strip().lower() for c in next(rows, [])]

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        return None

    c_ref = col("channel url", "channel id", "channel")
    c_title = col("creator", "channel", "channel title", "title")
    c_country = col("channel country", "country")
    c_best = col("best video", "best video title")
    if c_ref is None:
        return []
    out = []
    for row in rows:
        if not row or c_ref >= len(row) or not row[c_ref]:
            continue
        def cell(i):
            return str(row[i]).strip() if i is not None and i < len(row) and row[i] else ""
        out.append((str(row[c_ref]), cell(c_title), cell(c_country), cell(c_best)))
    return out


def build_channel_list(books: list[Path], out_dir: Path, study: dict) -> Path:
    """Merge, de-duplicate, and screen candidates BEFORE the donor scan.

    Geography is screened here rather than in the report because the scan is the
    stage that costs quota: a channel scout already tells us is British is ~4
    wasted units and several wasted seconds. Channels with no country in their
    metadata are kept — donor_trail resolves those from content markers.
    """
    geo = study.get("geo_prefilter") or {}
    target = (geo.get("target") or "").upper()
    keep_unknown = geo.get("keep_unknown", True)

    brand_channel = brand_channel_re(study)
    exclude_channel = exclude_channel_re(study)
    noise_channel = noise_channel_re(study)
    seen, keep, dropped, noise = set(), [], [], []
    brand = off_geo = 0
    by_country: dict[str, int] = {}
    for book in books:
        for ref, title, country, best in channels_from_workbook(book):
            if ref in seen:
                continue
            seen.add(ref)
            if brand_channel.search(title) or brand_channel.search(ref):
                brand += 1
                continue
            if noise_channel is not None and (noise_channel.search(title)
                                              or noise_channel.search(best)):
                # Matched the search term by coincidence, not by sponsorship.
                noise.append(f"{title or ref} :: {best[:70]}")
                continue
            if exclude_channel is not None and exclude_channel.search(title):
                # Recorded, not dropped. Excluding before the scan makes a
                # recall-first pass impossible and hides the screen's own
                # mistakes; the workbook flags these instead, so they can be
                # filtered by someone who can see what is being filtered.
                dropped.append(title)
            cc = (country or "").upper()
            by_country[cc or "?"] = by_country.get(cc or "?", 0) + 1
            if target:
                if not cc:
                    if not keep_unknown:
                        off_geo += 1
                        continue
                elif cc != target:
                    off_geo += 1
                    continue
            keep.append(ref)

    dist = ", ".join(f"{k}:{v}" for k, v in sorted(by_country.items(), key=lambda x: -x[1])[:8])
    path = out_dir / "candidates.txt"
    path.write_text(
        "# merged unique channels from this study's scout workbooks\n"
        f"# {len(keep)} candidates | {brand} brand-owned dropped | "
        f"{len(dropped)} supply-side FLAGGED (still scanned) | "
        f"{off_geo} dropped outside {target or 'any'}"
        f"{' (unknown-country kept)' if target and keep_unknown else ''} | "
        f"{len(noise)} topic-homonym DROPPED\n"
        f"# country distribution of pool: {dist}\n"
        + ("".join(f"# supply-side flagged: {t}\n" for t in sorted(dropped)) if dropped else "")
        + ("".join(f"# homonym dropped: {t}\n" for t in sorted(noise)) if noise else "")
        + "\n".join(keep) + "\n",
        encoding="utf-8",
    )
    print(f"\npool: {len(seen)} unique | {brand} brand-owned dropped | "
          f"{len(dropped)} supply-side FLAGGED (still scanned) | "
          f"{off_geo} outside {target or 'any'} dropped | "
          f"{len(noise)} homonym dropped | {len(keep)} to scan", file=sys.stderr)
    print(f"  countries: {dist}", file=sys.stderr)
    return path


def _int(value) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def priced_section(rows: list[dict], study: dict, limit: int = 12) -> str:
    """The decision table: what to buy, on which placement, at what price.

    Everything else in the report is evidence. This is the only part that says
    what to do, so it is the only part that needs the brief's economics, and it
    is omitted with a reason rather than guessed at when they are missing.
    """
    brand = study.get("brief") or (study.get("out_dir", "") + "/").split("/")[1]
    try:
        econ = _brief.load_economics(brand)
    except _brief.BriefError as exc:
        return ("> **Pricing omitted.** {}\n>\n> Everything below is evidence about who gets "
                "sponsored, not a recommendation about who to buy.".format(exc))

    gaps = sorted(set(_brief.missing(econ, "longform")) | set(_brief.missing(econ, "shorts")))
    if gaps:
        return ("> **Pricing omitted.** `{}` has no value yet for: {}.\n>\n"
                "> Fill the Lane economics table and its `bellwether:economics` block, re-run, and "
                "this section becomes a priced slate. Everything below is evidence about who gets "
                "sponsored, not a recommendation about who to buy."
                .format(econ["_brief"], ", ".join("`{}`".format(g) for g in gaps)))

    out = ["| # | Creator | Buy | Median views | Example placement | CPA med / opt | Max rate | Action |",
           "|---:|---|---|---:|---|---|---:|---|"]
    fallback_used = False
    for i, r in enumerate(rows[:limit], 1):
        # Price the placement this creator actually carries sponsors on.
        name = "longform" if _int(r.get("donor_in_longform")) >= _int(r.get("donor_in_shorts")) else "shorts"
        key = "median_longform_views" if name == "longform" else "median_shorts_views"
        views = _int(r.get(key))
        if not views:                       # pre-2026-09-24 scans have one median only
            views = _int(r.get("median_views"))
            fallback_used = fallback_used or bool(views)

        flags = []
        if _int(r.get("hit_count")) and not _int(r.get("disclosed_hits")):
            flags.append("no disclosure marker on any brand mention")
        if (r.get("geo_verdict") or "?").startswith("?"):
            flags.append("geography unresolved")

        p = _brief.price(econ, name, views=views,
                         scanned=_int(r.get("scanned_depth")), flags=flags)
        cpa = ("{} / {}".format(_brief._money(p["cpa_median"]), _brief._money(p["cpa_optimistic"]))
               if p["cpa_median"] is not None else "n/a, ranking buy")
        example = ("[{}]({})".format((r.get("example_title") or "example")[:38], r["example_url"])
                   if r.get("example_url") else "—")
        out.append("| {} | [{}]({}) | {} | {} | {} | {} | {} | {} |".format(
            i, r["handle"], r["url"], "long-form" if name == "longform" else "Shorts",
            "{:,}".format(views) if views else "—", example, cpa,
            _brief._money(p["max_rate"]) if p["max_rate"] else "—", p["action"]))

    notes = [
        "Priced against `{}`. Rates are the brief's typical rate; **Max rate** is the most payable "
        "while the median case still clears the CPA ceiling, capped by the CPM cap.".format(econ["_brief"]),
        "Shorts rows carry no CPA on purpose: a ranking buy has no measured sign-up rate, and a "
        "borrowed one would be invented.",
    ]
    if fallback_used:
        notes.append("Some rows fall back to the all-uploads median because they were scanned before "
                     "the long-form/Shorts split was recorded. Re-scan to price those properly.")
    return "\n".join(out) + "\n\n" + "\n".join("*{}*".format(n) for n in notes)


def report(scan_csv: Path, study: dict, out_path: Path, books: list[Path]) -> None:
    rows = list(csv.DictReader(scan_csv.open(encoding="utf-8")))
    today = datetime.now(timezone.utc).date().isoformat()
    latest = max((r["scan_date"] for r in rows), default=today)
    rows = [r for r in rows if r["scan_date"] == latest]
    # One scorer for both outputs — see build_workbook.score_and_tier.
    tiers = score_and_tier(rows, study, latest)
    slate_n = int(study.get('slate_size', 12))
    target, min_subs = tiers["target"], tiers["min_subs"]
    eligible, other = tiers["all"], tiers["excluded"]
    referral_noise, discrete, standing = tiers["noise"], tiers["tier_a"], tiers["tier_b"]

    donor = study.get("donor_label", "the donor brand")
    priced = priced_section(tiers["tier_a"] + tiers["tier_b"], study, slate_n)

    def table(rs, limit=40, score=True):
        # The date column names the donor brand on purpose: "Last seen" reads as
        # "last time they posted anything", which is not what it measures.
        # (header, alignment) pairs, so the rule row can never drift out of sync
        # with the header — it did once, when Months since was inserted.
        cols = [("Creator", "---"), ("Subs", "---:"), ("Donor hits", "---:"),
                ("Long-form", "---:"), ("Shorts", "---:"), ("Shorts share", "---:")]
        if score:
            cols.append(("Score", "---:"))
        cols += [("Pattern", "---"), (f"Last {donor} post", "---"),
                 ("Months since", "---:"), ("Secondary donors", "---")]
        head = "| " + " | ".join(c for c, _ in cols) + " |"
        rule = "|" + "|".join(a for _, a in cols) + "|"
        out = [head, rule]
        for r in rs[:limit]:
            share = r.get("shorts_share") or "0"
            cells = (f"| [{r['handle']}]({r['url']}) | {r['_subs']:,} | "
                     f"{r['_hits']}/{r['scanned_depth']} | {r['_long']} | {r['_short']} | "
                     f"{float(share):.0%} | ")
            if score:
                cells += f"{r['_score']} | "
            since = months_since(r.get("last_seen", ""), latest)
            cells += (f"{r['pattern']} | {r['last_seen'] or '—'} | "
                      f"{since if since is not None else '—'} | "
                      f"{r['secondary_donors'] or '—'} |")
            out.append(cells)
        return "\n".join(out)
    md = f"""# {study.get('name', 'Donor-trail study')} — API re-run

**Method:** `docs/predictive-discovery-spec.md` §3 · **Run:** {today}
**Discovery:** youtube-scout, {len(books)} topic searches · **Donor scan:** `donor_trail.py` at depth {study.get('depth', 90)}
**Channels scanned:** {len(rows)} · **Geo-eligible ({target}):** {len(eligible)} · **Subscriber floor:** {min_subs:,}

> Counts are placements of {donor} found in the **full** description of each scanned
> upload, read through the YouTube Data API. They are a floor: a verbal-only sponsorship
> with no description link is invisible to the scan. Geography is resolved from channel
> metadata where present, otherwise from content markers.

**Ranking.** Score = long-form donor placements × a recency weight (same year 1.0,
one year 0.7, two 0.45, older 0.25). Long-form carries the score because a 60–90s
integration inside a vlog is the conversion placement; **Shorts** are reported
separately because they are bought against a video-pack/SEO goal, not a conversion goal.

## Recommended slate

Top {slate_n} eligible creators, priced. This is the decision table; the tiers below are the evidence.

{priced}

## Tier A — {target}, discrete rebookings (2+)

The core signal: {donor} chose to buy these creators again, on separate dates.

{table(discrete)}

## Tier B — {target}, standing affiliate link

{donor} sits in most or all descriptions. A continuously monetised link and an audience
trained to use the description box — a real transacting signal, but not a count of
rebooking decisions. Never report these counts as sponsorship counts.

{table(standing)}

## Below the subscriber floor — probable referral codes, not bookings

{len(referral_noise)} channels under {min_subs:,} subscribers carried a {donor} mention.
Consumer-subscription brands issue a referral code to **every customer**, so at this size a
description match is far more likely to be a viewer sharing their own link than a paid
placement. Listed for audit, not for consideration.

{table(referral_noise, limit=25, score=False)}

## Excluded — outside {target}

{table(other, limit=60, score=False)}

---

*Regenerate: `python3 scripts/run_study.py --study {study.get('_path', '<config>')}`*
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nreport: {out_path}", file=sys.stderr)
    print(f"  tier A (discrete, {target}): {len(discrete)}", file=sys.stderr)
    print(f"  tier B (standing, {target}): {len(standing)}", file=sys.stderr)
    print(f"  excluded (non-{target}):     {len(other)}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run an end-to-end donor-trail study.")
    ap.add_argument("--study", type=Path, required=True, help="Study config JSON")
    ap.add_argument("--refresh", action="store_true", help="Re-run scout even if workbooks are cached")
    ap.add_argument("--skip-scout", action="store_true", help="Reuse cached workbooks only")
    ap.add_argument("--rescan", action="store_true",
                    help="Re-scan channels already recorded today (needed after a scan-schema change)")
    args = ap.parse_args()

    study = json.loads(args.study.read_text(encoding="utf-8"))
    study["_path"] = str(args.study)
    out_dir = ROOT / study.get("out_dir", "outputs/homeaglow/study")
    out_dir.mkdir(parents=True, exist_ok=True)

    topics = study.get("topics", [])
    if not topics:
        sys.exit("run_study: config has no topics")
    est = len(topics) * 100 * max(1, study.get("scout", {}).get("max", 100) // 50)
    print(f"study: {study.get('name')} | {len(topics)} topics | scout ~{est} quota units",
          file=sys.stderr)

    books = []
    for topic in topics:
        if args.skip_scout:
            book = out_dir / f"scout-{slug(topic)}.xlsx"
            if book.is_file():
                books.append(book)
            continue
        books.append(scout_topic(topic, study.get("scout", {}), out_dir, args.refresh))

    if not books:
        sys.exit("run_study: no scout workbooks. Drop --skip-scout for the first run.")

    candidates = build_channel_list(books, out_dir, study)
    scan_csv = ROOT / study.get("scan_csv", "data/donor-scans-api.csv")

    cmd = [sys.executable, DONOR_TRAIL,
           "--channels", candidates,
           "--donors", ROOT / study["donors"],
           "--depth", str(study.get("depth", 90)),
           "--min-count", str(study.get("min_count", 1)),
           "--out", scan_csv]
    if args.rescan:
        cmd.append("--rescan")
    run(cmd, "donor scan")

    report(scan_csv, study, out_dir / "report.md", books)

    book = out_dir / f"donor-trail-{datetime.now(timezone.utc).date().isoformat()}.xlsx"
    try:
        build_workbook(scan_csv, study, book)
        print(f"workbook: {book}", file=sys.stderr)
    except SystemExit as exc:            # a missing openpyxl must not lose the scan
        print(f"workbook skipped: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
