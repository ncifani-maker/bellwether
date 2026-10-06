#!/usr/bin/env python3
"""
donor_trail.py — Bellwether Scout, donor-trail mode.

Companion to youtube-scout (vendor/youtube-scout). Where scout.py answers
"what is performing on this topic", this answers "which creators does a
comparable brand rebook, and how often".

Method is specified in docs/predictive-discovery-spec.md sec 3. In short: enumerate a
channel's uploads via the uploads playlist, read the FULL description of every
upload, count donor-brand placements, and classify the pattern as a standing
affiliate link or discrete rebookings.

Why not scout.py: it is topic-scoped, and it truncates descriptions to 300
characters. Sponsor disclosures and promo codes routinely sit past that.

Why not the channel search page: YouTube's channel search pads results to
roughly 30 rows regardless of how many genuinely match and returns no matched
snippet, so counts taken that way are wrong in both directions.

Quota: about 4 units per channel at depth 90 (2 playlistItems + 2 videos calls).
The default 10,000 unit/day allowance covers roughly 2,500 channel scans.

Usage:
  python3 donor_trail.py --channels handles.txt --donors donors/homeaglow.json
  python3 donor_trail.py --channels @AshleyTaylorr,@rachelleea --depth 90
  python3 donor_trail.py --from-scout scout-mom-vlog-2026-09-11.xlsx --depth 60

API key resolution matches scout.py: YOUTUBE_API_KEY, then SCOUT_ENV_FILE,
then ~/.config/scout/.env, then ./.env. The key is never printed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://www.googleapis.com/youtube/v3"
DEFAULT_DEPTH = 90
STANDING_RATIO = 0.60      # >= this share of uploads -> standing link
DISCRETE_RATIO = 0.30      # <= this share -> discrete rebookings
SHORTS_MAX_SEC = 180       # YouTube Shorts ceiling (3 min since Oct 2024)

ISO_DUR = re.compile(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def duration_seconds(iso: str) -> int:
    """PT1H2M3S -> 3723. Returns 0 when absent or unparseable."""
    m = ISO_DUR.fullmatch(iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s

UK_MARKERS = re.compile(
    r"\bmum\b|\bmummy\b|£|primark|tesco|sainsbury|asda|\bnhs\b|colour|favourite"
    r"|\.co\.uk|united kingdom|london|manchester|home bargains|b&m",
    re.I,
)
US_MARKERS = re.compile(
    r"\bmom\b|\bmoms\b|\$\d|\btarget\b|costco|trader joe|walmart|thanksgiving"
    r"|\bnicu\b|texas|colorado|florida|california|\bohio\b|freshman",
    re.I,
)


# ---------------------------------------------------------------- key + http

def load_api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if key:
        return key
    candidates = []
    if os.environ.get("SCOUT_ENV_FILE"):
        candidates.append(Path(os.environ["SCOUT_ENV_FILE"]))
    candidates += [Path.home() / ".config" / "scout" / ".env", Path(".env")]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("YOUTUBE_API_KEY"):
                    _, _, val = line.partition("=")
                    val = val.strip().strip('"').strip("'")
                    if val:
                        return val
        except OSError:
            continue
    sys.exit(
        "donor_trail: no YouTube Data API key found.\n"
        "  Create one (YouTube Data API v3) in Google Cloud Console, restrict it to that API, then:\n"
        "    mkdir -p ~/.config/scout && printf 'YOUTUBE_API_KEY=YOUR_KEY\\n' > ~/.config/scout/.env\n"
        "    chmod 600 ~/.config/scout/.env\n"
        "  The same key is used by the /scout skill."
    )


class TransientError(Exception):
    """A per-channel failure the run should survive: timeout, reset, 5xx."""


class Quota:
    def __init__(self) -> None:
        self.units = 0
        self.calls = 0

    def spend(self, n: int) -> None:
        self.units += n
        self.calls += 1


# --- disclosure layer -------------------------------------------------------
# The FTC does NOT mandate a hashtag and, for video, pushes disclosure INTO the
# video (visual + audible) where no text scan can reach it. So this is a proxy,
# not a legal test, and it under-reads by design. What it buys is precision: a
# contractor writing "find us on Angi" never writes #ad, while a creator Angi
# paid usually does. Brand mention AND a disclosure marker on the SAME video is
# the high-confidence signal; brand mention alone is a candidate, not a finding.
DISCLOSURE = re.compile(
    r"#ad\b|#sponsored\b|\bsponsored\b|#paidpartnership\b|paid\s+partnership|"
    r"paid\s+promotion|#\w*partner\b|in\s+partnership\s+with|"
    r"thanks?\s+to\s+.{0,40}?\s+for\s+sponsoring",
    re.I,
)
# "not sponsored" is a real and common phrase; it must not count as one.
NOT_SPONSORED = re.compile(r"\b(?:not|non|un)[\s-]*sponsored\b", re.I)


def has_disclosure(text: str) -> bool:
    return bool(DISCLOSURE.search(NOT_SPONSORED.sub(" ", text)))


MAX_ATTEMPTS = 6

def api_get(endpoint: str, params: dict, key: str, quota: Quota, cost: int) -> dict:
    """One API call. Retries transient faults with backoff.

    Fatal (exits the run): exhausted quota, invalid key. Everything else that
    fails after MAX_ATTEMPTS raises TransientError so the caller can skip this
    one channel and keep the rest of the run.
    """
    params = dict(params)
    params["key"] = key
    url = f"{API}/{endpoint}?" + urllib.parse.urlencode(params)
    last = ""
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=45) as resp:
                quota.spend(cost)
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:400]
            low = body.lower()
            if exc.code in (403, 429) and "quota" in low:
                sys.exit(f"donor_trail: YouTube API quota exceeded. Spent {quota.units} units this run.\n"
                         "  Quota resets at midnight Pacific. Re-run to resume where you stopped.")
            if exc.code == 400 and "api key not valid" in low:
                sys.exit("donor_trail: API key not valid. Check ~/.config/scout/.env")
            if exc.code in (429, 500, 502, 503, 504):
                last = f"HTTP {exc.code}"
                time.sleep(min(2 ** attempt, 30))
                continue
            raise TransientError(f"HTTP {exc.code} on {endpoint}: {body[:160]}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = str(exc)
            time.sleep(min(2 ** attempt, 30))
            continue
        except json.JSONDecodeError as exc:
            last = f"bad JSON: {exc}"
            time.sleep(min(2 ** attempt, 30))
            continue
    raise TransientError(f"{endpoint} failed after {MAX_ATTEMPTS} attempts: {last}")


# ------------------------------------------------------------------ channels

def resolve_channel(ref: str, key: str, quota: Quota) -> dict | None:
    """Resolve @handle, channel URL, or UC... id to a channel record."""
    ref = ref.strip()
    if not ref:
        return None
    if "youtube.com" in ref:
        m = re.search(r"@([A-Za-z0-9._-]+)", ref) or re.search(r"channel/(UC[\w-]+)", ref)
        ref = ("@" + m.group(1)) if m and m.group(0).startswith("@") else (m.group(1) if m else ref)

    params = {"part": "snippet,statistics,contentDetails,brandingSettings", "maxResults": 1}
    if ref.startswith("UC") and len(ref) == 24:
        params["id"] = ref
    else:
        params["forHandle"] = ref if ref.startswith("@") else "@" + ref

    data = api_get("channels", params, key, quota, cost=1)
    items = data.get("items") or []
    if not items:
        return None
    it = items[0]
    sn = it.get("snippet") or {}
    st = it.get("statistics") or {}
    return {
        "channel_id": it.get("id", ""),
        "title": sn.get("title", ""),
        "handle": sn.get("customUrl", ref),
        "country": sn.get("country", ""),
        "description": sn.get("description", ""),
        "subs": int(st.get("subscriberCount", 0) or 0),
        "video_count": int(st.get("videoCount", 0) or 0),
        "uploads_playlist": ((it.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads", ""),
    }


def list_uploads(playlist_id: str, depth: int, key: str, quota: Quota) -> list[str]:
    ids, token = [], None
    while len(ids) < depth:
        params = {"part": "contentDetails", "playlistId": playlist_id,
                  "maxResults": min(50, depth - len(ids))}
        if token:
            params["pageToken"] = token
        data = api_get("playlistItems", params, key, quota, cost=1)
        for item in data.get("items", []):
            vid = ((item.get("contentDetails") or {}).get("videoId") or "").strip()
            if vid:
                ids.append(vid)
        token = data.get("nextPageToken")
        if not token:
            break
    return ids[:depth]


def fetch_videos(video_ids: list[str], key: str, quota: Quota) -> list[dict]:
    out = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        data = api_get("videos", {"part": "snippet,statistics,contentDetails",
                                  "id": ",".join(chunk), "maxResults": 50}, key, quota, cost=1)
        for it in data.get("items", []):
            sn = it.get("snippet") or {}
            st = it.get("statistics") or {}
            out.append({
                "id": it.get("id", ""),
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),   # FULL, not truncated
                "published": sn.get("publishedAt", ""),
                "views": int(st.get("viewCount", 0) or 0),
                "seconds": duration_seconds(((it.get("contentDetails") or {}).get("duration") or "")),
            })
    return out


# ------------------------------------------------------------------- scoring

def parse_dt(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def classify(hits: int, scanned: int) -> str:
    if scanned == 0:
        return "none"
    if hits == 0:
        return "none"
    ratio = hits / scanned
    if ratio >= STANDING_RATIO:
        return "standing"
    if ratio <= DISCRETE_RATIO:
        return "discrete"
    return "mixed"


def resolve_geo(channel: dict, videos: list[dict]) -> tuple[str, str]:
    if channel.get("country"):
        return channel["country"], "channel metadata"
    blob = " ".join(v["title"] + " " + v["description"][:1500] for v in videos[:25])
    blob += " " + channel.get("description", "")
    uk, us = len(UK_MARKERS.findall(blob)), len(US_MARKERS.findall(blob))
    if uk > us * 1.2:
        return "GB", f"content markers uk:{uk} us:{us}"
    if us > uk * 1.2:
        return "US", f"content markers us:{us} uk:{uk}"
    return "?", f"content markers inconclusive uk:{uk} us:{us}"


def scan_channel(ref: str, donors: dict, depth: int, key: str, quota: Quota) -> dict | None:
    ch = resolve_channel(ref, key, quota)
    if not ch or not ch["uploads_playlist"]:
        print(f"  ! could not resolve {ref}", file=sys.stderr)
        return None

    ids = list_uploads(ch["uploads_playlist"], depth, key, quota)
    videos = fetch_videos(ids, key, quota)
    if not videos:
        return None

    primary = donors["primary"]
    prx = re.compile(primary["pattern"], re.I)
    secondary = [(d["name"], re.compile(d["pattern"], re.I)) for d in donors.get("secondary", [])]

    # Title AND description. The scan originally read descriptions only, which
    # suited the meal-kit convention where the tracked promo code in the
    # description IS the conversion mechanism. Marketplace brands buy awareness
    # instead and tag the brand handle in the TITLE with a partnership hashtag
    # (@Angi_home ... #AngiPartner) and often no description link at all. Reading
    # descriptions only made the Sept 23 competitor run miss creator placements
    # with eight figures of views on them.
    hits, sec_found, disclosed_hits, disclosed_any = [], {}, 0, 0
    for v in videos:
        hay = v["title"] + "\n" + v["description"]
        disclosed = has_disclosure(hay)
        disclosed_any += disclosed
        if prx.search(hay):
            v["_disclosed"] = disclosed
            hits.append(v)
            disclosed_hits += disclosed
        for name, rx in secondary:
            if rx.search(hay):
                sec_found[name] = sec_found.get(name, 0) + 1

    def is_short(v):
        return 0 < v.get("seconds", 0) <= SHORTS_MAX_SEC

    def median_views(vs):
        vals = sorted(v["views"] for v in vs)
        return vals[len(vals) // 2] if vals else 0

    shorts_total = sum(1 for v in videos if is_short(v))
    hits_short = sum(1 for h in hits if is_short(h))
    hits_long = len(hits) - hits_short

    dates = [parse_dt(v["published"]) for v in videos]
    dates = sorted(d for d in dates if d)
    window_days = (dates[-1] - dates[0]).days if len(dates) > 1 else 0
    hit_dates = sorted(d for d in (parse_dt(h["published"]) for h in hits) if d)
    last_seen = hit_dates[-1].date().isoformat() if hit_dates else ""

    # One link the reader can click to check the claim. A disclosed hit is
    # preferred over an undisclosed one -- an undisclosed match may be a
    # contractor citing the platform rather than a paid placement, which is
    # exactly the case someone opening this column wants to catch -- and the
    # most recent is preferred within each group.
    def example_key(v):
        return (bool(v.get("_disclosed")), parse_dt(v["published"]) or datetime.min.replace(
            tzinfo=timezone.utc))
    best = max(hits, key=example_key) if hits else None
    example_url = f"https://www.youtube.com/watch?v={best['id']}" if best and best.get("id") else ""
    example_title = (best["title"][:90] if best else "")

    geo, geo_basis = resolve_geo(ch, videos)

    return {
        "source_ref": ref,
        "handle": ch["handle"] if ch["handle"].startswith("@") else "@" + ch["handle"].lstrip("@"),
        "channel_id": ch["channel_id"],
        "title": ch["title"],
        "subs": ch["subs"],
        "url": f"https://www.youtube.com/channel/{ch['channel_id']}",
        "donor_primary": primary["name"],
        "donor_primary_count": len(hits),
        "donor_scanned": len(videos),
        "donor_pattern": classify(len(hits), len(videos)),
        "donor_window_days": window_days,
        "donor_last_seen": last_seen,
        # of the videos that mention the brand, how many also carry a
        # disclosure marker -- the conversion from "mentions" to "paid".
        "donor_disclosed_hits": disclosed_hits,
        "donor_example_url": example_url,
        "donor_example_title": example_title,
        # share of ALL scanned uploads carrying a disclosure marker: how
        # heavily sponsored this creator is in general, brand-agnostic.
        "sponsor_load": round(disclosed_any / len(videos), 2) if videos else 0,
        "donor_secondary": ";".join(f"{k}:{v}" for k, v in sorted(sec_found.items())),
        "shorts_share": round(shorts_total / len(videos), 2) if videos else 0,
        # Homeaglow buys BOTH: long-form 60-90s integrations are the conversion
        # driver, shorts serve video-pack/SEO ranking. Kept separate because the
        # two placements are bought against different goals.
        "donor_in_longform": hits_long,
        "donor_in_shorts": hits_short,
        "geo_verdict": geo,
        "geo_basis": geo_basis,
        # Three medians, because a placement is priced against the views that
        # placement actually gets. One median over all uploads is a Shorts number
        # on a Shorts-heavy channel and a long-form number on a vlogger, so
        # pricing either buy off it is wrong in one direction or the other.
        # No extra API calls: the duration is already on every scanned video.
        "median_views": median_views(videos),
        "median_longform_views": median_views([v for v in videos if not is_short(v)]),
        "median_shorts_views": median_views([v for v in videos if is_short(v)]),
        "hit_titles": " | ".join(h["title"][:60] for h in hits[:5]),
    }


# ---------------------------------------------------------------------- main

CSV_FIELDS = ["scan_date", "source_ref", "handle", "channel_id", "title", "subs", "url",
              "donor_brand", "method", "scanned_depth", "hit_count", "pattern", "window_days",
              "last_seen", "disclosed_hits", "sponsor_load",
              "example_url", "example_title",
              "secondary_donors", "geo_verdict", "geo_basis",
              "median_views", "median_longform_views", "median_shorts_views",
              "shorts_share", "donor_in_longform", "donor_in_shorts", "hit_titles"]


def schema_matches(path: Path) -> bool:
    """True when an existing CSV's header is the one we are about to write."""
    if not path.is_file():
        return True
    try:
        with path.open(encoding="utf-8") as f:
            header = next(csv.reader(f), [])
    except OSError:
        return True
    return header == CSV_FIELDS


