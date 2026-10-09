---
name: create-seeds
description: "Draft a seed keyword list for a Bellwether brief: buyer-intent category queries (the four-bucket method), or \"[brand] review(s)\" queries for comparable brands. Writes them as `proposed`, optionally checks Google volume and cost-per-click, then records Nicole's approvals and retirements. Use when the user says 'create seeds', 'make a seed list', 'draft keywords' for a client or brief."
argument-hint: "<brief-slug> [category | brand-review] [brands or notes]"
allowed-tools: Bash, Read, Write
user-invocable: true
---

# /create-seeds

You draft; Nicole approves. The seed list is the first gate (PRD §5): nothing you write here runs
until she approves it.

## 1. Read the brief

`briefs/<slug>/brief.md`. You need: what it sells, who buys it, and 3–5 competitors or comparable
brands. If the brief is missing or thin, ask for exactly those, briefly. Don't invent a client's
competitors.

## 2. Pick the mode

- **category** (default): queries a buyer types while shortlisting. Use the four buckets in
  `docs/seed-list-framework.md`: commercial/comparison ("best X for Y", "X alternatives", "X vs Y"),
  category/how-to, vertical/ICP ("best X for <audience>"), brand/reputation. Aim for 12–20.
- **brand-review**: for each comparable brand, "[brand] review" AND "[brand] reviews". Both, because
  the plural surfaces different independent blogs (CHANGELOG D10: about 87% more usable sites).
  Group brands by category.

## 3. Apply what earlier runs taught (CHANGELOG)

- A seed earns its place by what its search results contain, not by volume. Cost-per-click is the
  better intent signal; volume only breaks ties.
- How-to and informational queries pull medical publishers and health systems, which don't take
  affiliate placements (Covey: 4 of 5 how-to seeds retired). Draft fewer of them.
- A brand seed for a brand nobody has heard of returns homonyms: a town, a restaurant, a supplement.
  Keep it as one low-priority seed, if at all.
- Ambiguous brand names catch other things: *Otherland* (a novel and a play), *Mosaic* (a café),
  *Purple*, *Bear*, *Sunday*, *Material*. Add the product word: "Purple mattress review".
- Marketplace and franchise brands (cleaning services, Angi, Thumbtack) return employee reviews on job
  sites and provider listings. Expect to retire some.

## 4. Write them as `proposed`

Write the draft to the scratchpad as a CSV, then import it. The importer never changes seeds the
brief already has.

- category: columns `intent,query`
- brand-review: columns `category,brand,query 1,query 2` (query 1 = singular, query 2 = plural)

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/import_seeds.py" "<draft.csv>" <slug> --hold --dry-run
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/import_seeds.py" "<draft.csv>" <slug> --hold
```

## 5. Optional: volume and cost-per-click

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/seed_volume.py" <slug> --dry-run
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/seed_volume.py" <slug>
```

DataForSEO, one request, pay-as-you-go: the dry run shows the balance first. Exit 3 means over the
confirm threshold; ask, then `--yes`. Exit 2 means the balance is too low; say so. Only offer this;
don't run it unasked.

## 6. Show the list and record her decision

Show the proposed seeds as a table (bucket or category, seed, and volume/CPC if checked). Then record
exactly what she says, never more:

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/seed_status.py" <slug> approve --all-proposed
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/seed_status.py" <slug> approve "<seed>" "<seed>"
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/seed_status.py" <slug> retire "<seed>" --reason "<why>"
```

Never approve on her behalf. Retiring always takes a reason.

Then: `→ Ready for review. Reply: APPROVE to proceed, REVISE [note] to adjust, NEXT to move to the next stage.`
Next stage: `/run-seeds <slug> --dry-run`.
