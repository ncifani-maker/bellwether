#!/usr/bin/env python3
"""
api_check.py — is every key present, valid, and how much is left?

Runs before a scan, or whenever something 401s. Each provider is checked with
its own free account endpoint, so this costs nothing:

  YouTube      videos.list on one known id      1 unit of 10,000/day
  SerpAPI      /account                         free, reports searches left
  Hunter       /account                         free, reports credits left
  DataForSEO   /appendix/user_data              free, reports balance
  Anthropic    /v1/models                       free, no tokens
  OpenAI       /v1/models                       free, no tokens
  Close        /me/                             free (not used by Bellwether)

Keys are read via _keys.py and never printed — the report shows where each key
came from, not what it is.

Usage:
  python3 scripts/api_check.py                 # everything
  python3 scripts/api_check.py --only serpapi,hunter
  python3 scripts/api_check.py --json
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _keys import CANONICAL, get, source_of  # noqa: E402

TIMEOUT = 20
# A public video id, used only to prove the key answers. 1 quota unit.
YT_PROBE_ID = "dQw4w9WgXcQ"


def fetch(url, headers=None, data=None):
    """-> (status, parsed_json_or_text). Never raises on an HTTP error code."""
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.getcode()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        status = exc.code
    except Exception as exc:  # network down, DNS, timeout
        return 0, str(exc)
    try:
        return status, json.loads(body)
    except ValueError:
        return status, body


def money(value):
    try:
        return "${:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return str(value)


def num(value):
    try:
        return "{:,}".format(int(value))
    except (TypeError, ValueError):
        return str(value)


# --- one checker per provider -------------------------------------------------
# Each returns (ok: bool, detail: str). `detail` is what a human needs to decide
# whether to run a scan today.


def check_youtube(key):
    url = "https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode(
        {"part": "id", "id": YT_PROBE_ID, "key": key}
    )
    status, body = fetch(url)
    if status == 200:
        return True, "valid · 10,000 units/day, not queryable (search = 100, donor scan ≈ 4/channel)"
    if isinstance(body, dict):
        err = body.get("error", {})
        reason = (err.get("errors") or [{}])[0].get("reason", "")
        if reason == "quotaExceeded":
            return False, "quota exhausted for today — resets at midnight Pacific"
        return False, "HTTP {} {}".format(status, err.get("message", ""))[:90]
    return False, "HTTP {}".format(status)


def check_serpapi(key):
    url = "https://serpapi.com/account?" + urllib.parse.urlencode({"api_key": key})
    status, body = fetch(url)
    if status == 200 and isinstance(body, dict):
        left = body.get("total_searches_left")
        plan_left = body.get("plan_searches_left")
        used = body.get("this_month_usage")
        plan = body.get("plan_name", "")
        return True, "{} · {} searches left this month ({} used){}".format(
            plan or "plan", num(left if left is not None else plan_left), num(used),
            "" if left is not None else " (plan allowance)",
        )
    return False, "HTTP {}".format(status)


def check_hunter(key):
    url = "https://api.hunter.io/v2/account?" + urllib.parse.urlencode({"api_key": key})
    status, body = fetch(url)
    if status == 200 and isinstance(body, dict):
        data = body.get("data", {})
        plan = data.get("plan_name", "")
        reset = data.get("reset_date", "")
        requests_ = data.get("requests", {})
        searches = requests_.get("searches", {})
        verifs = requests_.get("verifications", {})
        credits = data.get("credits")
        if searches or verifs:
            detail = "{} · searches {}/{} · verifications {}/{}".format(
                plan or "plan",
                num(searches.get("used", 0)), num(searches.get("available", 0)),
                num(verifs.get("used", 0)), num(verifs.get("available", 0)),
            )
        else:
            detail = "{} · {} credits".format(plan or "plan", num(credits))
        if reset:
            detail += " · resets {}".format(reset)
        return True, detail
    if isinstance(body, dict) and body.get("errors"):
        return False, "HTTP {} {}".format(status, body["errors"][0].get("details", ""))[:90]
    return False, "HTTP {}".format(status)


def check_dataforseo(login, password):
    token = base64.b64encode("{}:{}".format(login, password).encode()).decode()
    status, body = fetch(
        "https://api.dataforseo.com/v3/appendix/user_data",
        headers={"Authorization": "Basic " + token},
    )
    if status == 200 and isinstance(body, dict):
        tasks = body.get("tasks") or [{}]
        result = (tasks[0].get("result") or [{}])[0]
        balance = (result.get("money") or {}).get("balance")
        # rates.limits is a deep per-endpoint tree; only the scalar minute rate
        # is worth showing, and only when it really is a scalar.
        limits = (result.get("rates") or {}).get("limits") or {}
        detail = "balance {}".format(money(balance))
        minute = limits.get("minute")
        if isinstance(minute, (int, float)):
            detail += " · {} req/min".format(num(minute))
        return True, detail
    return False, "HTTP {}".format(status)


def check_anthropic(key):
    status, body = fetch(
        "https://api.anthropic.com/v1/models?limit=1",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    if status == 200:
        return True, "valid · billed per token (drafting runs in-session, so Bellwether rarely needs it)"
    if isinstance(body, dict):
        return False, "HTTP {} {}".format(status, (body.get("error") or {}).get("message", ""))[:90]
    return False, "HTTP {}".format(status)


def check_openai(key):
    status, body = fetch(
        "https://api.openai.com/v1/models", headers={"Authorization": "Bearer " + key}
    )
    if status == 200:
        return True, "valid · billed per token"
    if isinstance(body, dict):
        return False, "HTTP {} {}".format(status, (body.get("error") or {}).get("message", ""))[:90]
    return False, "HTTP {}".format(status)


def check_close(key):
    token = base64.b64encode("{}:".format(key).encode()).decode()
    status, body = fetch(
        "https://api.close.com/api/v1/me/", headers={"Authorization": "Basic " + token}
    )
    if status == 200 and isinstance(body, dict):
        org = (body.get("organizations") or [{}])[0].get("name", "")
        return True, "valid{}".format(" · " + org if org else "")
    return False, "HTTP {} — key rejected. Close is the CRM in 2.0 (CHANGELOG D3); fresh key pending, Phase 3 waits on it.".format(status)


CHECKS = [
    # slug, label, key names, required by Bellwether, checker
    ("youtube", "YouTube Data v3", ["YOUTUBE_API_KEY"], True, check_youtube),
    ("serpapi", "SerpAPI", ["SERP_API_KEY"], True, check_serpapi),
    ("hunter", "Hunter.io", ["HUNTER_API_KEY"], True, check_hunter),
    ("dataforseo", "DataForSEO", ["DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"], True, check_dataforseo),
    ("anthropic", "Anthropic", ["ANTHROPIC_API_KEY"], False, check_anthropic),
    ("openai", "OpenAI", ["OPENAI_API_KEY"], False, check_openai),
    ("close", "Close", ["CLOSE_API_KEY"], False, check_close),
]


def main():
    ap = argparse.ArgumentParser(description="Check every API key: present, valid, what's left.")
    ap.add_argument("--only", help="comma-separated slugs, e.g. serpapi,hunter")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    wanted = {s.strip().lower() for s in args.only.split(",")} if args.only else None
    rows, failures = [], []

    for slug, label, names, required, checker in CHECKS:
        if wanted and slug not in wanted:
            continue
        values = [get(n) for n in names]
        if not all(values):
            missing = [n for n, v in zip(names, values) if not v]
            rows.append((label, "MISSING", "not in {}: {}".format(CANONICAL.name, ", ".join(missing)), "-"))
            if required:
                failures.append(label)
            continue
        ok, detail = checker(*values)
        rows.append((label, "ok" if ok else "FAIL", detail, source_of(names[0])))
        if not ok and required:
            failures.append(label)

    if args.json:
        print(json.dumps(
            [{"service": r[0], "status": r[1], "detail": r[2], "key_from": r[3]} for r in rows],
            indent=2,
        ))
    else:
        print("keys file: {}\n".format(CANONICAL))
        width = max(len(r[0]) for r in rows) if rows else 10
        for label, status, detail, src in rows:
            print("{:<{w}}  {:<7}  {}".format(label, status, detail, w=width))
        print("\nkey source: {}".format(rows[0][3] if rows else "-"))

    if failures:
        print("\nFAILED: {}".format(", ".join(failures)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
