#!/usr/bin/env python3
"""
build_shortlist.py — one outreach list from both studies.

The donor trail and the competitor panel answer different questions and, as it
turns out, reach entirely different creators: 132 channels and 124 channels with
ZERO overlap. Neither list is the deliverable on its own. This merges them into
a single ranked sheet a client can act on.

Evidence is NOT comparable across the two, and the sheet says so per row:

  donor      HelloFresh rebooked them. Unrelated category, shared buyer, so it
             is a TRANSFER argument -- their audience demonstrably transacts,
             which argues for but does not prove they will book cleaning.
  competitor Thumbtack / TaskRabbit / Angi / Care.com paid them, with a
             disclosure marker on the video. Same purchase as Homeaglow, so it
             is direct evidence rather than transfer -- a stronger claim per
             placement, and the reason competitor rows outrank donor rows at
             equal counts.

Priority is a recommendation, not a score, and every input to it is a visible
column so the reasoning can be argued with.

Usage:
  python3 scripts/build_shortlist.py --out outputs/homeaglow/creator-shortlist.xlsx
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_workbook import (  # noqa: E402
    FONT, NAVY, HEADER_BG, GREY, BAND, INPUT_BLUE,
    TITLE_SIZE, SUB_SIZE, HEAD_SIZE, BODY_SIZE,
    _xl, months_since, dedupe,
)

ROOT = Path(__file__).resolve().parent.parent
PANEL = ("Thumbtack", "TaskRabbit", "Angi", "Care.com", "Handy")

# Homeaglow sells house cleaning to consumers. Fit is about whether hiring
# household help is a natural on-camera moment for this creator, not about
# audience size. Ordered: the first pattern that matches wins.
# Off-thesis first, deliberately. A channel can read as "home DIY" from a single
# renovation video and still be a comedy channel; the disqualifier has to win.
OFF_THESIS_PATTERNS = [
    ("business/gig",   r"business|hustle|gig\b|entrepreneur|make money|\bleads\b|contractor|"
                       r"how to start|\$\d|passive income"),
    ("podcast/media",  r"podcast|fireside|interview with|\bceo\b|masters of scale"),
    ("comedy/prank",   r"comedy|prank|sketch|magic|\bskit\b"),
]
# Homeaglow sells house cleaning to consumers. Fit asks whether hiring household
# help is a natural on-camera moment, not how big the channel is.
FIT = [
    ("home/cleaning",  r"clean|declutter|organi[sz]|home\s?making|tidy|weekly reset|laundry"),
    ("home DIY/reno",  r"\breno|remodel|\bdiy\b|makeover|home\s?tour|backyard|garden|interior|decor"),
    ("family",         r"\bmom\b|\bmum\b|family|toddler|baby|kids|parent|household|sister"),
    ("lifestyle/vlog", r"vlog|day in|routine|lifestyle|wife|husband|couple|house|apartment|moving"),
    ("beauty",         r"beauty|makeup|skincare|glam|hair"),
]
# Hand labels from the HelloFresh longlist. A human already judged these; the
# keyword classifier must not silently overrule that work.
FIT_OVERRIDE = {
    "@santagatostudios": "comedy/prank", "@youshouldknowpodcast": "podcast/media",
    "@brutalmoose": "comedy/prank", "@mastersofscale_": "podcast/media",
    "@nazaninkavari": "beauty", "@rachelleea": "home/cleaning",
    "@staceydiazapodaca": "family", "@jamerrillstewart": "family",
    "@xomacennavlogs": "home DIY/reno", "@vikavasilek": "lifestyle/vlog",
    "@vadahzaniel": "home/cleaning", "@savway": "lifestyle/vlog",
    "@amazonappstoredevelopers": "podcast/media",
}
OFF_THESIS = {"business/gig", "comedy/prank", "podcast/media", "needs review"}


def classify_fit(handle: str, text: str) -> str:
    if handle.lower() in FIT_OVERRIDE:
        return FIT_OVERRIDE[handle.lower()]
    for label, pat in OFF_THESIS_PATTERNS:
        if re.search(pat, text, re.I):
            return label
    for label, pat in FIT:
        if re.search(pat, text, re.I):
            return label
    return "needs review"


def load(path: Path) -> list[dict]:
    if not path.is_file():
        print(f"build_shortlist: {path} missing, skipping", file=sys.stderr)
        return []
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        return []
    latest = max(r.get("scan_date", "") for r in rows)
    return dedupe([r for r in rows if r.get("scan_date") == latest]), latest


def brands(r: dict, only=None) -> dict:
    out = {}
    for p in filter(None, (r.get("secondary_donors") or "").split(";")):
        n, _, c = p.partition(":")
        if only is None or n in only:
            out[n] = int(c or 0)
    return out


def priority(row: dict) -> tuple[str, str]:
    """Returns (priority, why). Every input is a column in the sheet."""
    if row["off_thesis"]:
        return "Skip", f"{row['fit']} — wrong conversion profile whatever the evidence"
    if row["months_since"] is not None and row["months_since"] >= 24:
        return "Skip", f"lapsed {row['months_since']} months"
    if row["review"].startswith("no"):
        return "Skip", "hand review rejected this row"
    if row["sponsor_load"] is not None and row["sponsor_load"] >= 0.5:
        return "Watch", "sponsor load high — takes most offers, weak choice signal"
    if row["review"].startswith("good"):
        return "Book", "hand-verified placement"
    if row["signal"] == "donor" and row["pattern"] in ("standing", "mixed"):
        return "Watch", ("standing affiliate link, not repeat bookings — continuous monetisation, "
                         "never a count of rebooking decisions")
    if row["fit"] == "needs review":
        return "Test", "evidence holds but content fit unclassified — eyeball the example first"
    if row["signal"] == "competitor" and row["disclosed"] >= 2:
        return "Book", "2+ disclosed competitor placements — proven buyer, same purchase"
    if row["signal"] == "competitor" and row["disclosed"] == 1:
        return "Test", "one disclosed competitor placement — real but unrepeated"
    if row["signal"] == "donor" and row["hits"] >= 4:
        return "Book", "repeat donor bookings — audience transacts, transfer argument"
    if row["signal"] == "donor":
        return "Test", "donor evidence, thin — useful as a control"
    return "Watch", "evidence present but weak"


def build(out_path: Path) -> Path:
    comp, comp_date = load(ROOT / "data/competitor-scans-api.csv")
    donor, donor_date = load(ROOT / "data/donor-scans-api.csv")

    review = {}
    fb = ROOT / "data/review/tier-a-feedback-2026-09-24.csv"
    if fb.is_file():
        for r in csv.DictReader(fb.open(encoding="utf-8")):
            review[r["handle"].strip().lower()] = f"{r['verdict']}: {r['note']}"

    rows = []
    for src, data, ref_date in (("competitor", comp, comp_date), ("donor", donor, donor_date)):
        for r in data:
            subs = int(r.get("subs") or 0)
            hits = int(r.get("hit_count") or 0)
            disclosed = int(r.get("disclosed_hits") or 0)
            if subs < 10000 or not (r.get("geo_verdict") or "").upper().startswith("US"):
                continue
            # competitor rows need a disclosed placement (80% precise on the
            # hand review, vs 25% for the raw hit rule); donor rows predate the
            # disclosure column entirely, so they qualify on rebooking instead.
            if src == "competitor" and disclosed < 1:
                continue
            if src == "donor" and hits < 2:
                continue
            b = brands(r, PANEL if src == "competitor" else None)
            text = f"{r.get('title','')} {r.get('hit_titles','')}"
            fit = classify_fit(r.get("handle", ""), text)
            load_ = r.get("sponsor_load")
            row = {
                "signal": src,
                "creator": r.get("title") or r.get("handle", ""),
                "handle": r.get("handle", ""),
                "url": r.get("url", ""),
                "subs": subs,
                "hits": hits,
                "disclosed": disclosed,
                "brands": ", ".join(f"{k} x{v}" for k, v in sorted(b.items(), key=lambda x: -x[1])),
                "last_seen": r.get("last_seen", ""),
                "months_since": months_since(r.get("last_seen", ""), ref_date),
                "sponsor_load": float(load_) if load_ not in (None, "") else None,
                "shorts_share": float(r["shorts_share"]) if r.get("shorts_share") else None,
                "fit": fit,
                "pattern": r.get("pattern", ""),
                "off_thesis": fit in OFF_THESIS,
                "review": review.get((r.get("handle") or "").strip().lower(), ""),
                "example": r.get("example_url", ""),
                "example_title": r.get("example_title", ""),
            }
            row["priority"], row["why"] = priority(row)
            rows.append(row)

    order = {"Book": 0, "Test": 1, "Watch": 2, "Skip": 3}
    # Within a priority, on-thesis fit beats raw counts: the HelloFresh study's
    # own warning is that a standing-link creator's hit count is not bookings.
    fit_rank = {"home/cleaning": 0, "home DIY/reno": 1, "family": 2,
                "lifestyle/vlog": 3, "beauty": 4, "needs review": 5}
    rows.sort(key=lambda r: (order[r["priority"]], fit_rank.get(r["fit"], 6),
                             0 if r["signal"] == "competitor" else 1,
                             -r["disclosed"], -r["hits"], -r["subs"]))

    Workbook, Font, PatternFill, Alignment, col_letter = _xl()
    wb = Workbook(); wb.remove(wb.active)
    ws = wb.create_sheet("Shortlist")
    ws.cell(row=1, column=1, value="Homeaglow — creator shortlist").font = Font(
        name=FONT, size=TITLE_SIZE, bold=True, color=NAVY)
    ws.cell(row=2, column=1, value=(
        f"Both studies merged. competitor = a rival PAID them, disclosed on the video (direct "
        f"evidence, same purchase). donor = HelloFresh rebooked them (transfer argument, their "
        f"audience transacts). Competitor rows outrank donor rows at equal counts. "
        f"Competitor scan {comp_date}; donor scan {donor_date}.")).font = Font(
        name=FONT, size=SUB_SIZE, color=GREY)

    cols = [("#", 5, None), ("Priority", 10, None), ("Why", 44, None), ("Creator", 24, None),
            ("Handle", 20, None), ("Channel URL", 26, None), ("Subscribers", 12, "#,##0"),
            ("Signal", 11, None), ("Evidence", 26, None), ("Hits", 7, "#,##0"),
            ("Disclosed", 10, "#,##0"), ("Fit", 15, None), ("Pattern", 10, None), ("Last Placement", 14, None),
            ("Months Since", 12, "#,##0"), ("Sponsor Load", 12, "0%"),
            ("Shorts Share", 12, "0%"), ("Review", 30, None), ("Example Video", 30, None),
            ("Example Title", 40, None)]
    hf = Font(name=FONT, size=HEAD_SIZE, bold=True, color=NAVY)
    hfill = PatternFill("solid", start_color=HEADER_BG, end_color=HEADER_BG)
    for i, (h, w, _) in enumerate(cols, start=1):
        c = ws.cell(row=3, column=i, value=h)
        c.font, c.fill = hf, hfill
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[col_letter(i)].width = w
    body = Font(name=FONT, size=BODY_SIZE)
    link = Font(name=FONT, size=BODY_SIZE, color=INPUT_BLUE, underline="single")
    band = PatternFill("solid", start_color=BAND, end_color=BAND)
    for n, r in enumerate(rows):
        vals = [n + 1, r["priority"], r["why"], r["creator"], r["handle"], r["url"], r["subs"],
                r["signal"], r["brands"], r["hits"], r["disclosed"], r["fit"], r["pattern"],
                r["last_seen"],
                r["months_since"], r["sponsor_load"], r["shorts_share"], r["review"],
                r["example"], r["example_title"]]
        for i, (v, (h, _, fmt)) in enumerate(zip(vals, cols), start=1):
            c = ws.cell(row=4 + n, column=i, value=v)
            c.font = body
            if fmt:
                c.number_format = fmt
            if h in ("Channel URL", "Example Video") and isinstance(v, str) and v.startswith("http"):
                c.hyperlink, c.font = v, link
            if n % 2:
                c.fill = band
    ws.freeze_panes = "D4"
    ws.auto_filter.ref = f"A3:{col_letter(len(cols))}{max(3 + len(rows), 4)}"
    ws.row_dimensions[3].height = 28

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    from collections import Counter
    print(f"{len(rows)} creators | " + " ".join(
        f"{k}:{v}" for k, v in sorted(Counter(r['priority'] for r in rows).items())), file=sys.stderr)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "outputs/homeaglow/creator-shortlist.xlsx")
    a = ap.parse_args()
    print(f"wrote {build(a.out)}", file=sys.stderr)


if __name__ == "__main__":
    main()