def rotate_if_stale(path: Path) -> Path | None:
    """Appending new columns to an old header silently corrupts every new row:
    DictWriter emits values in CSV_FIELDS order while DictReader parses against
    the file's shorter header, so fields shift. When the schema has changed,
    archive the old file and start a fresh one instead."""
    if schema_matches(path):
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = path.parent / "archive" / f"{path.stem}-{stamp}{path.suffix}"
    archive.parent.mkdir(parents=True, exist_ok=True)
    path.rename(archive)
    return archive


def already_scanned(path: Path, today: str) -> set[str]:
    """source_refs already scanned TODAY in this CSV, so a resumed run skips them.
    Scoped to today so a later re-scan of the same list refreshes rather than skips."""
    if not path.is_file():
        return set()
    try:
        with path.open(encoding="utf-8") as f:
            return {r.get("source_ref", "") for r in csv.DictReader(f)
                    if r.get("scan_date") == today and r.get("source_ref")}
    except OSError:
        return set()


def row_for_csv(r: dict, today: str) -> dict:
    return {"scan_date": today, "source_ref": r["source_ref"], "handle": r["handle"],
            "channel_id": r["channel_id"], "title": r["title"], "subs": r["subs"],
            "url": r["url"], "donor_brand": r["donor_primary"],
            "method": "api-description-read-v2", "scanned_depth": r["donor_scanned"],
            "hit_count": r["donor_primary_count"], "pattern": r["donor_pattern"],
            "window_days": r["donor_window_days"], "last_seen": r["donor_last_seen"],
            "disclosed_hits": r["donor_disclosed_hits"], "sponsor_load": r["sponsor_load"],
            "example_url": r["donor_example_url"], "example_title": r["donor_example_title"],
            "secondary_donors": r["donor_secondary"], "geo_verdict": r["geo_verdict"],
            "geo_basis": r["geo_basis"], "median_views": r["median_views"],
            "median_longform_views": r["median_longform_views"],
            "median_shorts_views": r["median_shorts_views"],
            "shorts_share": r["shorts_share"], "donor_in_longform": r["donor_in_longform"],
            "donor_in_shorts": r["donor_in_shorts"], "hit_titles": r["hit_titles"]}


