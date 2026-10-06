---
name: serp-scan
description: "Bellwether partner discovery, step 1 (web lane). Runs a brand's approved seed keywords through Google via SerpAPI and returns the candidate partner domains — review sites, roundups, blogs, complementary tools — noise-filtered, de-duplicated and ranked by how many seeds each one covers. Use when the user says 'serp scan <brand>', wants to find partner or placement targets for a brand, or asks who ranks for a set of keywords."
argument-hint: "<brand> [--slate 2026-10] [--depth 20] [--keywords \"kw one\" \"kw two\"] [--dry-run]"
allowed-tools: Bash, Read
user-invocable: true
disable-model-invocation: true
---

# /serp-scan

Finds who already ranks in front of a brand's buyers. The script does the work;
your job is to run it, handle the spend gate, and read the result back.

**Never** put an API key on a command line, in a file, or in your reply. The
script reads keys itself from `nac-worldwide/.env`.

## Step 1: Run

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../scripts/serp_scan.py <brand> [flags]
```

Default depth is 20 results per seed, which costs 2 SerpAPI searches per seed.
Use `--dry-run` first whenever the seed count is unknown — it prints the plan and
the budget and spends nothing.

| Flag | Meaning |
|---|---|
| `--slate 2026-10` | Output folder, defaults to this month |
| `--depth 10\|20\|30\|40\|50` | Results per seed, 1 search per 10 |
| `--seeds <path>` | Override the seeds CSV |
| `--keywords "a" "b"` | One-off keywords instead of the seed file |
| `--dry-run` | Plan and budget only |
| `--yes` | Approve a run over the confirm threshold |

## Step 2: Handle the gates

**Exit code 3 — stopped before spending.** The run is bigger than the confirm
threshold in `config/budgets.json`. Nothing was spent. Show Nicole the
planned searches and what's left on the account, and ask whether to go ahead. Only
if she says yes, re-run the identical command with `--yes`.

**Exit code 2 — refused.** Either it would drop below the reserve kept for the
SERP Tracker's client rank checks, or it's over the month's cap. Do not work
around it. Report the numbers and offer the real options: fewer seeds, a smaller
`--depth`, or raising the limit in `config/budgets.json` (her call, not yours).

**"no seeds marked `approved`".** That's the seed gate, working. The seed list is
Nicole's to approve — do not edit `status` to `approved` yourself, and do not
substitute `--keywords` to get around it. Show her the seeds and ask.

## Step 3: Report

The script prints a table and writes `outputs/<brand>/<slate>/serp-domains.csv`.
Relay:

- Domain count, seeds run, searches spent, and what SerpAPI says is left.
- The top rows as printed, in a code block.
- Anything flagged `known` (already in `creators.csv`) or `contacted` (already in
  `outreach.csv`) — an existing partner ranking for a new seed is worth saying out
  loud, not filtering away.
- Any failed or contaminated seeds. A dropped page means that seed's results are
  incomplete, not that the domain list is wrong.
- Two or three observations worth acting on: which seeds were target-rich versus
  which returned only competitors' own pages (a dead-end seed), and any domain
  covering several seeds at once.

Then: `→ Ready for review. Reply: APPROVE to proceed, REVISE [note] to adjust, NEXT to move to the next stage.`

Next stage is scoring. Say so; don't start it.
