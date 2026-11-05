---
name: run-seeds
description: "Run a Bellwether brief's approved seeds through to a tiered list of review sites: SerpAPI scan (budget-gated), keep only reviews and comparisons, then tier each site as creator blog, niche review site, media or check-by-hand, capturing any email the site publishes. Use when the user says 'run the seeds', 'run the seed list', or wants review sites for a brief."
argument-hint: "<brief-slug> [--limit N] [--depth 10] [--dry-run] [--skip-scan] [--live]"
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

**A demo brief replays instead of going live (D27).** A demo brief is one `/reset-demo` can reset
(Braise). Seeds already searched come from the saved results, and sites already profiled come from
their saved profiles: 0 searches, no site visits, done in under a second. Skip the dry run there: the
run itself can't spend. Go straight to the run and a short answer. A seed or site with nothing saved
is listed and left out. Exit 4 means none of the approved seeds had saved results. `--live` runs it for
real, and that is for preparing before a talk, never on stage.

| Flag | Meaning |
|---|---|
| `--limit N` | Only the first N approved seeds |
| `--depth 10` | Results per seed. 10 = page 1 = 1 search per seed (default) |
| `--slate 2026-10` | Output folder, defaults to this month |
| `--skip-scan` | No SerpAPI: rebuild the review list and tiers from results already on disk |
| `--yes` | Approve a scan over the confirm threshold |
| `--live` | On a demo brief: search and visit sites for real instead of replaying |

**Gates, never worked around.** Exit 3: the scan is bigger than the confirm threshold in
`config/budgets.json`; show the plan and ask, and only then re-run with `--yes`. Exit 2: refused
because it would breach the monthly cap or the SerpAPI reserve kept for the tracker; report the
numbers and the options (fewer seeds, wait for the reset, or Nicole changes the budget). Never edit
`budgets.json` to get a run through.

**Output: one file,** `briefs/<slug>/review-sites.csv`, beside the brief and the seed list (D25). One row
per review site: the tier, evidence, brands reviewed, best rank, AI crawler access, and `email` /
`email status` last. Any address a site publishes is in `email`, marked "published on site, not yet
verified". It's a living file: each run adds and updates rows, and never touches a column a person
added or an email `/fetch-emails` verified. Gitignored, local (D16). The detail (every result kept,
every skip with its reason) is in `briefs/<slug>/raw/`. What everything means: `docs/brief-folder.md`.

Report the counts per tier, how many publish an email, how many can be read by ChatGPT and Claude
search (`ai_search`; say how many are `no` or edge-blocked), and the next step: the team curates
"For the team", then `/fetch-emails` on the CSV they export. Keep any email address masked
(`h***@domain.com`) in the reply.
