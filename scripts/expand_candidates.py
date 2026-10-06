#!/usr/bin/env python3
"""
expand_candidates.py — two discovery routes that brand-first topic search misses.

Topic search cannot tell you its own recall: it returns whatever YouTube's
ranking surfaces for a query, with no denominator. These two routes widen the
candidate pool from outside that ranking, and both are cheap.

  from-urls     Resolve YouTube video URLs/IDs harvested OUTSIDE the API --
                Google 'site:youtube.com "#AngiPartner"' indexes far more pages
                than search.list returns -- into channels. videos.list takes 50
                ids per call at 1 unit, so 500 harvested videos cost 10 units
                against the 100 units a single search.list query costs.

  from-network  Sponsored creators cluster: the same agency rosters and the
                same collaborator circles get booked repeatedly. Given creators
                already confirmed, pull their uploads and extract the @handles
                they mention, which surfaces the circle around them.

Both write a newline-delimited candidate file in the shape build_channel_list
produces, so donor_trail.py consumes it unchanged.

Usage:
  python3 scripts/expand_candidates.py from-urls    --in harvest.txt  --out candidates-web.txt
  python3 scripts/expand_candidates.py from-network --handles a,b,c   --out candidates-net.txt \
                                                    --depth 60
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from donor_trail import (  # noqa: E402
    Quota,
    api_get,
    load_api_key,
    resolve_channel,
    list_uploads,
    fetch_videos,
)

# youtu.be/ID, /watch?v=ID, /shorts/ID, /embed/ID, or a bare 11-char id
VIDEO_ID = re.compile(
    r"(?:youtu\.be/|/watch\?(?:[^ ]*&)?v=|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})"
    r"|^([A-Za-z0-9_-]{11})$"
)
HANDLE = re.compile(r"@([A-Za-z0-9._-]{3,30})")


def read_ids(path: Path) -> list[str]:
    """Pull video ids out of anything: a pasted SERP, a list of urls, bare ids."""
    ids, seen = [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        for m in VIDEO_ID.finditer(line.strip()):
            vid = m.group(1) or m.group(2)
            if vid and vid not in seen:
                seen.add(vid)
                ids.append(vid)
    return ids


def resolve_videos(ids: list[str], key: str, quota: Quota) -> list[dict]:
    """videos.list in pages of 50 -- 1 unit per page, regardless of page size."""
    out = []
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = api_get("videos", {"part": "snippet", "id": ",".join(chunk),
                                  "maxResults": 50}, key, quota, 1)
        for it in data.get("items", []):
            sn = it.get("snippet") or {}
            out.append({
                "video_id": it.get("id", ""),
                "channel_id": sn.get("channelId", ""),
                "channel_title": sn.get("channelTitle", ""),
                "title": sn.get("title", ""),
                "published": sn.get("publishedAt", ""),
            })
        print(f"  resolved {min(i + 50, len(ids))}/{len(ids)}", file=sys.stderr)
    return out


def cmd_from_urls(args) -> None:
    key, quota = load_api_key(), Quota()
    ids = read_ids(args.infile)
    if not ids:
        sys.exit(f"expand_candidates: no YouTube video ids found in {args.infile}")
    print(f"{len(ids)} unique video ids -> {(len(ids) + 49) // 50} api calls "
          f"({(len(ids) + 49) // 50} units)", file=sys.stderr)
    vids = resolve_videos(ids, key, quota)

    channels: dict[str, dict] = {}
    for v in vids:
        cid = v["channel_id"]
        if not cid:
            continue
        rec = channels.setdefault(cid, {"title": v["channel_title"], "n": 0, "sample": v["title"]})
        rec["n"] += 1
    lines = [f"https://www.youtube.com/channel/{cid}" for cid in channels]
    header = [
        "# candidates harvested from web search, resolved via videos.list",
        f"# {len(ids)} videos -> {len(channels)} unique channels | {quota.units} quota units spent",
    ]
    for cid, rec in sorted(channels.items(), key=lambda kv: -kv[1]["n"]):
        header.append(f"# {rec['n']:>3} video(s)  {rec['title']}  — {rec['sample'][:70]}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(header + lines) + "\n", encoding="utf-8")
    print(f"\n{len(channels)} channels -> {args.out}  ({quota.units} units)", file=sys.stderr)


def cmd_from_network(args) -> None:
    key, quota = load_api_key(), Quota()
    seeds = [h.strip() for h in args.handles.split(",") if h.strip()]
    if not seeds:
        sys.exit("expand_candidates: --handles is empty")

    mentions: dict[str, int] = {}
    seed_ids = set()
    for ref in seeds:
        ch = resolve_channel(ref, key, quota)
        if not ch or not ch["uploads_playlist"]:
            print(f"  ! could not resolve {ref}", file=sys.stderr)
            continue
        seed_ids.add(ch["channel_id"])
        vids = fetch_videos(list_uploads(ch["uploads_playlist"], args.depth, key, quota), key, quota)
        found = set()
        for v in vids:
            for m in HANDLE.finditer(v["title"] + "\n" + v["description"]):
                found.add(m.group(1).lower())
        for h in found:
            mentions[h] = mentions.get(h, 0) + 1
        print(f"  {ref}: {len(vids)} uploads, {len(found)} distinct handles mentioned",
              file=sys.stderr)

    # A handle mentioned by several different seeds is a cluster member rather
    # than one creator's friend, so rank by how many seeds mention it.
    ranked = sorted(mentions.items(), key=lambda kv: -kv[1])
    keep = [(h, n) for h, n in ranked if n >= args.min_seeds]
    header = [
        "# candidates from creator-network expansion",
        f"# {len(seeds)} seeds, depth {args.depth} | {len(mentions)} handles seen | "
        f"{len(keep)} mentioned by >= {args.min_seeds} seeds | {quota.units} quota units",
        "# NOTE: brand handles and the seeds themselves are left in -- screen them in the study's",
        "#       brand_channel_pattern rather than here, so the filter stays auditable.",
    ]
    header += [f"# {n:>3} seed(s)  @{h}" for h, n in keep[:60]]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(header + [f"@{h}" for h, _ in keep]) + "\n", encoding="utf-8")
    print(f"\n{len(keep)} candidates -> {args.out}  ({quota.units} units)", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("from-urls", help="resolve web-harvested video urls/ids to channels")
    a.add_argument("--in", dest="infile", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    a.set_defaults(func=cmd_from_urls)

    b = sub.add_parser("from-network", help="expand out from confirmed creators")
    b.add_argument("--handles", required=True, help="comma-separated @handles or channel urls")
    b.add_argument("--out", type=Path, required=True)
    b.add_argument("--depth", type=int, default=60)
    b.add_argument("--min-seeds", type=int, default=2,
                   help="keep handles mentioned by at least this many seeds (default 2)")
    b.set_defaults(func=cmd_from_network)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
