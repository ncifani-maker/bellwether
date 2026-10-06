#!/usr/bin/env python3
"""
_keys.py — one place to get an API key, for every Bellwether script.

The canonical file is `nac-worldwide/.env`: one file, inside the folder every
project already lives in, readable from any of them. Resolution order:

  1. the process environment          (a key exported for this run wins)
  2. $NAC_KEYS_FILE                   (a deliberate override, e.g. a test key)
  3. <nac-worldwide>/.env             (canonical)
  4. ~/.config/scout/.env             (legacy; the YouTube key used to live here)

Keys are returned, never printed. Scripts pass them to APIs and nowhere else:
not to argv (process listings are world-readable), not to stdout, not into a
report. `mask()` is here for the one case where a human needs to tell two keys
apart in a log.

serp-tracker keeps its own keys.txt and its Render env vars. This file does not
replace them, so a rotated key has to be updated in both places.

Usage:
    from _keys import get, require, as_env
    key = require("SERP_API_KEY")            # raises SystemExit with a fix hint
    login, pw = require("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD")
    env = as_env("YOUTUBE_API_KEY")          # for subprocess(env=...)
"""

from __future__ import annotations

import os
from pathlib import Path

# bellwether/scripts/_keys.py -> bellwether/scripts -> bellwether -> nac-worldwide
NAC_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = NAC_ROOT / ".env"
LEGACY = Path.home() / ".config" / "scout" / ".env"


def _parse(path: Path) -> dict:
    """Read KEY=VALUE lines. Tolerates comments, blanks, quotes and junk lines."""
    out = {}
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and val:
            out.setdefault(key, val)
    return out


def _files() -> list:
    paths = []
    override = os.environ.get("NAC_KEYS_FILE")
    if override:
        paths.append(Path(override).expanduser())
    paths.extend([CANONICAL, LEGACY])
    return paths


_cache = None


def _loaded() -> dict:
    global _cache
    if _cache is None:
        merged = {}
        for path in _files():
            for key, val in _parse(path).items():
                merged.setdefault(key, val)
        _cache = merged
    return _cache


def source_of(name: str) -> str:
    """Where a key came from — for diagnostics. Returns a path or 'environment'."""
    if os.environ.get(name):
        return "environment"
    for path in _files():
        if _parse(path).get(name):
            try:
                return "~/" + path.relative_to(Path.home()).as_posix()
            except ValueError:
                return str(path)
    return "not found"


def get(name: str, default: str = "") -> str:
    """The key, or `default`. Never raises."""
    return os.environ.get(name) or _loaded().get(name) or default


def require(*names: str):
    """One key, or a tuple of them. Exits with a fix hint if any is missing."""
    values = []
    missing = []
    for name in names:
        val = get(name)
        if not val:
            missing.append(name)
        values.append(val)
    if missing:
        raise SystemExit(
            "missing key(s): {}\n"
            "  add them to {}\n"
            "  then check with: python3 bellwether/scripts/api_check.py".format(
                ", ".join(missing), CANONICAL
            )
        )
    return values[0] if len(values) == 1 else tuple(values)


def as_env(*names: str, base: dict = None) -> dict:
    """A copy of the environment with these keys set — for subprocess(env=...).

    Used to hand the YouTube key to the vendored scout.py without writing it
    anywhere or passing it on a command line.
    """
    env = dict(base if base is not None else os.environ)
    for name in names:
        val = get(name)
        if val:
            env[name] = val
    return env


def mask(value: str) -> str:
    """'sk-ant-…9f2c' — enough to tell two keys apart, not enough to use one."""
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return "{}…{}".format(value[:4], value[-4:])


if __name__ == "__main__":
    # Deliberately prints names and sources only — never values.
    print("canonical: {}".format(CANONICAL))
    print("exists:    {}".format(CANONICAL.exists()))
    print()
    for name in sorted(_loaded()):
        print("{:<24} {}".format(name, source_of(name)))
