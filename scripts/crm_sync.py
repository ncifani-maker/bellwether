#!/usr/bin/env python
"""close-demo - Phase 3: sync verified contacts into Close as DRAFT leads.

Reads output/contacts.csv (+ opportunities.csv for url / fit / seed context) and
creates one Close lead per target, with the contact + verified email. Metadata
(motion, fit, seed, relevance, ranking URL) goes in the lead description so leads
are filterable by motion via Close Smart Views.

SAFETY:
  * Dry-run by default - prints what it WOULD create and writes nothing.
  * Pass --commit to actually POST leads.
  * Creating a lead NEVER sends an email. Sequences are armed and fired
    separately, by a human. This script only stages draft leads.

Reads CLOSE_API_KEY from keys.txt / env (never the CLI, so the key stays out of
process listings and shell history).
"""
import os
import sys
import csv
import json
from collections import Counter

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "..", "output")
BASE = "https://api.close.com/api/v1"


def load_key():
    if os.environ.get("CLOSE_API_KEY"):
        return os.environ["CLOSE_API_KEY"]
    for fname in ("keys.txt", ".env"):
        path = os.path.join(ROOT, fname)
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                if key.strip() == "CLOSE_API_KEY":
                    return val.strip().strip('"').strip("'")
    return ""


CLOSE_API_KEY = load_key()


def read_csv(path):
    # Skip leading comment lines (e.g. an editor's "# nimbalyst:" header).
    with open(path) as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


# Proper display names (Hunter org field / known brands). Fallback derives from domain.
NAME_OVERRIDES = {
    "technologyadvice.com": "TechnologyAdvice",
    "solutionsreview.com": "Solutions Review",
    "pcmag.com": "PCMag",
    "forbes.com": "Forbes (Advisor)",
    "emailtooltester.com": "EmailToolTester",
    "efficient.app": "Efficient App",
    "zapier.com": "Zapier",
    "uschamber.com": "U.S. Chamber of Commerce (CO-)",
    "salesdorado.com": "Salesdorado",
    "hackceleration.com": "Hackceleration",
    "crm.org": "CRM.org",
    "getvoip.com": "GetVoIP",
    "geekflare.com": "Geekflare",
    "marketbetter.ai": "MarketBetter",
    "onsaas.me": "ONSAAS",
    "business-software.com": "Business-Software.com",
    "cuspera.com": "Cuspera",
    "callboxinc.com": "Callbox",
    "vendr.com": "Vendr",
    "custify.com": "Custify",
    "clevenio.com": "Clevenio",
    "fayedigital.com": "Faye (Faye Digital)",
    "prospeo.io": "Prospeo",
    "zeeg.me": "Zeeg",
    "bettercontact.rocks": "BetterContact",
    "saleshandy.com": "Saleshandy",
    "forecastio.ai": "Forecastio",
    "blog.sellerant.com": "Sellerant",
    "kobedigital.com": "Kobe Digital",
}


def org_name(domain):
    if domain in NAME_OVERRIDES:
        return NAME_OVERRIDES[domain]
    base = domain.replace("blog.", "").replace("www.", "").split(".")[0]
    return base.replace("-", " ").title()


def build_payloads():
    contacts = read_csv(os.path.join(OUT, "contacts.csv"))
    opps = {r["domain"]: r for r in read_csv(os.path.join(OUT, "opportunities.csv"))}
    payloads, skipped = [], []
    for c in contacts:
        email = (c.get("email") or "").strip()
        domain = (c.get("opportunity_domain") or "").strip()
        if not email:
            skipped.append(domain)
            continue
        opp = opps.get(domain, {})
        desc = "motion={} | fit={} | seed={} | deliverability={} | rank_url={} | {}".format(
            c.get("motion", ""), opp.get("fit_score", ""), opp.get("seed_keyword", ""),
            c.get("verified", ""), opp.get("ranking_url", ""), opp.get("relevance_note", ""),
        )
        contact = {"emails": [{"email": email, "type": "office"}]}
        if (c.get("name") or "").strip():
            contact["name"] = c["name"].strip()
        if (c.get("role") or "").strip():
            contact["title"] = c["role"].strip()
        payloads.append((domain, c.get("motion", ""), {
            "name": org_name(domain),
            "url": "https://" + domain,
            "description": desc,
            "contacts": [contact],
        }))
    return payloads, skipped


def get_json(auth, path):
    try:
        r = requests.get(BASE + path, auth=auth, timeout=30)
    except requests.RequestException as exc:
        sys.stderr.write("ERROR GET {}: {}\n".format(path, exc))
        return {}
    if r.status_code != 200:
        sys.stderr.write("WARN GET {}: HTTP {} {}\n".format(path, r.status_code, r.text[:120]))
        return {}
    return r.json()


