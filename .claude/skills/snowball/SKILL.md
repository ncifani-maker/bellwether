---
name: snowball
description: "Find seed brands from what our review sites already review. Reads each review site's sitemap and feed, counts how many sites cover each brand, then sorts brands from noise and proposes '[brand] review(s)' seeds for Nicole to approve. Free: no paid API. Use when the user says 'snowball', 'find more brands', 'what else do these sites review', or wants a seed list for a new client without picking brands by hand."
argument-hint: "<brief-slug> [--sites <csv of starting sites>]"
allowed-tools: Bash, Read, Write
user-invocable: true
disable-model-invocation: true
---

# /snowball

The script counts; you judge; Nicole approves. Nothing becomes a seed until she does (CHANGELOG D22).

## 1. Starting sites

The script needs review sites to start from: any CSV with a `domain` (or `website` / `url` / `site`)
column. In order of preference:

1. **This brief's own** `outputs/<slug>/<slate>/site-profiles.csv`, from an earlier `/run-seeds`.
   This is the default.
2. **The client's existing affiliate or creator partners**, exported from their network (Impact
   etc.). These are the best start there is: sites that already promote the client.
3. **Another brief's pool**, when the categories overlap, for example
   `outputs/affiliate-seo-creators/2026-10/site-profiles.csv`.

None of these exist for a brand-new client? Then it starts from 3–5 comparable brands:
`/create-seeds <slug> brand-review` → approve → `/run-seeds <slug>` → then `/snowball`.

## 2. Count (free)

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/snowball_brands.py" <slug> [--sites "<csv>"] --dry-run
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/snowball_brands.py" <slug> [--sites "<csv>"]
```

It takes a few minutes for about 200 sites. Output: `outputs/<slug>/<slate>/snowball-names.csv`
(name, sites, creator_sites, seeded, common_word, example_sites).

## 3. Sort brands from noise

Read `snowball-names.csv`, starting with the rows that aren't seeded. For each name, decide:

- **Keep** a consumer brand that independent sites review: a DTC or challenger brand.
- **Drop**, with a one-word reason:
  - ordinary words ("air", "best", "black"), unless it's a brand that happens to be a word (Casper,
    Puffy). The `common_word` flag marks these for you to check; it doesn't decide.
  - retailers and marketplaces (Costco, Walmart, IKEA)
  - legacy brands sold mainly through retail (Sealy, Serta, Tempur-Pedic)
  - tech giants (Apple, Samsung, Google)
  - closed companies (for example, Freshly closed in 2022)
  - a product model when the brand is already a row ("nolah evolution" → "nolah")
- **Category:** use the brief's categories where they fit.
- **Flags:**
  - An ambiguous name gets the product word: "Purple mattress review", not "Purple review".
  - Service, franchise and marketplace brands carry job-site risk: in the 2026-10 run they returned
    Glassdoor and Indeed, and no reviewers.

**What a good seed looks like** (from the 2026-10 run): a product brand with at least 2 creator blogs
covering it. Product brands with buzz found the creators; service brands found none. Prefer names in
categories the brief hasn't covered much yet. A brand that 15 of *our* sites already cover will mostly
re-find those same 15, so it's proven but not new.

Aim for 15–30 brands, grouped by category. Stay within the brief: don't propose a category the client
doesn't sell into.

## 4. Propose them

Write `category,brand,query 1,query 2` (singular, then plural) to the scratchpad, then import them as
`proposed`. The importer never changes seeds the brief already has.

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/import_seeds.py" "<draft.csv>" <slug> --hold --dry-run
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/import_seeds.py" "<draft.csv>" <slug> --hold
```

## 5. Show the list and record her decision

Show a table: category, brand, creator blogs / all sites, and any flag. Then a short list of what you
dropped and why, so she can overrule you. Record exactly what she says, never more:

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/seed_status.py" <slug> approve --all-proposed
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/seed_status.py" <slug> retire "<seed>" --reason "<why>"
```

Optional, and only if she asks: `/create-seeds` step 5 checks volume and cost-per-click (DataForSEO,
pennies).

Then: `→ Ready for review. Reply: APPROVE to proceed, REVISE [note] to adjust, NEXT to move to the next stage.`
Next stage: `/run-seeds <slug> --dry-run`.
