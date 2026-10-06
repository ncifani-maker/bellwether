#!/usr/bin/env python
"""close-demo - keyword validation via DataForSEO.

Validates the seed keywords with REAL data instead of judgment alone:
  * Google search volume + competition + CPC  (Keywords Data / Google Ads)
  * Keyword difficulty 0-100                   (DataForSEO Labs)

Reads the 15 seeds from output/seeds.csv and writes output/keyword_validation.csv.
Credentials (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD) come from keys.txt / env -
HTTP Basic auth, never passed on the CLI. DataForSEO bills per request (tiny for
15 keywords - two live calls), so it runs against Nicole's account.
"""
import os
import sys
import csv
import json

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# Optional CLI arg: a client output dir containing seeds.csv (default: close-demo's own).
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "..", "output")
BASE = "https://api.dataforseo.com/v3"
LOCATION_CODE = 2840   # United States
LANGUAGE_CODE = "en"


def load_cred(name):
    if os.environ.get(name):
        return os.environ[name]
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
                if key.strip() == name:
                    return val.strip().strip('"').strip("'")
    return ""


LOGIN = load_cred("DATAFORSEO_LOGIN")
PASSWORD = load_cred("DATAFORSEO_PASSWORD")


def read_seeds():
    with open(os.path.join(OUT, "seeds.csv")) as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return [{"keyword": r["keyword"], "intent": r.get("intent", "")}
            for r in csv.DictReader(lines)
            if r.get("keyword") and r.get("status", "").strip().lower() != "retired"]


def post(endpoint, keywords):
    payload = [{"keywords": keywords, "location_code": LOCATION_CODE, "language_code": LANGUAGE_CODE}]
    try:
        resp = requests.post(BASE + endpoint, auth=(LOGIN, PASSWORD), json=payload, timeout=120)
    except requests.RequestException as exc:
        sys.stderr.write("ERROR {}: {}\n".format(endpoint, exc))
        return [], {"error": str(exc)}
    if resp.status_code != 200:
        sys.stderr.write("ERROR {}: HTTP {} - endpoint may not be on this plan. {}\n".format(
            endpoint, resp.status_code, resp.text[:160]))
        return [], {"http_status": resp.status_code, "body": resp.text[:300]}
    data = resp.json()
    if data.get("status_code") != 20000:
        sys.stderr.write("WARN {}: {} {}\n".format(endpoint, data.get("status_code"), data.get("status_message")))
    items = []
    for task in data.get("tasks") or []:
        if task.get("status_code") != 20000:
            sys.stderr.write("WARN task: {} {}\n".format(task.get("status_code"), task.get("status_message")))
        items.extend(task.get("result") or [])
    return items, data


def main():
    if not (LOGIN and PASSWORD):
        sys.exit("DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD not found in env or keys.txt")
    seeds = read_seeds()
    keywords = [s["keyword"] for s in seeds]

    vol_items, vol_raw = post("/keywords_data/google_ads/search_volume/live", keywords)
    vol = {i.get("keyword", "").lower(): i for i in vol_items}

    diff_items, diff_raw = post("/dataforseo_labs/google/bulk_keyword_difficulty/live", keywords)
    diff = {i.get("keyword", "").lower(): i.get("keyword_difficulty") for i in diff_items}

    rows = []
    for s in seeds:
        kw = s["keyword"]
        v = vol.get(kw.lower(), {})
        rows.append({
            "keyword": kw,
            "intent_bucket": s["intent"],
            "search_volume": v.get("search_volume"),
            "competition": v.get("competition"),
            "competition_index": v.get("competition_index"),
            "cpc": v.get("cpc"),
            "keyword_difficulty": diff.get(kw.lower()),
        })

    fields = ["keyword", "intent_bucket", "search_volume", "competition",
              "competition_index", "cpc", "keyword_difficulty"]
    with open(os.path.join(OUT, "keyword_validation.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    state_dir = OUT if len(sys.argv) > 1 else os.path.join(HERE, "..", "state")
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, "dataforseo_raw.json"), "w") as fh:
        json.dump({"search_volume": vol_raw, "difficulty": diff_raw}, fh, indent=2)

    sys.stderr.write("\nWROTE output/keyword_validation.csv ({} keywords)\n".format(len(rows)))
    for r in sorted(rows, key=lambda x: (x["search_volume"] or 0), reverse=True):
        sys.stderr.write("  {:>7}  KD={:<5} {}\n".format(
            r["search_volume"] if r["search_volume"] is not None else "n/a",
            r["keyword_difficulty"] if r["keyword_difficulty"] is not None else "n/a",
            r["keyword"]))


if __name__ == "__main__":
    main()
