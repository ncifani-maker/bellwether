#!/usr/bin/env python3
"""
_budget.py — spend caps and the usage ledger, shared by every paid command.

Three checks, in order, before anything is spent (config/budgets.json):

  reserve        never spend below this many units left on the account, so the
                 SERP Tracker's client rank checks keep working
  monthly cap    Bellwether's own share per calendar month, counted from
                 data/api-usage.csv
  confirm_above  a larger run stops and prints the plan (exit code 3) instead of
                 spending; re-run with --yes once Nicole has approved it

The ledger is Bellwether's own count, not the provider's. The provider's number
is the truth for what is left; the ledger is the truth for what Bellwether spent,
which is what the monthly cap limits.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # bellwether/
CONFIG = ROOT / "config" / "budgets.json"
LEDGER = ROOT / "data" / "api-usage.csv"
FIELDS = ["date", "provider", "units", "unit_type", "command", "brand", "slate", "note"]

OK, REFUSE, CONFIRM = 0, 2, 3


def budgets() -> dict:
    try:
        cfg = json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def _provider_cfg(provider: str) -> dict:
    return {k: v for k, v in budgets().get(provider, {}).items() if not k.startswith("_")}


def month_used(provider: str, month: str = None) -> int:
    """Units this calendar month, from Bellwether's own ledger."""
    month = month or date.today().strftime("%Y-%m")
    if not LEDGER.exists():
        return 0
    total = 0
    with LEDGER.open() as fh:
        for row in csv.DictReader(fh):
            if row.get("provider") == provider and (row.get("date") or "").startswith(month):
                try:
                    total += int(float(row.get("units") or 0))
                except ValueError:
                    continue
    return total


def log(provider, units, unit_type, command, brand="", slate="", note=""):
    """Append actual spend. Called after the calls happen, with what really ran."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    new = not LEDGER.exists()
    with LEDGER.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        writer.writerow({
            "date": date.today().isoformat(),
            "provider": provider,
            "units": units,
            "unit_type": unit_type,
            "command": command,
            "brand": brand,
            "slate": slate,
            "note": note,
        })


def gate(provider, planned, remaining=None, yes=False, unit="searches"):
    """-> (code, lines). code is OK, REFUSE or CONFIRM; lines explain why.

    `remaining` is what the provider says is left on the account (None if the
    provider cannot report it, in which case the reserve check is skipped).
    """
    cfg = _provider_cfg(provider)
    used = month_used(provider)
    cap = next((v for k, v in cfg.items() if k.endswith("_cap")), None)
    reserve = cfg.get("reserve")
    confirm_above = cfg.get("confirm_above")
    lines = []

    if remaining is not None:
        lines.append("account: {:,} {} left".format(remaining, unit))
    if cap is not None:
        lines.append("bellwether this month: {:,} of {:,} {} used".format(used, cap, unit))
    lines.append("this run: {:,} {}".format(planned, unit))

    if remaining is not None and reserve is not None and remaining - planned < reserve:
        lines.append(
            "REFUSED: would leave {:,} on the account, below the reserve of {:,} kept for the "
            "SERP Tracker's client rank checks. Cut the run (fewer seeds, or --depth 10), or "
            "raise 'reserve' in config/budgets.json.".format(remaining - planned, reserve)
        )
        return REFUSE, lines

    if cap is not None and used + planned > cap:
        lines.append(
            "REFUSED: {:,} + {:,} is over this month's cap of {:,}. Raise the cap in "
            "config/budgets.json, or wait for the month to roll.".format(used, planned, cap)
        )
        return REFUSE, lines

    if confirm_above is not None and planned > confirm_above and not yes:
        lines.append(
            "STOPPED before spending: {:,} {} is over the confirm threshold of {:,}. "
            "Nothing has been spent. Re-run with --yes to go ahead.".format(planned, unit, confirm_above)
        )
        return CONFIRM, lines

    return OK, lines
