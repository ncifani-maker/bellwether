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
  address on a site's own pages, it goes in the `email` column of the brief's `review-sites.csv`, with
  `email status` "published on site, not yet verified". Found is not verified; `/fetch-emails` verifies it
  and updates the same two columns.
- **One folder per brand, and one results file** (CHANGELOG D25). Everything for a brand lives in
  `briefs/<slug>/`: `brief.md`, `snowball.csv`, `seeds.csv` and `review-sites.csv`, with the commands' own
  files in `briefs/<slug>/raw/`. `review-sites.csv` is a living file: a run adds and updates rows, and
  never touches a column a person added or a verified email. All CSV, not xlsx (D24). What every file and
  column means: `docs/brief-folder.md`.
- **No email address goes to GitHub, ever.** Contacts live in `data/contacts.csv`, which is gitignored and
  stays on this Mac. Spreadsheets stay local too. A pre-commit hook in `.githooks/` refuses any commit that
  adds either (CHANGELOG D16). It is on via `git config core.hooksPath .githooks`; run that again after
  any fresh clone, because git does not carry the setting.
- **Nothing goes to Downloads** (CHANGELOG D21, D25): files handed to Nicole, such as the team's CSV with
  emails filled in, go in the brief's folder. A file holding addresses must be gitignored
  (`*with emails*.csv` and `briefs/*/review-sites.csv` are); `emails_into_sheet.py` checks with git before
  writing.
- **Every paid call is checked against `config/budgets.json` before it spends** and logged to
  `data/api-usage.csv` after. A command that stops with exit code 3 is asking Nicole, not failing.
- **A demo brief replays; it never goes live on stage** (CHANGELOG D27). A brief with
  `raw/seeds.baseline.csv` (Braise) is a demo brief. Its commands use saved searches, site profiles,
  reads and contacts, take seconds, and spend nothing; what isn't saved is listed and left out (exit 4
  when nothing is). `--live` goes live, for preparing before a talk. On a demo brief skip dry runs and
  keep answers short.
- **Keys:** one file, `../.env` (the nac-worldwide root, mode 600), read through `scripts/_keys.py`. Never
  printed, never copied into the repo, never passed on a command line.
- **Predecessors are read-only** (CHANGELOG D2). `../_archive/bellwether-1.0/` and
  `~/Desktop/serp-tracker/close-demo/` are reference. Copy from them; never edit or delete in them.
- **The SERP Tracker is never modified from here.** It is the client-facing view (PRD §9).

## Layout
```
briefs/_template/   brief.md, seeds.csv, relationships.csv, voice.md, donors.json
briefs/<slug>/      one per brand (or prospecting list): brief.md, snowball.csv, seeds.csv,
                    review-sites.csv (local: emails), raw/ (the commands' own files)
config/budgets.json spend caps
scripts/            pipeline scripts + _keys.py, _budget.py, _brief.py
data/               api-usage.csv (the ledger), contacts.csv (gitignored: PII), opportunities, results
docs/               method docs carried forward
talk/               the partner-discovery talk: walkthrough.md (on screen), speaker-notes.md
vendor/youtube-scout/  pinned upstream; local patches in patches/
```

## Commands (`.claude/skills/`, paths relative to the skill so a folder rename can't break them)
| Command | Stage |
| --- | --- |
| `/create-seeds <slug>` | 1: draft a seed list (category or brand-review) as `proposed`, optional volume/CPC, record approvals and retirements |
| `/snowball <slug> [--sites <csv>] [--refresh]` | 1: seed brands from what the brief's review sites already review (sitemaps, free) → `snowball.csv`. Reads `starting-sites.csv` if present, else `review-sites.csv`; reuses a read for 24 h; saves only the picks Nicole approves, to `seeds.csv` |
| `/reset-demo <slug>` | puts a demo brief's seeds back to its baseline after a rehearsal. Only briefs with `raw/seeds.baseline.csv` (Braise) |
| `/import-seeds <file> <slug>` | 1: a seed spreadsheet (.xlsx/.csv) into `briefs/<slug>/seeds.csv`. Free. |
| `/run-seeds <slug>` | 2a + 3: scan approved seeds, keep reviews, tier sites, capture published emails, check AI crawler access → `review-sites.csv` |
| `/fetch-emails <slug> [<csv>]` | 4: contacts for the sites marked yes in `review-sites.csv`'s `shortlist`, filled in place (or a team's CSV, handed back as a copy). Reuses contacts other briefs verified |
| `/api-check` | Keys present, valid, what's left. Free. |
| `/serp-scan <slug>` | 2a: approved seeds → candidate partner domains (SerpAPI, capped) |
| `/yt-scan <slug> "<topic>"` | 2b: scout → geo → donor trail → farm flag |
| `/find-contacts` | 4: published first, Hunter second, verify always |
| `/scout <topic>` | raw youtube-scout, no screens |

Not built yet: `/score`, `/crm-sync`, `/draft-copy` (PRD §12, Phases 1–4).

## Status
Phase 0 (scaffold) done 2026-10-06. Next: Phase 1, brand-neutral schema and the Close.com replay (PRD §11).
