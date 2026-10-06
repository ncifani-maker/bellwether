---
name: yt-scan
description: "Bellwether creator discovery, YouTube lane. Runs the whole chain for a brand in one command: youtube-scout topic search, the geography screen, the donor-brand sponsorship scan on full descriptions, and the content-farm flag, then writes a ranked report. Use when the user says 'yt scan <brand> <topic>', wants YouTube creators for a brand or slate, or wants to know which creators a comparable brand rebooks."
argument-hint: "<brand> \"<topic>\" [--max 50] [--length short] [--geo US] [--depth 90] [--study <config.json>] [--dry-run]"
allowed-tools: Bash, Read
user-invocable: true
disable-model-invocation: true
---

# /yt-scan

One command for the whole YouTube chain: scout → geo screen → donor trail → farm
flag → report. It wraps `run_study.py`, so runs are cached and resumable.

Prefer this over calling `/scout` directly for Bellwether work. `/scout` alone
gives a topic workbook with none of the screens, and the two hard rules in
`CLAUDE.md` exist because skipping them produced wrong sponsorship
counts twice.

**Never** print or copy an API key. The script hands the canonical key file to
scout and donor_trail by path.

## Step 1: Run

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../scripts/yt_scan.py <brand> "<topic>" [flags]
```

Several topics can be quoted one after another. `--dry-run` prints the plan and
the estimated quota and spends nothing — use it whenever the topic count or
`--max` is large.

| Flag | Meaning |
|---|---|
| `--max N` | Videos per topic, default 50. Each 50 costs one search call (100 units). |
| `--length short` | Shorts lanes want this. Take it from the brief's lane. |
| `--sort` | `views` (default), `engagement`, `likes`, `recent`, `momentum`, `breakout` |
| `--since` | `hour`, `today`, `week`, `month`, `year`, `any` |
| `--geo US` | Geography screened **before** the donor scan, never after |
| `--depth 90` | Uploads scanned per channel in the donor trail |
| `--no-donors` | Scout and farm flag only |
| `--study <path>` | Run an existing multi-topic study config |
| `--refresh` | Re-run scout even if a workbook is cached |
| `--yes` | Approve a run over the confirm threshold |

The donor scan runs only when `briefs/donors/<brand>.json` exists. Without it the
command still scouts and flags farms, and says so. Don't invent a donor config:
picking which brands count as conversion evidence is a judgment call for the
brief, so ask Nicole what belongs in it.

## Step 2: Handle the gate

**Exit code 3 — stopped before spending.** The estimate is over the threshold in
`config/budgets.json`. Nothing ran. Show Nicole the estimate and the
day's usage, ask, and only then re-run the identical command with `--yes`.

A multi-topic study is usually what trips this: eight topics at `--max 100` is
roughly 3,200 units of the 10,000/day. That's fine on a clear day and not fine if
something else already ran.

## Step 3: Report

Relay:

- Where the outputs landed, and the estimated quota against the 10,000/day.
- The scout top-10 table as printed, in a code block.
- Farm Risk counts, and name the HIGH channels. Farm Risk is a screen, not a
  verdict — a channel can be flagged and still be right.
- Geo: how many were dropped as outside the target, and the country spread.
- With a donor scan: the channels with the most donor placements, their pattern
  (discrete rebookings beat a standing affiliate link), and where `report.md` is.
- Two or three observations worth acting on, from the Channels sheet.

Say plainly that these counts are sponsorship *evidence*, not verified deals, and
that Channel Country still wants a human eye before outreach.

Then: `→ Ready for review. Reply: APPROVE to proceed, REVISE [note] to adjust, NEXT to move to the next stage.`
