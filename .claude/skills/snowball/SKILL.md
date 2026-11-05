---
name: snowball
description: "Find seed brands from what our review sites already review. Reads each review site's sitemap and feed, counts how many sites cover each brand, then sorts brands from noise and proposes '[brand] review(s)' seeds. Saves only the ones Nicole approves. Free: no paid API. Use when the user says 'snowball', 'find more brands', 'what else do these sites review', or wants a seed list for a new client without picking brands by hand."
argument-hint: "<brief-slug> [--sites <csv of starting sites>] [--refresh]"
allowed-tools: Bash, Read, Write
user-invocable: true
disable-model-invocation: true
---

# /snowball

The script counts; you sort; Nicole approves. Nothing is saved as a seed until she does (CHANGELOG D22,
D23). This often runs live in a talk, so keep it quick: no dry run, no extra reading, a short answer.

## 1. Count (free)

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/snowball_brands.py" <slug> [--sites "<csv>"] [--refresh]
```

Starting sites, if `--sites` isn't given: `briefs/<slug>/starting-sites.csv` (a hand-curated list, such as
a client's partner export), else the brief's own `briefs/<slug>/review-sites.csv`. It writes
`briefs/<slug>/snowball.csv`, beside the brief and the seed list (D25). No starting sites at all for a new client? Then it starts from
3–5 comparable brands: `/create-seeds <slug> brand-review` → approve → `/run-seeds <slug>` → then
`/snowball`.

Each site's read is reused for 24 hours, so a run later the same day takes seconds. Pass `--refresh`
only when she asks for a fresh read.

On a demo brief (one `/reset-demo` can reset, such as Braise) every saved read is reused, whatever its
age, and a site never read is left out. The stage run matches the rehearsal and takes under a second
(D27). `--live` reads as usual; use it only before a talk.

## 2. Sort brands from noise

Work from the "Top names not already seeded" list the script prints. Open `snowball-names.csv` only if
that list isn't enough. Read the brief's categories first: propose nothing outside them.

- **Keep** a consumer brand that independent sites review: a DTC or challenger brand.
- **Drop**, with a one-word reason:
  - ordinary words ("air", "best"), unless it's a brand that happens to be a word (Casper, Puffy)
  - retailers and marketplaces (Costco, Walmart)
  - legacy brands sold mainly through retail (KitchenAid, Sealy)
  - tech giants (Apple, Samsung, Google)
  - closed companies (Freshly closed in 2022)
  - anything outside the brief's categories (an airline, sneakers, paint, a garden hose)
- **Flag:**
  - An ambiguous name gets the product word: "Blue Diamond pan review", not "Blue Diamond review".
  - Service, franchise and marketplace brands carry job-site risk: they found Glassdoor, not reviewers.
- **Prefer** product brands with creator blogs covering them, in categories the brief hasn't covered much.

## 3. Show the picks (don't save yet)

A short table: brand, creator blogs / all sites, why. Aim for 3–8. Then one line of the most striking
drops, so she can overrule you ("Dropped: Lufthansa, Skechers, Sherwin-Williams…"). Then:

`→ Ready for review. Reply: APPROVE to proceed, REVISE [note] to adjust, NEXT to move to the next stage.`

## 4. Save only what she approves

When she approves brands ("approve Made In, Ooni and ThermoWorks"), write just those to the scratchpad as
`category,brand,query 1,query 2` (singular, then plural; with the product word where flagged), import
them, and record her approval:

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/import_seeds.py" "<approved.csv>" <slug> --hold
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/seed_status.py" <slug> approve "<seed>" "<seed>" ...
```

Never approve anything she didn't name. Next stage: `/run-seeds <slug> --dry-run` (on a demo brief,
just `/run-seeds <slug>`: it replays and can't spend).

A rehearsal on a demo brief? `/reset-demo <slug>` puts its seeds back afterwards.
