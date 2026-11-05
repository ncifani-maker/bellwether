#!/usr/bin/env python3
"""
emails_into_sheet.py — hand the team's own CSV back with email columns filled.

The team works in their own sheet. This takes the CSV they exported (any
columns, as long as one is `domain`), and writes a copy with two columns added
at the end:

  email          the address, filled only when it is safe to paste:
                 verified, or unconfirmed on an accept-all domain
  email status   why, for every row: verified / unconfirmed / bounces /
                 unverifiable / none found / waiting

Same rows, same order, original columns untouched, so a column pasted back
lines up. Addresses that failed verification are left out on purpose: a dead
address in a working file looks exactly like a live one.

A sheet that already has an `email` column (an earlier copy the team kept
working in) is filled in place instead: blank cells get an address, a cell
the team filled is never overwritten (a cell this pipeline filled, its status
still one of ours, is updated) (a different address is reported, not
replaced), and the status column is refreshed only where it still holds one
of this script's own statuses, so a team note survives. --status-column
names that column when it isn't called "email status".

The copy goes to the brief's own folder, briefs/<brief>/ (CHANGELOG D25; before that
D21, Nicole). That folder is inside the repo, so before writing, git is asked
whether the file is ignored; if it is not, nothing is written. `.gitignore`
covers "*with emails*.csv" and the pre-commit hook refuses email addresses,
so the copy cannot reach GitHub (D16). The source file is only read.

Usage:
  python3 scripts/emails_into_sheet.py "~/Downloads/Team list.csv" --brand affiliate-seo-creators
  python3 scripts/emails_into_sheet.py "~/Downloads/Outreach.csv" --brand affiliate-seo-creators \\
      --status-column contact_page
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTACTS = ROOT / "data" / "contacts.csv"


def status_for(c):
    if c is None:
        return "", "waiting: not looked up yet (Hunter budget)"
    if c["kind"] == "none" or not c["email"]:
        return "", "none found"
    if c["usable"] == "yes":
        return c["email"], "verified"
    if c["usable"] == "decide":
        return c["email"], "unconfirmed: domain accepts all mail"
    if c["usable"] == "pending":
        return "", "found, not yet verified"
    return "", {"invalid": "bounces (verifier: invalid)", "unknown": "unverifiable"}.get(
        c["verify_status"], "not usable: " + (c["verify_status"] or "?"))


def is_ours(status):
    """A status this script wrote, now or in an earlier wording, as opposed to a team note."""
    s = status.strip()
    return (s in ("", "verified", "unconfirmed: domain accepts all mail", "found, not yet verified",
                  "published on site, not yet verified",
                  "none found", "bounces (verifier: invalid)", "unverifiable")
            or s.startswith(("waiting", "not usable:")))


def main():
    ap = argparse.ArgumentParser(description="Add email columns to the team's CSV, as a copy.")
    ap.add_argument("file", type=Path, help="the team's exported CSV")
    ap.add_argument("--brand", required=True, help="brief slug the contacts were sourced under")
    ap.add_argument("--slate", default=__import__("datetime").date.today().strftime("%Y-%m"),
                    help="kept for old commands; the copy now goes in briefs/<brief>/")
    ap.add_argument("--status-column", default="email status",
                    help="the sheet's email-status column, if it already has one under another name")
    args = ap.parse_args()

    src = args.file.expanduser().resolve()
    import _paths
    # The brief's own review-sites.csv is updated in place (D26): one file from
    # research to outreach. Any other sheet (a team export) gets a copy, as before.
    in_place = src == _paths.review_sites(args.brand).resolve()
    raw = src.read_bytes()
    head = [l + "\n" for l in raw.decode("utf-8-sig").splitlines() if l.startswith("#")]
    bom = raw.startswith(b"\xef\xbb\xbf")
    # Editors such as Nimbalyst keep their view settings on a "# ..." first line.
    rows = list(csv.DictReader(l for l in raw.decode("utf-8-sig").splitlines() if not l.startswith("#")))
    if not rows or "domain" not in rows[0]:
        sys.exit("{} has no `domain` column".format(src.name))
    fields = list(rows[0].keys())
    scol = args.status_column
    if scol != "email status" and scol not in fields:
        sys.exit("{} has no `{}` column".format(src.name, scol))
    # Columns this run may write; every other column must come back byte-identical.
    ours = ["email", scol]
    out_fields = fields + [f for f in ours if f not in fields]

    with CONTACTS.open() as fh:
        contacts = {r["handle"]: r for r in csv.DictReader(l for l in fh if not l.startswith("#"))
                    if r["brand"] == args.brand}

    out_dir = _paths.brief_dir(args.brand)
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = src if in_place else out_dir / (src.stem + " (with emails).csv")
    # Third safeguard after .gitignore and the hook: refuse to write a file of
    # addresses into the repo unless git confirms it will ignore it.
    import subprocess
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", str(dst)]).returncode == 0
    if not ignored:
        sys.exit("refusing to write {}: git would not ignore it, so the addresses could be committed. "
                 "Check .gitignore covers '*with emails*.csv'.".format(dst.relative_to(ROOT)))

    out, changed, kept = [], [], []
    for r in rows:
        if in_place and r["domain"].strip() not in contacts:
            out.append(dict(r))      # not looked up for this brief: leave the row as it is
            continue
        email, status = status_for(contacts.get(r["domain"].strip()))
        theirs = (r.get("email") or "").strip()
        # An address this pipeline put there (its status is still ours, e.g. "published
        # on site, not yet verified") is ours to replace: a published address that
        # bounces must not stay in the sheet looking live. Only a team edit is kept.
        if theirs and is_ours(r.get(scol) or ""):
            theirs = ""
        conflict = bool(theirs) and theirs.lower() != email.lower()
        new = dict(r)
        if not theirs:
            new["email"] = email
        if conflict:
            kept.append((r["domain"], status))   # the team's address stands; ours is reported
        elif is_ours(r.get(scol) or ""):
            new[scol] = status
        if any((new.get(f) or "") != (r.get(f) or "") for f in ours):
            changed.append(r["domain"])
        out.append(new)
    with dst.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as fh:
        if in_place:
            fh.writelines(head)
        w = csv.DictWriter(fh, fieldnames=out_fields)
        w.writeheader(); w.writerows(out)

    back = list(csv.DictReader(l for l in dst.read_text(encoding="utf-8-sig").splitlines() if not l.startswith("#")))
    assert [b["domain"] for b in back] == [r["domain"] for r in rows], "row order changed"
    assert all(all(b[f] == r[f] for f in fields if f not in ours) for b, r in zip(back, rows)), \
        "a column changed"
    assert in_place or src.read_bytes() == raw, "source changed"

    print("{} {}".format("updated in place:" if in_place else "wrote", dst))
    print("  {} rows, same order, other columns unchanged{}".format(
        len(back), "" if in_place else "; source untouched"))
    if "email" in fields:
        print("  filled in place: {} row(s) changed in `email` / `{}`".format(len(changed), scol))
    print("  email filled in: {}".format(sum(1 for b in back if b["email"])))
    for k, v in Counter(b[scol] for b in back).most_common():
        print("    {:<44} {}".format(k, v))
    for d, s in kept:
        print("  kept the team's address for {}: contacts.csv differs ({}), check it".format(d, s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