def enroll(auth, commit):
    """Enroll each lead's contact into the Close Sequence matching its motion.

    Dry-run by default: discovers the org's sequences + sender accounts and prints
    the full plan, writing nothing. --commit actually creates sequence
    subscriptions, which STARTS SENDING on an active sequence (the human gate).
    Skips HOLD-risky leads and gaps.
    """
    sequences = (get_json(auth, "/sequence/") or {}).get("data", []) or []
    accounts = (get_json(auth, "/connected_account/") or {}).get("data", []) or []

    sys.stderr.write("\nConnected sender accounts:\n")
    for a in accounts:
        sys.stderr.write("  - type={} email={} id={}\n".format(
            a.get("type"), a.get("email") or a.get("name"), a.get("id")))
    if not accounts:
        sys.stderr.write("  (none — connect a sending email in Close before you can enroll)\n")

    sys.stderr.write("\nSequences in Close:\n")
    for s in sequences:
        sys.stderr.write("  - {!r} id={} status={}\n".format(s.get("name"), s.get("id"), s.get("status")))
    if not sequences:
        sys.stderr.write("  (none — create two sequences first: one 'editorial', one 'partner'/'referral')\n")

    def match_seq(motion):
        keys = {"editorial-outreach": ["editorial"], "referral-partner": ["partner", "referral"]}.get(motion, [])
        for s in sequences:
            name = (s.get("name") or "").lower()
            if any(k in name for k in keys):
                return s
        return None

    plan = []
    for c in read_csv(os.path.join(OUT, "contacts.csv")):
        email = (c.get("email") or "").strip()
        lead_id = (c.get("close_lead_id") or "").strip()
        status = (c.get("sequence_status") or "").strip()
        if not (email and lead_id) or status.startswith("blocked") or status.startswith("rejected"):
            continue
        motion = (c.get("motion") or "").strip()
        plan.append({"domain": c.get("opportunity_domain"), "email": email, "lead_id": lead_id,
                     "motion": motion, "hold": "hold-risky" in status, "seq": match_seq(motion)})

    sys.stderr.write("\nEnrollment plan ({} eligible):\n".format(len(plan)))
    for p in plan:
        seqname = p["seq"]["name"] if p["seq"] else "** NO MATCHING SEQUENCE **"
        sys.stderr.write("  {:<24} {:<18} -> {}{}\n".format(
            p["domain"], p["motion"], seqname, "  [HOLD: risky]" if p["hold"] else ""))

    if not commit:
        sys.stderr.write("\n--- DRY RUN: no one enrolled, nothing sent. ---\n")
        sys.stderr.write("Before `--enroll --commit`: create the 2 sequences + connect a sender, finalize copy\n"
                         "+ the 29 per-lead hooks. Commit skips HOLD-risky and gaps. Enrolling an active\n"
                         "sequence begins sending — that's the human gate.\n")
        return

    if not accounts:
        sys.exit("No connected sender account; cannot enroll.")
    sender = accounts[0]
    created = {}
    for p in plan:
        if p["hold"] or not p["seq"]:
            continue
        lead = get_json(auth, "/lead/" + p["lead_id"] + "/")
        contact_id = None
        for ct in (lead.get("contacts") or []):
            if any((em.get("email") or "").lower() == p["email"].lower() for em in (ct.get("emails") or [])):
                contact_id = ct.get("id")
                break
        if not contact_id and lead.get("contacts"):
            contact_id = lead["contacts"][0].get("id")
        payload = {
            "sequence_id": p["seq"]["id"], "contact_id": contact_id,
            "sender_account_id": sender.get("id"), "sender_name": "Nicole",
            "sender_email": sender.get("email"), "contact_email": p["email"],
        }
        r = requests.post(BASE + "/sequence_subscription/", auth=auth, json=payload, timeout=30)
        ok = r.status_code in (200, 201)
        created[p["domain"]] = r.json().get("id") if ok else None
        sys.stderr.write("{} {} -> {}\n".format(
            "enrolled" if ok else "FAILED", p["domain"],
            created[p["domain"]] or (str(r.status_code) + " " + r.text[:120])))
    state_dir = os.path.join(HERE, "..", "state")
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "close_enrollments.json"), "w") as fh:
        json.dump(created, fh, indent=2)
    sys.stderr.write("\nWROTE state/close_enrollments.json\n")


def main():
    commit = "--commit" in sys.argv
    if not CLOSE_API_KEY:
        sys.exit("CLOSE_API_KEY not found in env or keys.txt")
    auth = (CLOSE_API_KEY, "")

    me = requests.get(BASE + "/me/", auth=auth, timeout=30)
    if me.status_code != 200:
        sys.exit("Close auth failed: HTTP {} - {}".format(me.status_code, me.text[:200]))
    who = me.json()
    org = (who.get("organizations") or [{}])[0]
    sys.stderr.write("Connected to Close as {} | org: {} ({})\n".format(
        who.get("email"), org.get("name"), org.get("id")))

    if "--enroll" in sys.argv:
        enroll(auth, commit)
        return

    payloads, skipped = build_payloads()
    by_motion = Counter(m for _, m, _ in payloads)
    sys.stderr.write("\n{} leads to create  {}\n{} skipped (no email / gap)\n".format(
        len(payloads), dict(by_motion), len(skipped)))

    if not commit:
        sys.stderr.write("\n--- DRY RUN (no writes) ---\n")
        for domain, motion, p in payloads:
            sys.stderr.write("  [{}] {:<22} <- {}\n".format(
                motion, p["name"], p["contacts"][0]["emails"][0]["email"]))
        if skipped:
            sys.stderr.write("  skipped: {}\n".format(", ".join(skipped)))
        sys.stderr.write("\nRe-run with --commit to create these as draft leads.\n")
        return

    created = {}
    for domain, motion, p in payloads:
        r = requests.post(BASE + "/lead/", auth=auth, json=p, timeout=30)
        if r.status_code in (200, 201):
            created[domain] = r.json().get("id")
            sys.stderr.write("created {:<22} -> {}\n".format(domain, created[domain]))
        else:
            created[domain] = None
            sys.stderr.write("FAILED  {:<22} -> HTTP {} {}\n".format(domain, r.status_code, r.text[:160]))
    state_dir = os.path.join(HERE, "..", "state")
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "close_leads.json"), "w") as fh:
        json.dump(created, fh, indent=2)
    ok = sum(1 for v in created.values() if v)
    sys.stderr.write("\nWROTE state/close_leads.json ({} of {} created)\n".format(ok, len(payloads)))


if __name__ == "__main__":
    main()
