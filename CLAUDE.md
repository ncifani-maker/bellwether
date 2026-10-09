# Bellwether — project context

One pipeline from a brand brief to verified contacts loaded into Close, with approved copy armed and the send
left to Nicole. Read `PRD.md` first: it is the source of truth for scope. `CHANGELOG.md` records every
decision with who made it and why, so a later session doesn't relitigate it. Read both before changing
anything.

> Automate everything up to the inbox. The human owns the inbox.

## Operating rules
- **Four gates, all Nicole's:** seeds, shortlist, contacts, copy. Then the send, which is hers alone. You may
  draft and arm; you never fire. End every stage with:
  `→ Ready for review. Reply: APPROVE to proceed, REVISE [note] to adjust, NEXT to move to the next stage.`
- **No unverified address enters Close.** Contacts come from the target's own published pages or Hunter,
  role and business addresses only, every one verified. No guessed addresses, no captcha-gated sources.
  On a site run by one person, that person's address on the site's own domain counts as the business
  contact (CHANGELOG D14). Still verified, still never guessed.
- **Every brand is a brief folder**, `briefs/<slug>/`, created from `briefs/_template/`. No script, skill,
  config or template is named after a company, and no script refers to a brand by name (CHANGELOG D4).
- **A published email is captured at research time** (CHANGELOG D18): when `site_profile.py` finds an
  address on a site's own pages, it goes in the local workbook's `published email (unverified)` column.
  Found is not verified; verification still happens at the contact step.
- **No email address goes to GitHub, ever.** Contacts live in `data/contacts.csv`, which is gitignored and
  stays on this Mac. Spreadsheets stay local too. A pre-commit hook in `.githooks/` refuses any commit that
  adds either (CHANGELOG D16). It is on via `git config core.hooksPath .githooks`; run that again after
  any fresh clone, because git does not carry the setting.
- **Every paid call is checked against `config/budgets.json` before it spends** and logged to
  `data/api-usage.csv` after. A command that stops with exit code 3 is asking Nicole, not failing.
- **Keys:** one file, `../.env` (the nac-worldwide root, mode 600), read through `scripts/_keys.py`. Never
  printed, never copied into the repo, never passed on a command line.
- **Predecessors are read-only** (CHANGELOG D2). `../bellwether-1.0/` and
  `~/Desktop/serp-tracker/close-demo/` are reference. Copy from them; never edit or delete in them.
- **The SERP Tracker is never modified from here.** It is the client-facing view (PRD §9).

## Layout
```
briefs/_template/   brief.md, seeds.csv, relationships.csv, voice.md, donors.json
briefs/<slug>/      one per brand (or per prospecting list, see CHANGELOG)
config/budgets.json spend caps
scripts/            pipeline scripts + _keys.py, _budget.py, _brief.py
data/               api-usage.csv (the ledger), contacts.csv (gitignored: PII), opportunities, results
outputs/<slug>/     per-run outputs by slate
docs/               method docs carried forward
vendor/youtube-scout/  pinned upstream; local patches in patches/
```

## Commands (`.claude/skills/`, paths relative to the skill so a folder rename can't break them)
| Command | Stage |
| --- | --- |
| `/import-seeds <file> <slug>` | 1: a seed spreadsheet (.xlsx/.csv) into `briefs/<slug>/seeds.csv`. Free. |
| `/run-seeds <slug>` | 2a + 3: scan approved seeds, keep reviews, tier sites, capture published emails |
| `/fetch-emails <csv> <slug>` | 4: contacts for the team's curated list, handed back in their own CSV |
| `/api-check` | Keys present, valid, what's left. Free. |
| `/serp-scan <slug>` | 2a: approved seeds → candidate partner domains (SerpAPI, capped) |
| `/yt-scan <slug> "<topic>"` | 2b: scout → geo → donor trail → farm flag |
| `/find-contacts` | 4: published first, Hunter second, verify always |
| `/scout <topic>` | raw youtube-scout, no screens |

Not built yet: `/seed-list`, `/score`, `/crm-sync`, `/draft-copy` (PRD §12, Phases 1–4).

## Status
Phase 0 (scaffold) done 2026-10-06. Next: Phase 1, brand-neutral schema and the Close.com replay (PRD §11).
