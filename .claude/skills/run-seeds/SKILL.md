---
name: run-seeds
description: "Run a Bellwether brief's approved seeds through to a tiered list of review sites: SerpAPI scan (budget-gated), keep only reviews and comparisons, then tier each site as creator blog, niche review site, media or check-by-hand, capturing any email the site publishes. Use when the user says 'run the seeds', 'run the seed list', or wants review sites for a brief."
argument-hint: "<brief-slug> [--limit N] [--depth 10] [--dry-run] [--skip-scan]"
allowed-tools: Bash, Read
user-invocable: true
disable-model-invocation: true
---

# /run-seeds

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/run_seeds.py" <slug> --dry-run
```

Always dry-run first: it prints the searches the scan would spend and what SerpAPI has left,
spending nothing. Then the real run.

| Flag | Meaning |
|---|---|
| `--limit N` | Only the first N approved seeds |
| `--depth 10` | Results per seed. 10 = page 1 = 1 search per seed (default) |
| `--slate 2026-10` | Output folder, defaults to this month |
| `--skip-scan` | No SerpAPI: rebuild the review list and tiers from results already on disk |
| `--yes` | Approve a scan over the confirm threshold |

**Gates, never worked around.** Exit 3: the scan is bigger than the confirm threshold in
`config/budgets.json`; show the plan and ask, and only then re-run with `--yes`. Exit 2: refused
because it would breach the monthly cap or the SerpAPI reserve kept for the tracker; report the
numbers and the options (fewer seeds, wait for the reset, or Nicole changes the budget). Never edit
`budgets.json` to get a run through.

**Output.** `outputs/<slug>/<slate>/creator-shortlist.xlsx` is the team's file: For the team,
Check by hand, Media set aside, with each row's evidence and any published email captured as
`published email (unverified)`. It stays local; spreadsheets never go to GitHub (CHANGELOG D16).
`review-sites.xlsx` holds everything kept and every skip with its reason.

Report the counts per tier, how many publish an email, and the next step: the team curates
"For the team", then `/fetch-emails` on the CSV they export. Keep any email address masked
(`h***@domain.com`) in the reply.
