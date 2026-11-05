# Brief — <Brand> · <lanes: web, youtube>

*Copy this folder to `briefs/<slug>/`. The slug is the one place a brand name appears in a path.*
*Nothing runs until the three **Required** sections are filled (PRD §6).*

## What it sells
<Product, price point, how it is bought. One paragraph.>

## ICP
<Who buys it. Demand side only: the people who would buy, not the people who would supply it.>

## Categories and comparable brands  **for seeds**
- **Categories:** <the 1–4 categories it sells into or sits next to. /snowball proposes nothing outside them.>
- **Comparable brands:** <3–5 product brands this client's buyers also buy, the kind independent sites review.
  Not direct service or franchise competitors: in the 2026-10 run those turned up job sites, not reviewers
  (CHANGELOG D22).>
- **Known partner sites (optional):** <a CSV export of the client's current affiliate or creator partners,
  with a domain or website column, saved as `briefs/<slug>/starting-sites.csv`. /snowball starts from it
  when it exists. A `site type` column, if you add one, is respected (CHANGELOG D23).>

## Conversion event  **Required**
<The event that counts as a conversion, the attribution window, the tracker.>

## Asks by motion  **Required**
- **editorial-outreach:** <what we ask an editor for>
- **referral-partner:** <what we offer a complementary business>
- **marketplace:** <listing terms, if any>
- **paid-placement:** <budget rules; flag thresholds>
- **creator-sponsorship** (YouTube lane): <rate guidance>

## Hard exclusions  **Required**
- <media tiers out of reach, retail, competitors, anything off-brand or unsafe>

## Competitor test
Both sides of the transaction: who sells the same thing, AND who else wants the same inventory.
<e.g. a contractor channel citing "rated on Angi" is supply side, not a partner>

## Lane economics (YouTube lane only)
<!-- bellwether:economics — read by scripts/_brief.py. null = not set; pricing refuses to run. -->
```json
{
  "currency": "USD",
  "cpa_target": null,
  "cpa_ceiling": null,
  "flag_above_rate": null,
  "placements": {
    "longform": {"judged_on": "cpa", "cpm_cap": null, "cpm_stretch": null,
                 "signup_rate_median_pct": null, "signup_rate_optimistic_pct": null,
                 "typical_rate": null, "views_basis": "median_longform_views"},
    "shorts":   {"judged_on": "cpm", "cpm_cap": null, "cpm_stretch": null,
                 "typical_rate": null, "views_basis": "median_shorts_views"}
  }
}
```
