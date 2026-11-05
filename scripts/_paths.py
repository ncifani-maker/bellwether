"""
_paths.py — where a brief's files live: one folder per brand (CHANGELOG D25).

A talk, or a person, shouldn't have to jump between folders. Everything a brand
needs, and everything the commands make for it, sits with its brief:

  briefs/<slug>/brief.md            1. the brief: what it sells, categories, comparable brands
  briefs/<slug>/snowball.csv        2. /snowball: brands the review sites also review
  briefs/<slug>/seeds.csv           3. the seed list /run-seeds searches
  briefs/<slug>/review-sites.csv    4. /run-seeds: one row per review site, everything in one file.
                                       A living file: each run adds and updates rows, and never
                                       touches columns a person added or a verified email.
                                       Gitignored: it holds emails.
  briefs/<slug>/starting-sites.csv  optional: sites /snowball starts from, e.g. a partner export
  briefs/<slug>/raw/                what the commands keep for themselves; no need to open
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def brief_dir(slug):
    return ROOT / "briefs" / slug


def raw_dir(slug):
    d = brief_dir(slug) / "raw"
    d.mkdir(parents=True, exist_ok=True)
    return d


def review_sites(slug):
    return brief_dir(slug) / "review-sites.csv"


def is_demo(slug):
    """A demo brief is one /reset-demo can reset: it keeps raw/seeds.baseline.csv
    (CHANGELOG D23). Its commands replay what's saved instead of going live, so a
    talk gets results in seconds and spends nothing; --live goes live (D27). The
    marker is a file, not a name, so no script refers to a brand (D4)."""
    d = brief_dir(slug)
    return (d / "raw" / "seeds.baseline.csv").exists() or (d / "seeds.baseline.csv").exists()


DEMO_LINE = "demo brief: replaying what's saved, nothing fetched, nothing spent (--live for a fresh run)"
