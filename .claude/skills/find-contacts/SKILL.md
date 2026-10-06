---
name: find-contacts
description: "Bellwether Herald, step 1. Finds a verified way to reach each creator or partner on a shortlist: the channel's own published business address first (free), a Hunter domain search on a site they link second, and Hunter verification of every address always. Writes data/contacts.csv. Use when the user says 'find contacts', wants emails for a shortlist, or is ready to request rates from creators."
argument-hint: "--from-shortlist <xlsx> [--priority Book] [--reviewed] [--top N] [--no-hunter] [--verify-only] [--dry-run]"
allowed-tools: Bash, Read
user-invocable: true
disable-model-invocation: true
---

# /find-contacts

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../scripts/find_contacts.py [flags]
```

## The rule this implements

From `CLAUDE.md`, approved 2026-09-23: contacts come only from the
partner's own published pages or Hunter.io, restricted to role addresses and
business roles, and **every address is verified before a pitch is drafted against
it**. No guessed addresses, no harvesting beyond the target's own domain, no
captcha-gated sources.

That last one matters here. A YouTube About-page email sits behind a captcha.
Nicole can reveal it by hand; you never do, and you never suggest a way around it.

## Run it in two passes

Cheapest first, because the Hunter free tier is 50 searches and 100 verifications
a month.

1. `--dry-run` — reads channel descriptions (1 YouTube unit per 50 channels, no
   Hunter) and tells you exactly what the run would cost: how many creators
   publish an address, how many link a site worth searching, how many publish
   neither. The plan is computed from real descriptions, not from a worst case.
2. The real run, or `--verify-only` to check addresses already found.

| Flag | Meaning |
|---|---|
| `--from-shortlist <xlsx>` | A `build_shortlist.py` workbook |
| `--priority Book` | Only rows at that priority |
| `--reviewed` | Only rows you have hand-reviewed (the Review column) |
| `--top N` | First N rows after filtering |
| `--no-hunter` | Descriptions only, spends nothing |
| `--verify-only` | Verify addresses already in `data/contacts.csv` |
| `--yes` | Approve a run over the confirm threshold |

Re-running upserts on (handle, email), so a second pass corrects rows instead of
duplicating them.

## Reading the result

`usable` is the column that decides:

| Verify status | `usable` | What it means |
|---|---|---|
| `valid` | yes | Deliverable. Ready for a draft. |
| `webmail` | yes | A webmail address they published themselves. Fine. |
| `accept_all` | decide | Catch-all domain: it accepts everything, so deliverability is unconfirmed. Common on small blogs. Nicole's call. |
| `unknown`, `risky` | no | Use a contact form instead |
| `invalid`, `disposable` | no | Would bounce. Never send. |

A management or agency domain (`...mgmt.com`, an agency address) is a legitimate
business contact for booking, not a miss. Say so rather than treating it as a
lower-grade result.

## Reporting

The script masks addresses on screen (`h***@domain.com`) and writes them in full
to `data/contacts.csv`, which is gitignored because it is the only file in the
project holding personal data. **Keep them masked in your reply too** — a
transcript gets pasted around, and the CSV is one click away for anyone who
actually needs to send.

Report: how many are ready to send, how many need a decision, and how many
creators publish nothing. For that last group, name the honest options — the
About-page email by hand, a linked Instagram or Linktree followed manually, or
skip them — and do not invent an address for anyone.

Then: `→ Ready for review. Reply: APPROVE to proceed, REVISE [note] to adjust, NEXT to move to the next stage.`

Next stage is drafting. Herald drafts, Nicole sends.