DEFAULT_DONORS = {
    "primary": {"name": "HelloFresh", "pattern": r"hello\s?fresh"},
    "secondary": [
        {"name": "Instacart", "pattern": r"instacart"},
        {"name": "Thumbtack", "pattern": r"thumbtack"},
        {"name": "Care.com", "pattern": r"care\.com"},
        {"name": "TaskRabbit", "pattern": r"taskrabbit"},
        {"name": "Shipt", "pattern": r"\bshipt\b"},
        {"name": "Hungryroot", "pattern": r"hungryroot"},
        {"name": "Factor", "pattern": r"factor\s?75|\bfactor_?\b"},
        {"name": "RocketMoney", "pattern": r"rocket\s?money"},
        {"name": "BlueApron", "pattern": r"blue\s?apron"},
        {"name": "HomeChef", "pattern": r"home\s?chef"},
    ],
}


def read_channel_list(args) -> list[str]:
    refs: list[str] = []
    if args.channels:
        p = Path(args.channels)
        if p.is_file():
            refs += [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
                     if ln.strip() and not ln.strip().startswith("#")]
        else:
            refs += [c.strip() for c in args.channels.split(",") if c.strip()]
    if args.from_scout:
        try:
            from openpyxl import load_workbook
        except ImportError:
            sys.exit("donor_trail: --from-scout needs openpyxl. pip install --user openpyxl")
        wb = load_workbook(args.from_scout, read_only=True, data_only=True)
        if "Channels" not in wb.sheetnames:
            sys.exit("donor_trail: that workbook has no Channels sheet (run scout.py first).")
        ws = wb["Channels"]
        rows = ws.iter_rows(values_only=True)
        header = [str(c or "") for c in next(rows)]
        try:
            col = next(i for i, h in enumerate(header) if h.strip().lower() in ("channel url", "channel id", "channel"))
        except StopIteration:
            sys.exit("donor_trail: no Channel URL / Channel ID column in the Channels sheet.")
        for row in rows:
            if row and row[col]:
                refs.append(str(row[col]))
    seen, out = set(), []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Scan channels for donor-brand sponsorship trails.")
    ap.add_argument("--channels", help="Comma-separated handles/URLs, or a path to a file with one per line")
    ap.add_argument("--from-scout", type=Path, help="Take the channel list from a youtube-scout workbook's Channels sheet")
    ap.add_argument("--donors", type=Path, help="Donor config JSON (default: HelloFresh + household-services set)")
    ap.add_argument("--depth", type=int, default=DEFAULT_DEPTH, help=f"Uploads to scan per channel (default {DEFAULT_DEPTH})")
    ap.add_argument("--out", type=Path, default=Path("data/donor-scans.csv"), help="CSV to append scan rows to")
    ap.add_argument("--min-count", type=int, default=0, help="Only report channels with at least this many donor hits")
    ap.add_argument("--dry-run", action="store_true", help="Print results, write nothing")
    ap.add_argument("--rescan", action="store_true",
                    help="Re-scan channels already recorded today instead of skipping them")
    args = ap.parse_args()

    donors = json.loads(args.donors.read_text(encoding="utf-8")) if args.donors else DEFAULT_DONORS
    refs = read_channel_list(args)
    if not refs:
        sys.exit("donor_trail: no channels given. Use --channels or --from-scout.")

    key, quota = load_api_key(), Quota()
    today = datetime.now(timezone.utc).date().isoformat()

    if not args.dry_run:
        moved = rotate_if_stale(args.out)
        if moved:
            print(f"scan schema changed since {args.out.name} was written — "
                  f"archived it to {moved} and starting a fresh file", file=sys.stderr)

    done = set() if (args.dry_run or args.rescan) else already_scanned(args.out, today)
    todo = [r for r in refs if r not in done]
    if done:
        print(f"resuming: {len(done)} already scanned today, {len(todo)} to go", file=sys.stderr)

    est = len(todo) * (1 + 2 * ((args.depth + 49) // 50))
    print(f"scanning {len(todo)} channels at depth {args.depth} (~{est} quota units)", file=sys.stderr)

    writer = handle = None
    if not args.dry_run:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        is_new = not args.out.is_file()
        handle = args.out.open("a", newline="", encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if is_new:
            writer.writeheader()
            handle.flush()

    results, failed = [], []

    def scan_one(ref: str, idx: int, total: int) -> None:
        print(f"[{idx}/{total}] {ref}", file=sys.stderr)
        try:
            row = scan_channel(ref, donors, args.depth, key, quota)
        except TransientError as exc:
            print(f"  ! transient: {exc}", file=sys.stderr)
            failed.append(ref)
            return
        except SystemExit:
            raise
        except Exception as exc:
            print(f"  ! {ref}: {exc}", file=sys.stderr)
            return
        if not row or row["donor_primary_count"] < args.min_count:
            return
        results.append(row)
        if writer:                      # checkpoint immediately: a crash at
            writer.writerow(row_for_csv(row, today))   # channel 400 must not
            handle.flush()              # discard the first 399
    try:
        for i, ref in enumerate(todo, 1):
            scan_one(ref, i, len(todo))

        if failed:
            print(f"\nretrying {len(failed)} channels that hit network trouble", file=sys.stderr)
            time.sleep(10)
            retry, failed = failed, []
            for i, ref in enumerate(retry, 1):
                scan_one(ref, i, len(retry))
    except KeyboardInterrupt:
        print("\ninterrupted — rows scanned so far are saved; re-run to resume", file=sys.stderr)
    finally:
        if handle:
            handle.close()

    results.sort(key=lambda r: (-r["donor_primary_count"], -r["subs"]))
    print(f"\n{'handle':<28} {'hits':>7} {'pattern':<9} {'geo':<4} {'subs':>9}  secondary", file=sys.stderr)
    for r in results:
        print(f"{r['handle']:<28} {r['donor_primary_count']:>3}/{r['donor_scanned']:<3} "
              f"{r['donor_pattern']:<9} {r['geo_verdict']:<4} {r['subs']:>9,}  {r['donor_secondary']}",
              file=sys.stderr)
    print(f"\nquota spent: {quota.units} units across {quota.calls} calls", file=sys.stderr)
    if failed:
        print(f"still unreachable after retry ({len(failed)}): {', '.join(failed[:8])}"
              f"{' …' if len(failed) > 8 else ''}", file=sys.stderr)
        print("re-run the same command to pick these up", file=sys.stderr)
    if not args.dry_run:
        print(f"wrote {len(results)} rows to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
