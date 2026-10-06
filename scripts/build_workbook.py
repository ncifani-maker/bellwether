#!/usr/bin/env python3
"""
build_workbook.py — donor-trail results as an NAC Worldwide workbook.

Reads a donor scan CSV and writes a multi-sheet .xlsx in NAC's house style,
taken from homeaglow-youtube-creator-plan.xlsx and the August scorecard:
Arial throughout, navy 1F3864 titles, light-blue D9E2F3 header band with navy
bold text, grey subtitle line, frozen panes below the header, auto-filter on.

One deliberate departure from the creator plan: there, every data cell is blue
because the legend reads "blue = inputs you can change". These sheets are
derived output, not a worksheet to edit, so data is black and blue is kept for
links only. Anything you are meant to overwrite stays blue.

Sheets:
  Tier A          in-geo, discrete rebookings (2+), ranked by score
  Tier B          in-geo, standing or mixed affiliate-link patterns
  All Candidates  every scanned channel above the subscriber floor
  Referral Noise  below the floor — probable customer referral codes (audit)
  Excluded        outside the geography target
  Method          how to read the numbers, and what they do not mean

This module also owns `score_and_tier`, which run_study.py imports for the
markdown report, so the spreadsheet and the report cannot disagree.

Usage:
  python3 scripts/build_workbook.py --study briefs/studies/homeaglow-hellofresh.json
  python3 scripts/build_workbook.py --scan data/donor-scans-api.csv --out book.xlsx
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- NAC house style -------------------------------------------------------
FONT = "Arial"
NAVY = "FF1F3864"        # titles, header text
HEADER_BG = "FFD9E2F3"   # header band
GREY = "FF595959"        # subtitle / caveat text
INPUT_BLUE = "FF0000FF"  # reserved: cells meant to be edited, and links
BAND = "FFF2F5FB"        # subtle zebra for readability on long tables

TITLE_SIZE, SUB_SIZE, HEAD_SIZE, BODY_SIZE = 14, 9, 10, 10

# "{donor}" is substituted with the study's donor label. The date column used to
# read "Last Seen", which a client reads as "last time they posted anything" —
# it is in fact the publish date of their most recent upload that mentions the
# donor. Naming the brand removes the ambiguity, and Months Since saves the
# reader doing date arithmetic to spot a lapsed relationship.
COLUMN_TEMPLATE = [
    ("Creator", 24.0, None),
    ("Handle", 22.0, None),
    ("Channel URL", 30.0, None),
    ("Subscribers", 12.0, "#,##0"),
    ("Score", 9.0, "0.00"),
    ("Donor Hits", 11.0, "#,##0"),
    ("Disclosed", 11.0, "#,##0"),
    ("Sponsor Load", 12.0, "0%"),
    ("Long-form", 11.0, "#,##0"),
    ("Shorts", 9.0, "#,##0"),
    ("Shorts Share", 12.0, "0%"),
    ("Pattern", 11.0, None),
    ("Last {donor} Post", 20.0, None),
    ("Months Since", 12.0, "#,##0"),
    ("Window d", 10.0, "#,##0"),
    ("Secondary Donors", 28.0, None),
    ("Geo", 7.0, None),
    ("Geo Basis", 28.0, None),
    ("Median Views", 13.0, "#,##0"),
    ("Scanned", 9.0, "#,##0"),
    ("Review", 34.0, None),
    ("Example Video", 34.0, None),
    ("Example Video Title", 46.0, None),
    ("Sample Placements", 60.0, None),
]


def columns_for(donor: str) -> list[tuple]:
    return [(h.format(donor=donor), w, f) for h, w, f in COLUMN_TEMPLATE]


def months_since(last_seen: str, ref: str) -> int | None:
    """Whole months from the last donor placement to the scan date."""
    try:
        ly, lm = int(last_seen[:4]), int(last_seen[5:7])
        ry, rm = int(ref[:4]), int(ref[5:7])
    except (ValueError, IndexError):
        return None
    return max((ry - ly) * 12 + (rm - lm), 0)


def _xl():
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        sys.exit("build_workbook: openpyxl is not installed. "
                 "Run: python3 -m pip install --user openpyxl")
    return Workbook, Font, PatternFill, Alignment, get_column_letter


# ------------------------------------------------------------ scoring / tiers

def recency_weight(last_seen: str, cur_year: int) -> float:
    """A lapsed donor relationship is evidence about the past, not the present."""
    year = (last_seen or "")[:4]
    if not year.isdigit():
        return 0.3
    return {0: 1.0, 1: 0.7, 2: 0.45}.get(cur_year - int(year), 0.25)


def score_and_tier(rows: list[dict], study: dict, today: str) -> dict:
    """Annotate rows and split into tiers. Single source of truth for both outputs."""
    target = (study.get("geo_target") or "US").upper()
    min_subs = int(study.get("min_subs", 10000))
    cur_year = int(today[:4])

    for r in rows:
        r["_subs"] = int(r.get("subs") or 0)
        r["_hits"] = int(r.get("hit_count") or 0)
        r["_long"] = int(r.get("donor_in_longform") or 0)
        r["_short"] = int(r.get("donor_in_shorts") or 0)
        r["_rw"] = recency_weight(r.get("last_seen", ""), cur_year)
        # Long-form and Shorts count EQUALLY. The original rule scored long-form
        # only, on the HelloFresh finding that the brand bought long-form 986 to
        # 27. That does not generalise: Angi's creator spend is 79% Shorts, and
        # 27 of its 31 disclosed creators are Shorts-only.
        #
        # The old line was `(_long or _hits) * _rw`, whose `or` fallback made the
        # score NON-MONOTONIC -- 0 long + 5 shorts scored 5.0 while 1 long + 4
        # shorts scored 1.0, penalising a creator for having a long-form
        # placement. Summing the two formats removes that: adding a placement of
        # either kind can now only raise a score. The `or _hits` tail remains
        # solely for pre-v0.3 rows scanned before the format split existed, where
        # both format counts are zero but hits are not.
        r["_score"] = round(((r["_long"] + r["_short"]) or r["_hits"]) * r["_rw"], 2)

    def in_target(r):
        return (r.get("geo_verdict") or "").upper().startswith(target)

    in_geo = [r for r in rows if in_target(r)]
    out_geo = [r for r in rows if not in_target(r)]
    noise = [r for r in in_geo if r["_subs"] < min_subs]
    keep = [r for r in in_geo if r["_subs"] >= min_subs]
    rank = lambda rs: sorted(rs, key=lambda r: -r["_score"])

    # Tier A used to be "discrete pattern, 2+ hits". Nicole hand-reviewed 16 such
    # rows on Sept 24: 4 were real placements, 12 were not -- 25% precision. On
    # the same 16, disclosed_hits > 0 scored 80% precision at 100% recall, and
    # every row she marked good had a disclosed hit. So Tier A is now defined by
    # confirmed disclosure. A brand mention without one is a candidate, not a
    # finding, and moves to its own sheet rather than being deleted.
    confirmed = [r for r in keep if int(r.get("disclosed_hits") or 0) > 0]
    mentions = [r for r in keep if r["_hits"] > 0 and not int(r.get("disclosed_hits") or 0)]
    # Sponsor Load >= 50% sorts to the bottom rather than out. On the Sept 24
    # review the only false positive sat at 91% load while all four confirmed
    # creators sat between 9% and 20% -- a creator who is always sponsored will
    # carry a disclosure marker on a video that merely mentions the brand, so
    # their disclosure is weak evidence. Sixteen labels is a thin basis for a
    # hard cut, so it demotes and never deletes.
    HEAVY = 0.5
    rank_conf = lambda rs: sorted(
        rs, key=lambda r: (float(r.get("sponsor_load") or 0) >= HEAVY,
                           -int(r.get("disclosed_hits") or 0),
                           float(r.get("sponsor_load") or 0), -r["_score"]))
    return {
        "target": target, "min_subs": min_subs,
        "tier_a": rank_conf(confirmed),
        "tier_b": rank([r for r in keep if r.get("pattern") in ("standing", "mixed")]),
        "mentions": rank(mentions),
        "all": rank(keep),
        "noise": rank(noise),
        "excluded": rank(out_geo),
    }


def dedupe(rows: list[dict]) -> list[dict]:
    """One row per channel.

    The same channel legitimately arrives under different source_refs — a URL
    from a scout workbook and an @handle from a curated list both resolve to one
    channel_id — so appending a second candidate list to the same scan file
    would otherwise list a creator twice. Keep the deepest scan, then the one
    with more evidence.
    """
    best: dict[str, dict] = {}
    for r in rows:
        key = r.get("channel_id") or r.get("handle", "")
        cur = best.get(key)
        if cur is None:
            best[key] = r
            continue
        rank = lambda x: (int(x.get("scanned_depth") or 0), int(x.get("hit_count") or 0))
        if rank(r) > rank(cur):
            best[key] = r
    return list(best.values())


def read_scan(path: Path) -> tuple[list[dict], str]:
    if not path.is_file():
        sys.exit(f"build_workbook: no scan file at {path}. Run the study first.")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        sys.exit(f"build_workbook: {path} has no rows.")
    latest = max(r.get("scan_date", "") for r in rows)
    today = [r for r in rows if r.get("scan_date") == latest]
    deduped = dedupe(today)
    if len(deduped) < len(today):
        print(f"build_workbook: merged {len(today) - len(deduped)} duplicate channel rows "
              f"(same channel reached via different references)", file=sys.stderr)
    return deduped, latest


# ---------------------------------------------------------------- the workbook

def load_feedback(study: dict) -> dict:
    """Hand review, keyed by handle, merged back on every rebuild.

    Nicole reviewed Tier A in the spreadsheet itself. Rebuilding the workbook
    would have silently overwritten that column, so the review lives in its own
    CSV and is re-merged here -- a verdict, once given, survives every rerun.
    """
    path = study.get("feedback_csv")
    if not path:
        return {}
    f = ROOT / path
    if not f.is_file():
        print(f"build_workbook: feedback file {f} not found", file=sys.stderr)
        return {}
    out = {}
    for row in csv.DictReader(f.open(encoding="utf-8")):
        h = (row.get("handle") or "").strip().lower()
        if h:
            verdict = (row.get("verdict") or "").strip()
            note = (row.get("note") or "").strip()
            out[h] = f"{verdict}: {note}" if verdict and note else (verdict or note)
    print(f"build_workbook: merged {len(out)} hand-review verdicts", file=sys.stderr)
    return out


def row_values(r: dict, ref_date: str = "") -> list:
    share = r.get("shorts_share")
    last = r.get("last_seen", "")
    return [
        r.get("title") or r.get("handle", ""),
        r.get("handle", ""),
        r.get("url", ""),
        r["_subs"], r["_score"], r["_hits"],
        int(r.get("disclosed_hits") or 0),
        float(r["sponsor_load"]) if r.get("sponsor_load") not in (None, "") else None,
        r["_long"], r["_short"],
        float(share) if share not in (None, "") else None,
        r.get("pattern", ""), last,
        months_since(last, ref_date) if last and ref_date else None,
        int(r.get("window_days") or 0),
        r.get("secondary_donors", ""),
        r.get("geo_verdict", ""), r.get("geo_basis", ""),
        int(r.get("median_views") or 0),
        int(r.get("scanned_depth") or 0),
        r.get("_review", ""),
        r.get("example_url", ""),
        r.get("example_title", ""),
        r.get("hit_titles", ""),
    ]


def add_sheet(wb, name: str, title: str, subtitle: str, rows: list[dict],
              donor: str = "Donor", ref_date: str = ""):
    Workbook, Font, PatternFill, Alignment, col_letter = _xl()
    ws = wb.create_sheet(name)
    columns = columns_for(donor)

    ws.cell(row=1, column=1, value=title).font = Font(
        name=FONT, size=TITLE_SIZE, bold=True, color=NAVY)
    ws.cell(row=2, column=1, value=subtitle).font = Font(
        name=FONT, size=SUB_SIZE, color=GREY)

    head_font = Font(name=FONT, size=HEAD_SIZE, bold=True, color=NAVY)
    head_fill = PatternFill("solid", start_color=HEADER_BG, end_color=HEADER_BG)
    wrap = Alignment(vertical="center", wrap_text=True)
    for i, (head, width, _) in enumerate(columns, start=1):
        c = ws.cell(row=3, column=i, value=head)
        c.font, c.fill, c.alignment = head_font, head_fill, wrap
        ws.column_dimensions[col_letter(i)].width = width

    body = Font(name=FONT, size=BODY_SIZE)
    link = Font(name=FONT, size=BODY_SIZE, color=INPUT_BLUE, underline="single")
    band = PatternFill("solid", start_color=BAND, end_color=BAND)
    for n, r in enumerate(rows):
        excel_row = 4 + n
        for i, (value, (head, _, fmt)) in enumerate(zip(row_values(r, ref_date), columns), start=1):
            c = ws.cell(row=excel_row, column=i, value=value)
            c.font = body
            if fmt:
                c.number_format = fmt
            if head in ("Channel URL", "Example Video") and isinstance(value, str) \
                    and value.startswith("http"):
                c.hyperlink, c.font = value, link
            if n % 2:
                c.fill = band

    ws.freeze_panes = "A4"
    last = col_letter(len(columns))
    ws.auto_filter.ref = f"A3:{last}{max(3 + len(rows), 4)}"
    ws.row_dimensions[3].height = 28
    return ws


def add_method_sheet(wb, study: dict, t: dict, scan_date: str, total: int):
    Workbook, Font, PatternFill, Alignment, _ = _xl()
    ws = wb.create_sheet("Method")
    donor = study.get("donor_label", "the donor brand")

    ws.cell(row=1, column=1, value="Method & caveats").font = Font(
        name=FONT, size=TITLE_SIZE, bold=True, color=NAVY)
    ws.cell(row=2, column=1,
            value="Read this before taking any number to a rate negotiation.").font = Font(
        name=FONT, size=SUB_SIZE, color=GREY)

    pairs = [
        ("RUN", ""),
        ("Study", study.get("name", "")),
        ("Donor brand", donor),
        ("Scan date", scan_date),
        ("Built", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        ("Spec", "docs/predictive-discovery-spec.md §3"),
        ("Scan depth", int(study.get("depth", 90))),
        ("Geography target", t["target"]),
        ("Subscriber floor", t["min_subs"]),
        ("COUNTS", ""),
        ("Channels with donor evidence", total),
        ("Tier A — confirmed by disclosure", len(t["tier_a"])),
        ("Mentions only — no disclosure", len(t["mentions"])),
        ("Tier B — standing / mixed link", len(t["tier_b"])),
        ("Above floor, in target geo", len(t["all"])),
        ("Below floor — probable referral codes", len(t["noise"])),
        ("Excluded — outside target geo", len(t["excluded"])),
        ("HOW TO READ IT", ""),
        ("Donor Hits", f"Uploads out of those scanned whose full description mentioned {donor}."),
        ("Long-form vs Shorts", "Long-form is the 60–90s integration inside a vlog — the conversion "
                                "placement. Shorts are bought for video-pack / SEO ranking. Only "
                                "long-form is scored, because only long-form is the conversion buy."),
        ("Review", "A human verdict on this row, merged from the hand-review CSV rather than typed "
                   "into the sheet -- typed here it would be destroyed by the next rebuild. Add "
                   "rows to that CSV and they reappear on every run."),
        ("Example Video", "One placement you can open and check. A DISCLOSED hit is preferred over "
                          "an undisclosed one, and the most recent within each group, so the link "
                          "shown is the strongest evidence on that row. If a row's example turns "
                          "out to be a contractor citing the platform rather than a paid "
                          "placement, that row's Disclosed count should be zero -- check it."),
        ("Disclosed", "Of the videos that mention the brand, how many ALSO carry a disclosure "
                      "marker (#ad, #sponsored, a brand partner tag, 'paid partnership'). This is "
                      "the column that separates a paid placement from a mention. A contractor "
                      "writing 'find us on Angi' does not disclose; a creator the brand paid "
                      "usually does. 'Not sponsored' is excluded before matching."),
        ("Disclosure is a proxy", "The FTC does not mandate any hashtag, and for video it directs "
                                  "disclosure INTO the video, visual and audible, where no text "
                                  "scan reaches. A verbal-only disclosure is invisible here, so "
                                  "Disclosed is a floor and a zero is not proof of an unpaid post."),
        ("Sponsor Load", "Share of ALL scanned uploads carrying any disclosure marker, whatever the "
                         "brand. How heavily sponsored this creator is in general — useful for "
                         "reading whether one brand placement was a real decision or routine."),
        ("Score", "Long-form placements × recency weight: same year 1.0, one year 0.7, "
                  "two years 0.45, older 0.25."),
        (f"Last {donor} Post", f"Publish date of that creator's most recent upload whose "
                               f"description mentioned {donor} — NOT their most recent upload. "
                               "Bounded by the scan depth, so on a prolific channel it reflects "
                               "the scanned window only (see Window d). On a standing-link creator "
                               "it tracks their upload cadence rather than a booking decision."),
        ("Months Since", "Whole months from that date to the scan date. The Score recency weight "
                         "is built on the same fact."),
        ("Pattern", "discrete = separate bookings on separate dates, the real signal. "
                    "standing = a permanent affiliate block in nearly every description, which is "
                    "continuous monetisation, NOT a count of rebooking decisions."),
        ("WHAT IT DOES NOT MEAN", ""),
        ("Referral codes", f"{donor} issues a referral code to every customer, so a description "
                           "match cannot by itself prove a paid booking. The subscriber floor "
                           "mitigates this; it does not solve it. See the Referral Noise sheet."),
        ("Counts are a floor", "Verbal-only sponsorships with no description link are invisible "
                               "to the scan, so a low count is not proof of absence."),
        ("Transfer is an argument", f"{donor} rebooking a creator proves their audience buys "
                                    f"{donor}. It argues for, but does not prove, that the same "
                                    "audience books home cleaning."),
        ("Not yet validated", "The whole thesis is unproven until the bake-off readout. "
                              "These numbers make the signal measurable, not true."),
    ]
    section_font = Font(name=FONT, size=HEAD_SIZE, bold=True, color="FFFFFFFF")
    section_fill = PatternFill("solid", start_color=NAVY, end_color=NAVY)
    key_font = Font(name=FONT, size=BODY_SIZE, bold=True, color=NAVY)
    val_font = Font(name=FONT, size=BODY_SIZE)

    for i, (k, v) in enumerate(pairs, start=4):
        a, b = ws.cell(row=i, column=1, value=k), ws.cell(row=i, column=2, value=v)
        if v == "":
            a.font, a.fill = section_font, section_fill
            b.fill = section_fill
        else:
            a.font, b.font = key_font, val_font
            b.alignment = Alignment(wrap_text=True, vertical="top")
            if isinstance(v, int):
                b.number_format = "#,##0"
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 96
    return ws


def add_first_pass_sheet(wb, study: dict, current: list[dict], donor: str, scan_date: str):
    """Channels a PRIOR scan found that the current one does not.

    Nothing should vanish from a deliverable without a reason the reader can
    check. A channel can leave the set two ways: the supply-side screen drops
    it before scanning, or a corrected pattern no longer matches it. Both are
    intentional, and both are recorded here rather than silently disappearing.

    These rows carry the PRIOR scan's numbers, computed under the old patterns,
    so they are audit material and must not be read as findings.
    """
    prior_path = study.get("prior_scan_csv")
    if not prior_path:
        return None
    path = ROOT / prior_path
    if not path.is_file():
        print(f"build_workbook: prior scan {path} not found, skipping audit sheet", file=sys.stderr)
        return None

    prior = list(csv.DictReader(path.open(encoding="utf-8")))
    if not prior:
        return None
    latest_prior = max(r.get("scan_date", "") for r in prior)
    prior = dedupe([r for r in prior if r.get("scan_date") == latest_prior])

    have = {r.get("channel_id") or r.get("handle", "") for r in current}
    gone = [r for r in prior if (r.get("channel_id") or r.get("handle", "")) not in have]
    if not gone:
        return None

    screen = study.get("exclude_channel_pattern")
    screen_re = re.compile(screen, re.I) if screen else None
    for r in gone:
        r["_subs"] = int(r.get("subs") or 0)
        r["_hits"] = int(r.get("hit_count") or 0)
        r["_long"] = int(r.get("donor_in_longform") or 0)
        r["_short"] = int(r.get("donor_in_shorts") or 0)
        r["_score"] = 0.0
        r["_why"] = ("dropped by the supply-side screen"
                     if screen_re and screen_re.search(r.get("title", ""))
                     else "not re-detected under the corrected patterns")
    gone.sort(key=lambda r: -r["_subs"])

    ws = add_sheet(
        wb, "First Pass Only",
        f"First pass only — in the {latest_prior} scan, not in the current one",
        f"Every channel the earlier {donor} scan found that the {scan_date} scan does not, with the "
        "reason. Their numbers are the OLD scan's, computed under the patterns that were later "
        "corrected, so treat this sheet as an audit trail and not as candidates. Nothing here "
        "carries disclosure data, because the first pass predated that column.",
        gone, donor, scan_date)

    # append the reason in the column the old rows have nothing useful in
    Workbook, Font, PatternFill, Alignment, col_letter = _xl()
    col = len(columns_for(donor)) + 1
    head = ws.cell(row=3, column=col, value="Why Not In Current")
    head.font = Font(name=FONT, size=HEAD_SIZE, bold=True, color=NAVY)
    head.fill = PatternFill("solid", start_color=HEADER_BG, end_color=HEADER_BG)
    head.alignment = Alignment(vertical="center", wrap_text=True)
    ws.column_dimensions[col_letter(col)].width = 38
    for n, r in enumerate(gone):
        c = ws.cell(row=4 + n, column=col, value=r["_why"])
        c.font = Font(name=FONT, size=BODY_SIZE)
        if n % 2:
            c.fill = PatternFill("solid", start_color=BAND, end_color=BAND)
    ws.auto_filter.ref = f"A3:{col_letter(col)}{max(3 + len(gone), 4)}"
    print(f"build_workbook: First Pass Only sheet -- {len(gone)} channels", file=sys.stderr)
    return ws


def build(scan: Path, study: dict, out_path: Path) -> Path:
    Workbook, *_ = _xl()
    rows, scan_date = read_scan(scan)
    feedback = load_feedback(study)
    for r in rows:
        r["_review"] = feedback.get((r.get("handle") or "").strip().lower(), "")
    t = score_and_tier(rows, study, scan_date)
    donor = study.get("donor_label", "donor")
    geo, floor = t["target"], t["min_subs"]

    wb = Workbook()
    wb.remove(wb.active)

    add_sheet(wb, "Tier A", f"Tier A — confirmed {donor} placements",
              f"{geo} audience, {floor:,}+ subscribers, and at least one placement carrying a "
              "disclosure marker. Sorted by Disclosed, then by Sponsor Load ascending: a low load "
              "means the brand chose them, a high load means they take everything and the "
              "disclosure may belong to a different sponsor. This is the shortlist.",
              t["tier_a"], donor, scan_date)
    add_sheet(wb, "Mentions Only", f"Mentions {donor} — no disclosure found",
              "The brand appears but no placement carries a disclosure marker. On a hand-review of "
              "16 such rows, 12 were the brand as a TOPIC rather than a sponsor: lead-gen advice, "
              "gig-work coaching, CEO interviews, a broken affiliate link. Kept because disclosure "
              "is a floor -- a verbal-only placement is invisible to the scan -- so a real "
              "placement can land here. Check the Example Video before dismissing a row.",
              t["mentions"], donor, scan_date)
    add_sheet(wb, "Tier B", f"Tier B — standing {donor} affiliate link",
              f"{donor} appears in most or all descriptions: continuous monetisation and an audience "
              "trained to use description links. A real signal, but not a count of bookings — never "
              "report these as sponsorship counts.", t["tier_b"], donor, scan_date)
    add_sheet(wb, "All Candidates", f"All candidates above the {floor:,} subscriber floor",
              f"Every {geo} channel where the scan found any {donor} evidence. "
              "Tier A and Tier B are cuts of this list.", t["all"], donor, scan_date)
    add_sheet(wb, "Referral Noise", "Below the subscriber floor — probable referral codes",
              f"{donor} gives a referral code to every customer, so under {floor:,} subscribers a "
              "description match is more likely a viewer sharing their own link than a paid booking. "
              "Listed for audit, not for consideration.", t["noise"], donor, scan_date)
    add_sheet(wb, "Excluded", f"Excluded — audience outside {geo}",
              f"{donor} runs separate national creator programmes. These carry real donor evidence "
              f"but fail the {geo} audience requirement.", t["excluded"], donor, scan_date)
    add_first_pass_sheet(wb, study, rows, donor, scan_date)
    add_method_sheet(wb, study, t, scan_date, len(rows))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Write donor-trail results as an NAC-style workbook.")
    ap.add_argument("--study", type=Path, help="Study config JSON (supplies scan path, floor, geo)")
    ap.add_argument("--scan", type=Path, help="Scan CSV (overrides the study's scan_csv)")
    ap.add_argument("--out", type=Path, help="Workbook path")
    args = ap.parse_args()

    study = json.loads(args.study.read_text(encoding="utf-8")) if args.study else {}
    scan = args.scan or (ROOT / study.get("scan_csv", "data/donor-scans-api.csv"))
    out = args.out or (ROOT / study.get("out_dir", "outputs") /
                       f"donor-trail-{datetime.now(timezone.utc).date().isoformat()}.xlsx")
    print(f"wrote {build(scan, study, out)}", file=sys.stderr)


if __name__ == "__main__":
    main()
