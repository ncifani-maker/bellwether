#!/usr/bin/env python3
"""
import_seeds.py — pull a seed list from a spreadsheet into a brief.

The seed list lives where Nicole edits it: a spreadsheet. This reads a
downloaded .xlsx or .csv and writes briefs/<slug>/seeds.csv, the file every
scan reads and the seed gate (only `approved` rows run).

Column names are matched loosely, so the sheet does not have to be reformatted:
  query, query 1, query 2, keyword, seed   -> one seed per non-empty cell
  brand                                    -> carried on each seed
  category                                 -> carried on each seed
  a column with "complet" or "done"        -> a date there means already done
The first query column is the `singular` form and the second `plural`, matching
the "[brand] review" / "[brand] reviews" layout.

Re-importing an updated sheet is safe. Seeds already in seeds.csv keep their
status and note, so a run, a hold or a retirement is never undone by pulling
the sheet again. New seeds come in as `approved`: importing her own sheet is the
approval. Pass --hold to bring them in as `proposed` instead.

The source file is only read, never written.

Usage:
  python3 scripts/import_seeds.py ~/Downloads/seeds.xlsx affiliate-seo-creators --dry-run
  python3 scripts/import_seeds.py ~/Downloads/seeds.xlsx new-client --hold
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["keyword", "intent", "priority", "status", "added_by", "date", "note", "category", "brand", "form"]


def read_sheet(path: Path) -> list:
    """Rows as lists, header first. .xlsx reads the first sheet."""
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
        return [list(r) for r in ws.iter_rows(values_only=True)]
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return [row for row in csv.reader(fh)]


def columns(header):
    h = [str(c or "").strip().lower() for c in header]
    pick = lambda pred: [i for i, name in enumerate(h) if name and pred(name)]
    return {
        "queries": pick(lambda n: re.search(r"\b(query|keyword|seed)\b", n)),
        "brand": next(iter(pick(lambda n: n == "brand" or n.startswith("brand"))), None),
        "category": next(iter(pick(lambda n: n.startswith("categor") and "complet" not in n)), None),
        "done": next(iter(pick(lambda n: "complet" in n or n == "done")), None),
    }


def main():
    ap = argparse.ArgumentParser(description="Import a seed list spreadsheet into briefs/<slug>/seeds.csv.")
    ap.add_argument("file", type=Path, help="downloaded .xlsx or .csv")
    ap.add_argument("slug", help="brief slug; briefs/<slug>/ is created from the template if missing")
    ap.add_argument("--hold", action="store_true", help="bring new seeds in as `proposed`, not `approved`")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = ap.parse_args()

    src = args.file.expanduser()
    if not src.exists():
        sys.exit("no file at {}".format(src))
    rows = read_sheet(src)
    header_at = next((i for i, r in enumerate(rows) if any(re.search(r"query|keyword|seed", str(c or ""), re.I)
                                                          for c in r)), None)
    if header_at is None:
        sys.exit("no column named query, keyword or seed in {}".format(src.name))
    cols = columns(rows[header_at])

    today = date.today().isoformat()
    incoming = []
    for r in rows[header_at + 1:]:
        cell = lambda i: (str(r[i]).strip() if i is not None and i < len(r) and r[i] not in (None, "") else "")
        brand, category, done = cell(cols["brand"]), cell(cols["category"]), cell(cols["done"])
        for n, qi in enumerate(cols["queries"]):
            kw = cell(qi)
            if not kw:
                continue
            form = "singular" if n == 0 else "plural" if n == 1 else "form-{}".format(n + 1)
            when = done[:10] if done else ""
            if isinstance(r[cols["done"]] if cols["done"] is not None else None, datetime):
                when = r[cols["done"]].date().isoformat()
            incoming.append({
                "keyword": kw, "intent": "", "priority": "",
                "status": "done" if done else ("proposed" if args.hold else "approved"),
                "added_by": src.name, "date": today,
                "note": "completed by hand {}; not re-run".format(when) if done else "",
                "category": category, "brand": brand, "form": form,
            })

    folder = ROOT / "briefs" / args.slug
    seeds_path = folder / "seeds.csv"
    existing = []
    if seeds_path.exists():
        with seeds_path.open() as fh:
            existing = list(csv.DictReader(l for l in fh if not l.startswith("#")))
    known = {r["keyword"].strip().lower(): r for r in existing}

    added, kept, updated = [], 0, 0
    for row in incoming:
        old = known.get(row["keyword"].lower())
        if old is None:
            added.append(row)
            known[row["keyword"].lower()] = row
            continue
        kept += 1
        # Never undo a decision: keep status and note. Only fill brand and
        # category where the old row had none.
        for k in ("brand", "category", "form"):
            if not old.get(k) and row.get(k):
                old[k] = row[k]; updated += 1
    in_sheet = {r["keyword"].lower() for r in incoming}
    gone = [r for r in existing if r["keyword"].strip().lower() not in in_sheet]

    from collections import Counter
    print("Import · {} -> briefs/{}/seeds.csv".format(src.name, args.slug))
    print("  sheet: {} seeds ({} marked done in the sheet)".format(
        len(incoming), sum(1 for r in incoming if r["status"] == "done")))
    print("  new: {} ({})".format(len(added), dict(Counter(r["status"] for r in added)) or "-"))
    print("  already in the brief: {} (status kept)".format(kept))
    if gone:
        print("  in the brief but not in the sheet: {} (kept; nothing is deleted)".format(len(gone)))
    if args.dry_run:
        print("\ndry run, nothing written")
        return 0

    if not folder.exists():
        shutil.copytree(ROOT / "briefs" / "_template", folder)
        print("  created briefs/{}/ from the template: fill brief.md before outreach".format(args.slug))
    merged = existing + added
    with seeds_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in merged:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    now = Counter(r["status"] for r in merged)
    print("  wrote {} seeds: {}".format(len(merged), dict(now)))
    print("next: /run-seeds {} --dry-run".format(args.slug))
    return 0


if __name__ == "__main__":
    sys.exit(main())
