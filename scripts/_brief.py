#!/usr/bin/env python3
"""
_brief.py — read a brand's economics out of its brief, and price a creator.

CLAUDE.md: criteria, caps and thresholds come from the brief, never from prompt
text, and a run refuses without them. So the numbers live in ONE place, a fenced
json block in the brief marked `<!-- bellwether:economics -->`, sitting right
under the human-readable table it mirrors. Nothing here has a default. A missing
value stops the run and names itself.

Core math (PRD, CLAUDE.md):  CPA = CPM / (10 * signup_rate_pct)

Long-form is judged on projected CPA. Shorts are judged on CPM and get no CPA at
all: no measured Homeaglow sign-up rate exists for a ranking buy, so a CPA there
would be a borrowed number wearing a decimal point. `price()` refuses to produce
one, which is the brief's rule expressed as code rather than as a convention.

Usage:
    from _brief import load_economics, price
    econ = load_economics("homeaglow")            # or a path
    row  = price(econ, "longform", views=180000, rate=2250, scanned=90)
    row["action"]      -> "Negotiate at $1,410"
    row["cpa_median"]  -> 44.64
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / "briefs"
MARKER = "bellwether:economics"
THIN_SCAN = 30  # uploads; below this the median view count is not trustworthy

SHARED_REQUIRED = ["cpa_target", "cpa_ceiling", "flag_above_rate"]
REQUIRED = {
    "cpa": ["cpm_cap", "signup_rate_median_pct", "signup_rate_optimistic_pct", "typical_rate"],
    "cpm": ["cpm_cap", "cpm_stretch", "typical_rate"],
}


class BriefError(Exception):
    """Something the brief has to say and does not."""


def brief_path(brand: str) -> Path:
    """A slug -> briefs/<slug>/brief.md (PRD §6). A path to a .md is used as given."""
    candidate = Path(brand)
    if candidate.suffix == ".md" and candidate.exists():
        return candidate
    path = BRIEFS / brand / "brief.md"
    if not path.exists():
        raise BriefError("no brief at {}. Create it from briefs/_template/.".format(path))
    return path


def load_economics(brand: str) -> dict:
    """Parse the economics block. Raises BriefError with a fix hint."""
    path = brief_path(brand)
    text = path.read_text()
    if MARKER not in text:
        raise BriefError(
            "{} has no '{}' block. Add the fenced json block under Lane economics."
            .format(path.name, MARKER))
    after = text.split(MARKER, 1)[1]
    match = re.search(r"```json\s*(\{.*?\})\s*```", after, re.S)
    if not match:
        raise BriefError("{}: found the marker but no ```json block after it".format(path.name))
    try:
        econ = json.loads(match.group(1))
    except ValueError as exc:
        raise BriefError("{}: the economics block is not valid json ({})".format(path.name, exc))
    econ["_brief"] = str(path.relative_to(ROOT))
    return econ


def placement(econ: dict, name: str) -> dict:
    try:
        return econ["placements"][name]
    except KeyError:
        raise BriefError("{}: no '{}' placement in the economics block"
                         .format(econ.get("_brief", "brief"), name))


def missing(econ: dict, name: str) -> list:
    """Which values this placement still needs. Empty means ready to price."""
    cfg = placement(econ, name)
    judged = cfg.get("judged_on", "cpa")
    gaps = ["{}.{}".format(name, k) for k in REQUIRED.get(judged, REQUIRED["cpa"])
            if cfg.get(k) in (None, "")]
    gaps += [k for k in SHARED_REQUIRED if econ.get(k) in (None, "")]
    return gaps


def require_ready(econ: dict, name: str) -> None:
    gaps = missing(econ, name)
    if gaps:
        raise BriefError(
            "{} has no value for: {}\n"
            "  Fill the Lane economics table and the economics block, then re-run.\n"
            "  Pricing a creator on invented numbers is the one thing this must not do."
            .format(econ.get("_brief", "the brief"), ", ".join(gaps)))


def cpa(cpm: float, signup_rate_pct: float) -> float:
    """CPA = CPM / (10 * sign-up rate %). The whole thesis in one line."""
    if not signup_rate_pct:
        raise BriefError("a sign-up rate of zero has no CPA")
    return cpm / (10.0 * signup_rate_pct)


def cpm_of(rate: float, views: float) -> float:
    if not views:
        raise BriefError("no views: nothing to price against")
    return rate / (views / 1000.0)


def _money(value: float) -> str:
    return "${:,.0f}".format(value)


def _cpm(value: float) -> str:
    """CPMs are small numbers; whole dollars would round $2.50 to $2."""
    return "${:,.2f}".format(value)


def price(econ: dict, name: str, views: float, rate: float = None,
          scanned: int = None, flags: list = None) -> dict:
    """Price one creator for one placement. Returns the row's pricing columns.

    `flags` are reasons a human should look regardless of the numbers (off-ICP,
    farm risk, geography). They force the action to Flag, per the brief.
    """
    require_ready(econ, name)
    cfg = placement(econ, name)
    judged = cfg.get("judged_on", "cpa")
    rate = cfg["typical_rate"] if rate is None else rate
    flags = list(flags or [])

    out = {"placement": name, "judged_on": judged, "views": views, "rate": rate,
           "cpa_median": None, "cpa_optimistic": None, "max_rate": None,
           "confidence": "high", "flags": flags}

    if scanned is not None and scanned < THIN_SCAN:
        out["confidence"] = "low"
        flags.append("thin scan ({} uploads)".format(scanned))
    if not views:
        out["confidence"] = "low"
        flags.append("no view history")
        out["action"] = "Flag: cannot price"
        return out

    out["cpm"] = round(cpm_of(rate, views), 2)
    cap, stretch = cfg["cpm_cap"], cfg.get("cpm_stretch") or cfg["cpm_cap"]

    if judged == "cpa":
        med, opt = cfg["signup_rate_median_pct"], cfg["signup_rate_optimistic_pct"]
        out["cpa_median"] = round(cpa(out["cpm"], med), 2)
        out["cpa_optimistic"] = round(cpa(out["cpm"], opt), 2)
        # The most payable while the MEDIAN case still clears the ceiling, and
        # never above the CPM cap. The conservative of the two, on purpose.
        ceiling_cpm = econ["cpa_ceiling"] * 10.0 * med
        out["max_rate"] = round(min(cap, ceiling_cpm) * views / 1000.0, 2)
        target_cpm = min(cap, econ["cpa_target"] * 10.0 * med)
        target_rate = target_cpm * views / 1000.0

        if rate > econ["flag_above_rate"]:
            flags.append("rate over the consultant-flag threshold")
        if flags:
            out["action"] = "Flag: " + "; ".join(flags)
        elif out["cpa_optimistic"] > econ["cpa_ceiling"]:
            out["action"] = "Decline: optimistic CPA {} over the {} ceiling".format(
                _money(out["cpa_optimistic"]), _money(econ["cpa_ceiling"]))
        elif out["cpa_median"] <= econ["cpa_target"] and out["cpm"] <= cap:
            out["action"] = "Approve at {}".format(_money(rate))
        else:
            out["action"] = "Negotiate at {}".format(_money(target_rate))
            out["target_rate"] = round(target_rate, 2)
    else:
        # Ranking buy. Judged on CPM, and deliberately carries no CPA.
        out["max_rate"] = round(cap * views / 1000.0, 2)
        if rate > econ["flag_above_rate"]:
            flags.append("rate over the consultant-flag threshold")
        if flags:
            out["action"] = "Flag: " + "; ".join(flags)
        elif out["cpm"] <= stretch:
            out["action"] = "Approve, ranking buy at {} CPM".format(_cpm(out["cpm"]))
        elif out["cpm"] <= cap:
            out["action"] = "Negotiate at {} (to a {} CPM)".format(
                _money(stretch * views / 1000.0), _cpm(stretch))
            out["target_rate"] = round(stretch * views / 1000.0, 2)
        else:
            out["action"] = "Decline: {} CPM over the {} cap".format(
                _cpm(out["cpm"]), _cpm(cap))

    out["flags"] = flags
    return out


if __name__ == "__main__":
    import sys
    brand = sys.argv[1] if len(sys.argv) > 1 else "homeaglow"
    econ = load_economics(brand)
    print("brief: {}".format(econ["_brief"]))
    for name in econ.get("placements", {}):
        gaps = missing(econ, name)
        print("  {:<10} judged on {:<4} {}".format(
            name, placement(econ, name).get("judged_on", "cpa"),
            "READY" if not gaps else "missing: " + ", ".join(gaps)))
