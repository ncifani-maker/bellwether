---
name: import-seeds
description: "Pull a seed list spreadsheet into a Bellwether brief. Reads a downloaded .xlsx or .csv (query / keyword columns, plus brand, category and a completion-date column if present) and writes briefs/<slug>/seeds.csv, the file every scan reads. Re-importing an updated sheet never undoes a decision: existing seeds keep their status. Use when the user says 'import seeds', 'pull the seed list', or hands over a seed spreadsheet. Free: no API calls."
argument-hint: "<file.xlsx|file.csv> <brief-slug> [--hold] [--dry-run]"
allowed-tools: Bash, Read
user-invocable: true
---

# /import-seeds

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/import_seeds.py" "<file>" <slug> --dry-run
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/import_seeds.py" "<file>" <slug>
```

Always dry-run first and show the user what would change, then write.

**Where the file comes from.** The seed list lives in a spreadsheet. Ask for it as a downloaded
.xlsx or .csv (in Google Sheets: File → Download). The Google Sheets connector has been failing to
connect, so the command reads a file rather than the live sheet.

**What it reads, loosely matched.** Any column named query, keyword or seed (one seed per filled
cell; the first is the `singular` form, the second `plural`). `brand` and `category` are carried
onto each seed. A date in a column whose name contains "complet" or "done" marks that row done.

**Statuses.** New seeds come in `approved`: importing her own sheet is the approval. `--hold` brings
them in as `proposed`. Seeds already in the brief keep their status and note, so a run, a hold or a
retirement is never undone by pulling the sheet again. Seeds missing from the sheet are kept, never
deleted. A brief that doesn't exist yet is created from `briefs/_template/`; say that `brief.md`
needs filling before outreach.

The source file is only read. Report: seeds in the sheet, how many are new, how many already known,
and the next step, `/run-seeds <slug> --dry-run`.
