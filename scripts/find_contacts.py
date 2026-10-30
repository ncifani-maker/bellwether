#!/usr/bin/env python3
"""
find_contacts.py — Bellwether Herald, step 1: a verified way to reach a creator.

Herald drafts; Nicole sends. This finds the address to send to, in the order the
brief allows (CLAUDE.md, contact rule, approved 2026-09-23):

  1. The channel's own description. Creators who take sponsorships put a business
     address there themselves. Free, public, and the most defensible source there
     is. 1 quota unit per 50 channels.
  2. Hunter domain search on a website the creator links from that description,
     restricted to role addresses and business roles. Costs a Hunter credit.
  3. Hunter verification of every address from either step, always.

Never: a guessed address, a personal address the creator did not publish, or the
captcha-gated email on a YouTube About page. That last one is Nicole's to reveal
by hand if she wants it; bypassing a captcha is not something an agent does.

Addresses land in data/contacts.csv, which is gitignored: it is the only file in
the project holding personal data. The terminal shows the domain and the verify
status, not the full address, so a shared screen or a pasted log does not leak a
working list of emails.

Usage:
  python3 scripts/find_contacts.py --from-shortlist outputs/homeaglow/creator-shortlist.xlsx --priority Book
  python3 scripts/find_contacts.py --handles @rachelleea,@kennadeekay --brand homeaglow
  python3 scripts/find_contacts.py --from-shortlist <xlsx> --top 5 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _budget  # noqa: E402
import _emails  # noqa: E402
from _emails import BUSINESS_CUE, EMAIL_RE  # noqa: E402
from _keys import get, require  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONTACTS = ROOT / "data" / "contacts.csv"
YT_API = "https://www.googleapis.com/youtube/v3"
HUNTER = "https://api.hunter.io/v2"
TIMEOUT = 30

FIELDS = ["found_at", "brand", "handle", "creator", "channel_url", "name", "role", "email",
          "kind", "source", "verify_status", "verify_score", "usable", "notes"]

URL_RE = re.compile(r"https?://([A-Za-z0-9.\-]+\.[A-Za-z]{2,})(?:/\S*)?")
# "for business inquiries", "business:", "collabs" — the line a creator writes
# when they mean "this is the address to pitch me at".
ROLE_LOCALPART = ("hello", "contact", "info", "business", "inquiries", "team", "press",
                  "partnerships", "collabs", "management", "booking", "media", "pr")
BUSINESS_POSITION = re.compile(r"founder|owner|editor|partner|marketing|manager|talent|brand|"
                               r"business|creator|media", re.I)
# Hosts a creator links to that are never their own site.
NOT_A_SITE = {"youtube.com", "www.youtube.com", "youtu.be", "instagram.com", "www.instagram.com",
              "tiktok.com", "www.tiktok.com", "twitter.com", "x.com", "facebook.com",
              "www.facebook.com", "amazon.com", "amzn.to", "linktr.ee", "bit.ly", "discord.gg",
              "patreon.com", "www.patreon.com", "open.spotify.com", "podcasts.apple.com",
              "pinterest.com", "www.pinterest.com", "threads.net", "snapchat.com",
              "shopmy.us", "liketk.it", "ltk.app.link", "go.magik.ly"}


def fetch(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.getcode(), json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8", "replace"))
        except ValueError:
            return exc.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def mask(email: str) -> str:
    """a***@example.com — enough to tell two apart, not a usable address."""
    if "@" not in email:
        return email
    local, _, domain = email.partition("@")
    return "{}***@{}".format(local[:1], domain)


# --- sources ------------------------------------------------------------------

def channel_records(channel_ids, key):
    """channels.list in batches of 50. 1 quota unit per call."""
    out = {}
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i + 50]
        url = YT_API + "/channels?" + urllib.parse.urlencode({
            "part": "snippet", "id": ",".join(batch), "maxResults": 50, "key": key})
        status, body = fetch(url)
        if status != 200:
            sys.stderr.write("  channels.list HTTP {}\n".format(status))
            continue
        for item in body.get("items", []):
            sn = item.get("snippet") or {}
            out[item["id"]] = {"title": sn.get("title", ""), "description": sn.get("description", "")}
    return out


def from_description(text):
    """-> (emails, candidate site domains). Both straight from what they published."""
    emails = []
    for match in EMAIL_RE.finditer(text or ""):
        email = match.group(0).strip(".,;:)")
        line_start = max(0, text.rfind("\n", 0, match.start()))
        context = text[line_start:match.end() + 40]
        emails.append({"email": email, "business_cue": bool(BUSINESS_CUE.search(context))})
    sites = []
    for match in URL_RE.finditer(text or ""):
        host = match.group(1).lower()
        if host.startswith("www."):
            host = host[4:]
        if host in NOT_A_SITE or host.replace("www.", "") in NOT_A_SITE:
            continue
        if host not in sites:
            sites.append(host)
    return emails, sites


# What the last domain search returned BEFORE the contact rule filtered it.
# "Hunter found nothing" and "nothing passed our rule" are different findings:
# on 2026-10-09 newmodernmom.com was logged as the first when it was the second.
LAST_SEARCH = {"returned": 0}


def hunter_domain_search(domain, key, single_operator=False):
    """Role addresses and business roles, plus the owner of a one-person site.

    One Hunter search credit per call, however many addresses come back
    (measured 2026-10-09: five results cost one credit). `single_operator` is
    the caller's to set, from evidence about the site (site_profile.py's
    creator tier with one author), never assumed: on a one-person site the
    owner's address on the site's own domain IS the business contact
    (CHANGELOG D14). It is still verified like every other address.
    """
    status, body = fetch(HUNTER + "/domain-search?" + urllib.parse.urlencode(
        {"domain": domain, "limit": 10, "api_key": key}))
    if status != 200:
        return [], "HTTP {}".format(status)
    out = []
    emails = (body.get("data") or {}).get("emails", [])
    LAST_SEARCH["returned"] = len(emails)
    for item in emails:
        email = item.get("value") or ""
        local = email.split("@")[0].lower()
        position = item.get("position") or ""
        is_role = item.get("type") == "generic" or local in ROLE_LOCALPART
        is_business = bool(BUSINESS_POSITION.search(position))
        own_domain = email.rsplit("@", 1)[-1].lower() in (domain.lower(), "www." + domain.lower())
        is_owner = single_operator and own_domain
        if not (is_role or is_business or is_owner):
            continue      # a named person with no business role is not ours to take
        out.append({
            "email": email,
            "name": " ".join(x for x in (item.get("first_name"), item.get("last_name")) if x),
            "role": position,
            "kind": "site-role" if is_role else ("site-business" if is_business else "site-owner"),
        })
    return out, ""


def hunter_verify(email, key):
    status, body = fetch(HUNTER + "/email-verifier?" + urllib.parse.urlencode(
        {"email": email, "api_key": key}))
    if status != 200:
        return {"status": "error", "score": "", "note": "HTTP {}".format(status)}
    data = body.get("data") or {}
    return {"status": data.get("status", "unknown"), "score": data.get("score", ""), "note": ""}


# The brief's rule, as a lookup: what each verifier verdict means for sending.
USABLE = {
    "valid": ("yes", ""),
    "accept_all": ("decide", "catch-all domain: deliverable but unconfirmed, common on small blogs"),
    "webmail": ("yes", "webmail address the creator published themselves"),
    "unknown": ("no", "unverifiable: use a contact form instead"),
    "risky": ("no", "risky: use a contact form instead"),
    "disposable": ("no", "disposable address"),
    "invalid": ("no", "invalid: would bounce"),
}


def read_contacts():
    if not CONTACTS.exists():
        return []
    with CONTACTS.open() as fh:
        return list(csv.DictReader(fh))


def write_rows(rows):
    """Upsert on (handle, email). A second run corrects a row, never duplicates it."""
    CONTACTS.parent.mkdir(parents=True, exist_ok=True)
    existing = read_contacts()
    incoming = {(r["handle"], r["email"]) for r in rows}
    kept = [r for r in existing if (r.get("handle"), r.get("email")) not in incoming]
    with CONTACTS.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in kept + rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def verify_only(brand, key, yes):
    """Verify addresses already found. No YouTube calls, no Hunter searches.

    The natural second half of a --no-hunter run: find for free, look at what
    came back, then spend only on checking the ones worth keeping.
    """
    rows = [r for r in read_contacts()
            if r.get("email") and r.get("verify_status") in ("", "not checked")]
    if not rows:
        print("nothing to verify: every address in data/contacts.csv has a status.")
        return 0
    code, lines = _budget.gate("hunter", len(rows), remaining=None, yes=yes, unit="verifications")
    print("Verify · {} addresses already found".format(len(rows)))
    for line in lines:
        print("  " + line)
    if code != _budget.OK:
        return code
    for r in rows:
        verdict = hunter_verify(r["email"], key)
        usable, note = USABLE.get(verdict["status"], ("decide", verdict["status"]))
        r["verify_status"], r["verify_score"], r["usable"] = (
            verdict["status"], verdict["score"], usable)
        r["notes"] = "; ".join(x for x in (note, r.get("notes", "")) if x)
        print("  {:<22} {:<28} {:<11} {}".format(
            r["handle"][:22], mask(r["email"])[:28], verdict["status"], usable))
    _budget.log("hunter", len(rows), "verifications", "find-contacts", brand, "", "verify-only pass")
    write_rows(rows)
    ready = [r for r in rows if r["usable"] == "yes"]
    print("\n{} verified, {} ready to send".format(len(rows), len(ready)))
    print("wrote {}".format(CONTACTS.relative_to(ROOT)))
    return 0


# --- inputs -------------------------------------------------------------------

def from_shortlist(path, priority=None, top=None, review_only=False):
    from openpyxl import load_workbook
    ws = load_workbook(path, read_only=True, data_only=True)["Shortlist"]
    rows = list(ws.iter_rows(values_only=True))
    header_at = next((i for i, r in enumerate(rows) if r and str(r[0]).strip() == "#"), 0)
    header = [str(c or "").strip() for c in rows[header_at]]
    idx = {h: i for i, h in enumerate(header)}
    out = []
    for r in rows[header_at + 1:]:
        if not r or not r[idx.get("Handle", 1)]:
            continue
        def cell(name):
            i = idx.get(name)
            return str(r[i]).strip() if i is not None and i < len(r) and r[i] is not None else ""
        if priority and cell("Priority").lower() != priority.lower():
            continue
        if review_only and not cell("Review"):
            continue
        out.append({"handle": cell("Handle"), "creator": cell("Creator"),
                    "channel_url": cell("Channel URL"), "priority": cell("Priority"),
                    "review": cell("Review")})
        if top and len(out) >= top:
            break
    return out


def channel_id_of(url):
    match = re.search(r"/channel/(UC[\w\-]+)", url or "")
    return match.group(1) if match else ""


# --- web lane: review sites ---------------------------------------------------
# Added 2026-10-09 for the curated affiliate-seo-creators list. Same rule as the
# creator path: the site's own published pages first (free), Hunter second,
# verification always (CHANGELOG D14 for one-person sites).

def published_on_site(domain, urls):
    """Emails the site publishes on its own pages. Fetches the pages, then defers
    to _emails.published_emails, the one definition shared with research.
    -> list of (email, page_url, business_cue), best first. No API, no spend."""
    import site_profile
    pages = []
    for url in urls:
        if url:
            status, html = site_profile.fetch(url)
            if status == 200 and html:
                pages.append((url, html))
    return _emails.published_emails(domain, pages)


def hunter_used(key):
    status, body = fetch(HUNTER + "/account?" + urllib.parse.urlencode({"api_key": key}))
    if status != 200:
        return None
    req = (body.get("data") or {}).get("requests") or {}
    return ((req.get("searches") or {}).get("used"), (req.get("verifications") or {}).get("used"))


def run_sites(args):
    import csv as _csv
    src = Path(args.from_sites)
    rows = list(_csv.DictReader(src.open(encoding="utf-8-sig")))
    all_domains = [r["domain"].strip() for r in rows]
    # Skip sites this brief has already resolved, whatever the outcome (an
    # address, or a search that found nothing). Re-running the same list after
    # a Hunter reset would otherwise re-verify and re-search every one of them:
    # caught 2026-10-22 before it spent ~60 credits. --refresh redoes them.
    if not args.refresh and CONTACTS.exists():
        with CONTACTS.open() as fh:
            resolved = {r["handle"] for r in _csv.DictReader(fh) if r.get("brand") == args.brand}
        before = len(rows)
        rows = [r for r in rows if r["domain"].strip() not in resolved]
        if before != len(rows):
            print("  skipping {} site(s) already resolved for {} (--refresh to redo)".format(
                before - len(rows), args.brand))
    if args.top:
        rows = rows[:args.top]
    if not rows:
        print("nothing left to look up for {}".format(args.brand))
        return 0
    key = require("HUNTER_API_KEY")
    slug = args.brand

    # 1. Free pass: what each site publishes itself.
    from concurrent.futures import ThreadPoolExecutor
    def pages(r):
        home = "https://" + r["domain"] + "/"
        return [r.get("contact_page"), r.get("about_page"), home]
    with ThreadPoolExecutor(max_workers=8) as pool:
        published = dict(zip([r["domain"] for r in rows],
                             pool.map(lambda r: published_on_site(r["domain"], pages(r)), rows)))
    need_hunter = [r for r in rows if not published[r["domain"]]]

    # 2. Budget, now that the real numbers are known.
    s_code, s_lines = _budget.gate("hunter", len(need_hunter), yes=args.yes, unit="searches")
    planned_verifs = (len(rows) - len(need_hunter)) + len(need_hunter)
    v_code, v_lines = _budget.gate("hunter", planned_verifs, yes=True, unit="verifications")
    print("Contacts · {} · {} sites".format(slug, len(rows)))
    print("  {} publish an address on their own pages (free) · {} need a Hunter search".format(
        len(rows) - len(need_hunter), len(need_hunter)))
    for line in s_lines + v_lines:
        print("  " + line)
    if args.dry_run:
        return 0
    if v_code == _budget.REFUSE:
        return v_code
    if s_code == _budget.CONFIRM:
        return s_code
    # A search refusal does not stop the free half: search as many as the cap
    # allows, in the team's order (most brands reviewed first), queue the rest.
    cfg = (_budget.budgets().get("hunter") or {})
    allowed = max(0, (cfg.get("monthly_search_cap") or 0) - _budget.month_used("hunter", unit="searches"))
    allowed = min(allowed, len(need_hunter))
    if s_code == _budget.REFUSE:
        print("  searching the first {} in the team's order; the other {} wait for search budget".format(
            allowed, len(need_hunter) - allowed))
    if allowed > (cfg.get("confirm_above") or 0) and not args.yes:
        print("  STOPPED before spending: {} searches is over the confirm threshold of {}. "
              "Re-run with --yes.".format(allowed, cfg.get("confirm_above")))
        return _budget.CONFIRM

    found, measured, searched = {}, [], 0
    out, verifs = [], 0
    today = date.today().isoformat()

    def base(d):
        return {"found_at": today, "brand": slug, "handle": d, "creator": "", "channel_url": "https://" + d + "/"}

    try:
        for r in rows:
            d = r["domain"]
            pub = published[d]
            if pub:
                email, url, cue = pub[0]
                found[d] = {"email": email, "kind": "site-published", "source": url, "name": "", "role": ""}
                continue
            if searched >= allowed:
                found[d] = None
                continue
            single = r.get("tier") == "creator blog" and str(r.get("authors_on_home") or "9") in ("0", "1")
            before = hunter_used(key)
            hits, err = hunter_domain_search(d, key, single_operator=single)
            after = hunter_used(key)
            searched += 1
            returned = 0 if err else LAST_SEARCH["returned"]
            # A counter already at the plan's limit cannot show a charge, so a
            # zero there proves nothing. Only below the limit is a delta evidence.
            charged = (after[0] - before[0]) if (before and after and after[0] < 50) else None
            measured.append((d, returned, charged))
            if hits:
                # Partnerships people and addresses first; Hunter's own order otherwise.
                best = min(hits, key=lambda h: _emails.partner_rank(h["email"].split("@")[0], h.get("role", "")))
                found[d] = dict(best, source="Hunter domain search")
            else:
                why = ("Hunter error: " + err if err else
                       "Hunter found nothing" if returned == 0 else
                       "Hunter found {} address(es); none fit the contact rule".format(returned))
                found[d] = {"email": "", "kind": "none", "source": why, "name": "", "role": ""}

        # 3. Verify every address found, whatever its source.
        for r in rows:
            d, f = r["domain"], found.get(r["domain"])
            if not f or not f["email"]:
                continue
            v = hunter_verify(f["email"], key); verifs += 1
            usable, note = USABLE.get(v["status"], ("decide", v["status"]))
            out.append(dict(base(d), name=f.get("name", ""), role=f.get("role", ""), email=f["email"],
                            kind=f["kind"], source=f["source"], verify_status=v["status"],
                            verify_score=v["score"], usable=usable, notes=note))
            print("  {:<30} {:<30} {:<11} {}".format(d[:30], mask(f["email"])[:30], v["status"], usable),
                  flush=True)
    finally:
        # Runs even if the process is interrupted, so paid results are never lost
        # (2026-10-22: a run detached from its terminal and only saved by luck).
        # Found-but-unverified addresses are kept as `pending`; --verify-only
        # finishes them. Spend is logged for whatever was actually sent.
        done = {o["handle"] for o in out}
        for d, f in found.items():
            if not f or d in done:
                continue
            if f["email"]:
                out.append(dict(base(d), name=f.get("name", ""), role=f.get("role", ""), email=f["email"],
                                kind=f["kind"], source=f["source"], verify_status="not checked",
                                verify_score="", usable="pending",
                                notes="found, not yet verified: run --verify-only"))
            else:
                out.append(dict(base(d), name="", role="", email="", kind="none", source=f["source"],
                                verify_status="", verify_score="", usable="no",
                                notes="nothing published, Hunter found nothing usable: contact form or skip"))
        if searched:
            _budget.log("hunter", searched, "searches", "find-contacts", slug, "", "site mode")
        if verifs:
            _budget.log("hunter", verifs, "verifications", "find-contacts", slug, "", "site mode")
        write_rows(out)
        out_dir = ROOT / "outputs" / slug / (args.slate or today[:7])
        out_dir.mkdir(parents=True, exist_ok=True)
        if measured:
            # Kept on disk, not just printed: the 2026-10-22 measurement was lost
            # with a dead terminal. Domains and counts only, no addresses.
            log_path = out_dir / "hunter-charges.csv"
            new_log = not log_path.exists()
            with log_path.open("a", newline="") as fh:
                w = _csv.writer(fh)
                if new_log:
                    w.writerow(["date", "domain", "addresses_returned", "credits_charged"])
                for d, n, ch in measured:
                    w.writerow([today, d, n, "" if ch is None else ch])

    # The summary covers the WHOLE list, from data/contacts.csv, not just this
    # run's sites (a re-run used to overwrite it with the latest batch only).
    with CONTACTS.open() as fh:
        known = {r["handle"]: r for r in _csv.DictReader(fh) if r.get("brand") == slug}
    summary = []
    for d in all_domains:
        k = known.get(d)
        if k is None:
            summary.append({"domain": d, "found_via": "waiting: Hunter search cap reached", "kind": "",
                            "verify_status": "", "usable": ""})
        elif k["kind"] == "none":
            summary.append({"domain": d, "found_via": "nothing found", "kind": "none",
                            "verify_status": "", "usable": "no"})
        else:
            summary.append({"domain": d, "found_via": "published on site" if k["kind"] == "site-published"
                            else "Hunter", "kind": k["kind"], "verify_status": k["verify_status"],
                            "usable": k["usable"]})
    summ = out_dir / "contacts-summary.csv"
    with summ.open("w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=["domain", "found_via", "kind", "verify_status", "usable"])
        w.writeheader(); w.writerows(summary)

    from collections import Counter
    c = Counter(s["usable"] for s in summary)
    print("\n{} looked up now · whole list of {}: ready to send {} · you decide {} · not usable {} · "
          "pending {} · waiting for Hunter budget {}".format(
        len(rows), len(summary), c.get("yes", 0), c.get("decide", 0), c.get("no", 0), c.get("pending", 0),
        sum(1 for s in summary if s["found_via"].startswith("waiting"))))
    print("Hunter spent: {} searches, {} verifications".format(searched, verifs))
    empties = [m for m in measured if m[1] == 0 and m[2] is not None]
    if empties:
        print("empty searches charged: {} of {} (measured below the plan limit)".format(
            sum(1 for m in empties if m[2] > 0), len(empties)))
    elif measured:
        print("empty-search charging: not measurable this run (no empties below the plan limit)")
    print("wrote {} (gitignored) and {}".format(CONTACTS.relative_to(ROOT), summ.relative_to(ROOT)))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Find and verify a way to reach each creator.")
    ap.add_argument("--from-shortlist", type=Path, help="a build_shortlist.py workbook")
    ap.add_argument("--handles", help="comma-separated @handles (needs --channels-from for urls)")
    ap.add_argument("--brand", required=True, help="brief slug, for the contacts file and the ledger")
    ap.add_argument("--priority", help="only rows with this Priority, e.g. Book")
    ap.add_argument("--reviewed", action="store_true", help="only rows you have reviewed by hand")
    ap.add_argument("--top", type=int, help="first N rows after filtering")
    ap.add_argument("--no-hunter", action="store_true", help="description only; spend no credits")
    ap.add_argument("--verify-only", action="store_true",
                    help="verify addresses already in data/contacts.csv; no lookups")
    ap.add_argument("--from-sites", type=Path,
                    help="a curated sites CSV (domain, tier, authors_on_home, contact_page, about_page)")
    ap.add_argument("--slate", help="output slate for the no-address summary, default this month")
    ap.add_argument("--refresh", action="store_true",
                    help="site mode: redo sites already resolved in data/contacts.csv")
    ap.add_argument("--dry-run", action="store_true", help="plan and budget only")
    ap.add_argument("--yes", action="store_true", help="approve a run over the confirm threshold")
    args = ap.parse_args()

    if args.verify_only:
        return verify_only(args.brand, require("HUNTER_API_KEY"), args.yes)
    if args.from_sites:
        return run_sites(args)

    if args.from_shortlist:
        targets = from_shortlist(args.from_shortlist, args.priority, args.top, args.reviewed)
    elif args.handles:
        targets = [{"handle": h.strip(), "creator": "", "channel_url": "", "priority": "", "review": ""}
                   for h in args.handles.split(",") if h.strip()]
    else:
        sys.exit("give --from-shortlist or --handles")
    if not targets:
        sys.exit("no rows matched. Check --priority / --reviewed / --top.")

    yt_key = require("YOUTUBE_API_KEY")
    hunter_key = "" if args.no_hunter else require("HUNTER_API_KEY")

    # Read the descriptions FIRST, then budget. Gating on the number of creators
    # would price the worst case, and the worst case is nothing like the real one:
    # a creator who publishes a business address costs no Hunter credit at all,
    # and one who links no website cannot be searched for even in principle.
    # A description read is 1 YouTube unit per 50 channels, which is free in
    # every sense that matters here.
    ids = [channel_id_of(t["channel_url"]) for t in targets]
    records = channel_records([i for i in ids if i], yt_key)
    for target, cid in zip(targets, ids):
        rec = records.get(cid, {})
        target["_desc"] = rec.get("description", "")
        target["_title"] = rec.get("title", "")
        target["_emails"], target["_sites"] = from_description(target["_desc"])

    needs_search = [t for t in targets if not t["_emails"] and t["_sites"]]
    no_route = [t for t in targets if not t["_emails"] and not t["_sites"]]
    found_count = sum(len(t["_emails"]) for t in targets)
    planned_searches = 0 if args.no_hunter else len(needs_search)

    print("Contacts · {} · {} creators".format(args.brand, len(targets)))
    print("  {} publish an address (free) · {} link a site to search · "
          "{} publish neither".format(len(targets) - len(needs_search) - len(no_route),
                                      len(needs_search), len(no_route)))
    code, lines = _budget.gate("hunter", planned_searches, remaining=None,
                               yes=args.yes, unit="searches")
    for line in lines:
        print("  " + line)
    if not args.no_hunter:
        print("  plus {} verifications (free tier is 100 a month)".format(found_count))

    if args.dry_run:
        print("\ndry run, nothing spent:")
        for t in targets:
            route = ("publishes {} address(es)".format(len(t["_emails"])) if t["_emails"]
                     else "search {}".format(t["_sites"][0]) if t["_sites"]
                     else "no address and no site: ask by hand or skip")
            print("  · {:<22} {}".format(t["handle"][:22], route))
        return 0
    if code != _budget.OK:
        return code

    rows, searches, verifications = [], 0, 0
    for target in targets:
        creator = target["creator"] or target["_title"]
        emails, sites = target["_emails"], target["_sites"]
        found = []

        for e in emails:
            found.append({"email": e["email"], "name": "", "role": "",
                          "kind": "channel-description",
                          "source": "YouTube channel description"
                                    + (" (business line)" if e["business_cue"] else "")})

        if not found and sites and not args.no_hunter:
            for site in sites[:1]:            # one domain per creator: credits are scarce
                hits, err = hunter_domain_search(site, hunter_key)
                searches += 1
                if err:
                    sys.stderr.write("  {} hunter: {}\n".format(target['handle'], err))
                for h in hits[:2]:
                    found.append({"email": h["email"], "name": h["name"], "role": h["role"],
                                  "kind": h["kind"], "source": "Hunter domain search: " + site})

        if not found:
            rows.append({"found_at": date.today().isoformat(), "brand": args.brand,
                         "handle": target["handle"], "creator": creator,
                         "channel_url": target["channel_url"], "name": "", "role": "", "email": "",
                         "kind": "none", "source": "no published address found",
                         "verify_status": "", "verify_score": "", "usable": "no",
                         "notes": "no address in the channel description"
                                  + ("" if sites else " and no website linked")
                                  + ". Ask via the channel's About page by hand, or skip."})
            print("  {:<22} no published address".format(target["handle"][:22]))
            continue

        for f in found:
            verdict = ({"status": "not checked", "score": "", "note": ""} if args.no_hunter
                       else hunter_verify(f["email"], hunter_key))
            if not args.no_hunter:
                verifications += 1
            usable, note = USABLE.get(verdict["status"], ("decide", verdict["status"]))
            rows.append({"found_at": date.today().isoformat(), "brand": args.brand,
                         "handle": target["handle"], "creator": creator,
                         "channel_url": target["channel_url"], "name": f["name"], "role": f["role"],
                         "email": f["email"], "kind": f["kind"], "source": f["source"],
                         "verify_status": verdict["status"], "verify_score": verdict["score"],
                         "usable": usable,
                         "notes": "; ".join(x for x in (note, verdict["note"], target.get("review", "")) if x)})
            print("  {:<22} {:<28} {:<11} {}".format(
                target["handle"][:22], mask(f["email"])[:28], verdict["status"], usable))

    if searches:
        _budget.log("hunter", searches, "searches", "find-contacts", args.brand, "",
                    "{} creators".format(len(targets)))
    if verifications:
        _budget.log("hunter", verifications, "verifications", "find-contacts", args.brand, "", "")

    write_rows(rows)

    usable_rows = [r for r in rows if r["usable"] == "yes"]
    decide = [r for r in rows if r["usable"] == "decide"]
    print("\n{} addresses for {} creators · {} ready to send, {} for you to decide, "
          "{} creators with nothing published".format(
              len([r for r in rows if r['email']]), len(targets), len(usable_rows), len(decide),
              len([r for r in rows if not r['email']])))
    print("Hunter spent: {} searches, {} verifications".format(searches, verifications))
    print("wrote {} (gitignored: it holds personal data)".format(CONTACTS.relative_to(ROOT)))
    print("next: draft outreach for the ready ones. Herald drafts, you send.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
