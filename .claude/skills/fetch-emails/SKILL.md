---
name: fetch-emails
description: "Find and verify contacts for the sites marked yes in a brief's review-sites.csv `shortlist` column (or a team's curated CSV), and fill email and email status in place (or hand back their CSV with the columns added, rows in the same order). Published addresses on the site come first (free), Hunter search second, Hunter verification always. Use when the user says 'fetch the emails', 'get contacts for the list', or sends back a curated sites CSV."
argument-hint: "<brief-slug> [<team's curated .csv>]"
allowed-tools: Bash, Read
user-invocable: true
disable-model-invocation: true
---

# /fetch-emails

Three steps. Dry-run first, always.

**Which list.** Just a slug (`/fetch-emails braise`): the brief's own `briefs/<slug>/review-sites.csv`,
and only the rows marked yes in its `shortlist` column (D26). If none are marked, say so and stop: the
shortlist is Nicole's call. The emails are filled into that same file. With a team's CSV as well: that
CSV, all rows, and a "(with emails)" copy comes back, as before.

A site whose contact another brief already verified is reused, with no Hunter spend.

**On a demo brief** (one `/reset-demo` can reset, such as Braise), only saved contacts are filled in:
this brief's own, and contacts reused from other briefs. A site with no saved contact is listed and
skipped. Nothing is fetched and nothing spent, so skip the dry run and go straight to steps 2 and 3.
`--live` looks the rest up for real, before a talk (D27).

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/find_contacts.py" --brand <slug> --from-sites "<csv>" --dry-run
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/find_contacts.py" --brand <slug> --from-sites "<csv>"
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/emails_into_sheet.py" "<csv>" --brand <slug>
```

1. **Dry run.** Reads every site's own pages (free) and shows how many publish an address and how
   many need a Hunter search, against the budget.
2. **The run.** Published addresses first, a Hunter search only for the rest, in the list's order,
   and every address verified. Exit 3 means it is over the confirm threshold: ask, then `--yes`.
   If the monthly search cap is hit, the rest are queued as "waiting", not dropped.
3. **Back into their sheet.** Writes `<name> (with emails).csv` to the brief's folder, `briefs/<slug>/` (D25):
   same rows, same order, original columns untouched, plus `email` and
   `email status`. Only verified or accept-all addresses are filled; bounced ones are left blank on
   purpose. Gitignored, and the script checks that before writing. Tell Nicole the full path.
   If their sheet already has an `email` column (a working copy from an earlier pass), it is filled
   in place: blanks only, never over the team's own entries, and the status refreshed only where it
   is still one of ours. Point `--status-column` at their status column if it has another name;
   check which column actually holds statuses before assuming.

**The contact rule** (`CLAUDE.md`): the site's own published pages or Hunter; role or business
addresses, or the owner's address on a one-person site's own domain (D14); every address verified;
never guessed. Addresses live in `data/contacts.csv` and the "(with emails)" copy, both local only.
Never commit or push them (D16); the pre-commit hook refuses anyway.

**In the reply, keep addresses masked** (`h***@domain.com`). Report: ready to send, to decide, not
usable, waiting, Hunter spend, and where the "(with emails)" file is.

For YouTube creators rather than review sites, use `/find-contacts`.
