#!/usr/bin/env python
"""close-demo - generate a personalized, brand-voice opener ({{hook}}) per lead.

For each contact (skipping gaps), asks Claude for ONE warm, specific opening line
in Close's voice (friendly/approachable/personable — see skills/close-brand-voice),
tailored to that target's motion:
  * editorial-outreach -> reference the specific article/roundup they published
  * referral-partner   -> name the complementarity, founder-to-founder

Writes the line into a new `hook` column in output/contacts.csv (preserving any
leading editor comment line). Reads ANTHROPIC_API_KEY from keys.txt / env.
Uses the Anthropic account — generating 29 short lines is cheap, but it's billed.
"""
import os
import sys
import csv
import json

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(HERE, "..", "output")
ENDPOINT = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

SYSTEM = (
    "You write the opening line of a cold outreach email for Close (close.com), a sales CRM with built-in "
    "calling, SMS, and email. Voice: friendly, approachable, personable - a warm, helpful real person, never "
    "a brand or corporate. Benefit-first, plain words, active voice. Banned words: leverage, synergy, "
    "holistic, best-in-class, revolutionary, game-changing, solutions. "
    "Write ONE opening line, under 25 words, specific and true to THIS recipient and the context given. "
    "Do NOT greet ('Hi X'), do NOT hard-pitch Close's features, no exclamation points. "
    "Return ONLY the line - no quotes, no preamble."
)


def load_key():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
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
                if key.strip() == "ANTHROPIC_API_KEY":
                    return val.strip().strip('"').strip("'")
    return ""


KEY = load_key()


def read_rows(path):
    with open(path) as fh:
        raw = fh.readlines()
    comments = [ln for ln in raw if ln.lstrip().startswith("#")]
    body = [ln for ln in raw if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(body)
    return comments, reader.fieldnames, list(reader)


def claude(user):
    headers = {"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {"model": MODEL, "max_tokens": 120, "system": SYSTEM,
            "messages": [{"role": "user", "content": user}]}
    r = requests.post(ENDPOINT, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    return " ".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()


def main():
    if not KEY:
        sys.exit("ANTHROPIC_API_KEY not found in env or keys.txt")
    opps = {r["domain"]: r for r in read_rows(os.path.join(OUT, "opportunities.csv"))[2]}
    comments, fields, rows = read_rows(os.path.join(OUT, "contacts.csv"))
    if "hook" not in fields:
        fields = fields + ["hook"]

    for c in rows:
        email = (c.get("email") or "").strip()
        status = (c.get("sequence_status") or "").strip()
        if not email or status.startswith("blocked") or status.startswith("rejected"):
            c["hook"] = c.get("hook", "")
            continue
        domain = (c.get("opportunity_domain") or "").strip()
        o = opps.get(domain, {})
        name = (c.get("name") or "there").strip() or "there"
        motion = (c.get("motion") or "").strip()
        if motion == "referral-partner":
            user = (
                "Recipient: {name} ({role}) at {domain}. What they do / context: {note}. "
                "Write a warm, founder-to-founder opener that names the complementarity between {domain} and "
                "Close - their users need a CRM/outbound engine to act on what {domain} does; we're not a "
                "competitor."
            ).format(name=name, role=c.get("role", ""), domain=domain, note=o.get("relevance_note", ""))
        else:
            user = (
                "Recipient: {name} ({role}) at {domain}. They published a piece on '{kw}': {url}. "
                "Context: {note}. Write a warm opener that references their specific piece and gently sets up "
                "(without pitching features yet) that Close could fit."
            ).format(name=name, role=c.get("role", ""), domain=domain, kw=o.get("seed_keyword", ""),
                     url=o.get("ranking_url", ""), note=o.get("relevance_note", ""))
        try:
            c["hook"] = claude(user)
        except Exception as exc:
            c["hook"] = ""
            sys.stderr.write("FAILED {}: {}\n".format(domain, exc))
            continue
        sys.stderr.write("[{}] {}\n  {}\n".format(motion, domain, c["hook"]))

    with open(os.path.join(OUT, "contacts.csv"), "w", newline="") as fh:
        for ln in comments:
            fh.write(ln if ln.endswith("\n") else ln + "\n")
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for c in rows:
            w.writerow({k: c.get(k, "") for k in fields})

    done = sum(1 for c in rows if c.get("hook"))
    with open(os.path.join(HERE, "..", "state", "hooks.json"), "w") as fh:
        json.dump({c.get("opportunity_domain"): c.get("hook", "") for c in rows}, fh, indent=2)
    sys.stderr.write("\nWROTE {} hooks into output/contacts.csv\n".format(done))


if __name__ == "__main__":
    main()
