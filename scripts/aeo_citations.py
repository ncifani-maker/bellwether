#!/usr/bin/env python
"""Which domains do AI answer engines cite for our seed questions? (client-agnostic)

Usage: aeo_citations.py <client_dir> [--engines claude,chatgpt] [--limit N]

The other half of "what's the expected result of a placement here". A Google rank
tells you what a placement wins on the SERP; this tells you whether the domain is
in the citation set an LLM draws from when a buyer asks the same question in
Claude or ChatGPT. A domain cited by both engines is worth materially more than
its Google rank alone suggests.

Writes <client_dir>/llm_citations.json — {domain: {engines:[], queries:[]}} —
which qualify_targets.py joins onto every row.

Raw HTTP (no SDKs) to stay Python 3.7-compatible, mirroring the SERP tracker's
idiom. Keys come from keys.txt / env. COSTS MONEY: 1 call per engine per query.
"""
import os
import sys
import json
import argparse
import collections
from urllib.parse import urlparse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


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
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


ANTHROPIC_KEY = load_cred("ANTHROPIC_API_KEY")
OPENAI_KEY = load_cred("OPENAI_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.5")
TIMEOUT = int(os.environ.get("AI_TIMEOUT", "180"))


def domain_of(url):
    n = urlparse(url or "").netloc.lower()
    return n[4:] if n.startswith("www.") else n


def ask_claude(query):
    """Anthropic Messages API with the standard live web-search tool."""
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": ANTHROPIC_MODEL, "max_tokens": 1500,
              "tools": [{"type": "web_search_20250305", "name": "web_search"}],
              "messages": [{"role": "user", "content": query}]},
        timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    urls = []
    for block in data.get("content") or []:
        for c in (block.get("citations") or []):
            if c.get("url"):
                urls.append(c["url"])
        if block.get("type") == "web_search_tool_result":
            for item in (block.get("content") or []):
                if isinstance(item, dict) and item.get("url"):
                    urls.append(item["url"])
    return urls


def ask_chatgpt(query):
    """OpenAI Responses API with web search; citations arrive as url_citation annotations."""
    r = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": "Bearer " + OPENAI_KEY, "Content-Type": "application/json"},
        json={"model": OPENAI_MODEL, "input": query,
              "tools": [{"type": "web_search", "search_context_size": "high"}]},
        timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    urls = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "url_citation" and node.get("url"):
                urls.append(node["url"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(data)
    return urls


ENGINES = {"claude": ask_claude, "chatgpt": ask_chatgpt}


def read_seeds(d):
    path = os.path.join(d, "seeds.csv")
    import csv
    with open(path) as fh:
        rows = list(csv.DictReader([ln for ln in fh if not ln.lstrip().startswith("#")]))
    return [r["keyword"] for r in rows
            if r.get("keyword") and r.get("status", "").strip().lower() != "retired"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("client_dir")
    ap.add_argument("--engines", default="claude,chatgpt")
    ap.add_argument("--limit", type=int, default=0, help="only the first N seeds (cost control)")
    args = ap.parse_args()
    d = args.client_dir

    engines = [e.strip() for e in args.engines.split(",") if e.strip() in ENGINES]
    if "claude" in engines and not ANTHROPIC_KEY:
        sys.exit("ANTHROPIC_API_KEY not found")
    if "chatgpt" in engines and not OPENAI_KEY:
        sys.exit("OPENAI_API_KEY not found")

    seeds = read_seeds(d)
    if args.limit:
        seeds = seeds[:args.limit]
    sys.stderr.write("{} seeds x {} engines = {} calls\n".format(
        len(seeds), len(engines), len(seeds) * len(engines)))

    cited = collections.defaultdict(lambda: {"engines": set(), "queries": set()})
    for kw in seeds:
        for eng in engines:
            try:
                urls = ENGINES[eng](kw)
            except Exception as exc:
                sys.stderr.write("  [{} / {}] ERROR {}\n".format(kw[:30], eng, str(exc)[:110]))
                continue
            doms = set(domain_of(u) for u in urls if domain_of(u))
            for dom in doms:
                cited[dom]["engines"].add(eng)
                cited[dom]["queries"].add(kw)
            sys.stderr.write("  [{:<32} {:<8}] {} citations, {} domains\n".format(
                kw[:32], eng, len(urls), len(doms)))

    out = {dom: {"engines": sorted(v["engines"]), "queries": sorted(v["queries"])}
           for dom, v in cited.items()}
    path = os.path.join(d, "llm_citations.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=2)

    sys.stderr.write("\nWROTE {} ({} domains cited)\n".format(path, len(out)))
    ranked = sorted(out.items(), key=lambda kv: (-len(kv[1]["engines"]), -len(kv[1]["queries"])))
    sys.stderr.write("\nMost-cited domains:\n")
    for dom, v in ranked[:25]:
        sys.stderr.write("  {:<34} {:<16} {} queries\n".format(
            dom[:34], ",".join(v["engines"]), len(v["queries"])))


if __name__ == "__main__":
    main()
