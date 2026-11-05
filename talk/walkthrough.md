# Bellwether- Partner discovery, from search results to a sent pitch

## The objective

Amplify CONSIDERATION funnel phase. 

Find the review, comparison, listicle, and creator sites that already review brands like ours and rank highly in SERP. Get a verified email contact for each one.
Draft a pitch customized towards their content.

> Keep the human in the loop. The human owns the inbox.

## What we're going to do

|  | Step | In Claude Code | Who decides | Tooling |
| --- | --- | --- | --- | --- |
| 1 | **Seeds**: give Claude the categories, affiliate partner lists, and comparable brands to search (brief.md). | `/import-seeds`, `/create-seeds`, `/snowball` | the tool proposes, the operator approves | Claude code |
| 2 | **Run the in-market names Claude provides**: scan, filter, sort | `/run-seeds` | the tool | Claude code, Google SERP API |
| 3 | **Curate (human in the loop)**: pick the sites | the `shortlist` column | the tool suggests, the operator picks | N/A |
| 4 | **Fetch emails**: published, then Hunter, then verify | `/fetch-emails` | the tool, then the operator | Hunter API |
| 5 | **Pitch**: draft, don't send | next | the operator; the operator sends | CRM of choice |

---

## 1. Seeds

A seed is a brand to search for: "[brand] review" and "[brand] reviews."
We're not trying to rank for these yet. We're finding who already ranks.
A site that reviewed Caraway is a good bet for the next cookware brand.

**Three ways to get seeds:**

| Way | Command | When |
| --- | --- | --- |
| Bring your own list | `/import-seeds <sheet> <brand>` | You already have brands in a spreadsheet. Our 159 brands came in this way |
| Draft from the brief | `/create-seeds <brand>` | A brand-new client: Claude drafts searches for the brief's 3–5 comparable brands |
| Snowball | `/snowball <brand>` | We already know some review sites: find the brands they also review |

**What `/snowball` does:** it reads the sitemaps of review sites we already know and counts what else
they've reviewed. A brand that several creator blogs have already reviewed is a proven seed. It's free:
no paid API.

**What goes in for a new client:**
1. **Categories (1–4):** what the client sells into or sits next to. `/snowball` won't propose anything
   outside them.
2. **3–5 comparable brands:** *product* brands the client's buyers also buy, the kind independent sites
   review. Not direct service competitors: those turn up Glassdoor, not reviewers.
3. **Optional, but the best start:** an export of the client's **current affiliate or creator partners**,
   for example from Impact. Those sites already promote the client, so whatever else they review is the
   strongest seed list you can get.

### Demo: Braise *(a fictional brand)*



| **Sells** | Non-toxic ceramic cookware, direct to consumer. A $145 braiser, a $395 set |
| **Categories** | Kitchen / cookware; kitchen tools & appliances |
| **Comparable brands** | Caraway, Our Place, GreenPan, Great Jones, HexClad |
| **Review sites** | 66 sites that already reviewed those brands (32 from October's cookware searches, 34 from five brands `/snowball` found), each categorized by type and niche, with whether AI crawlers can read it |

**Everything is in one folder,** `briefs/braise/`:

| File | What it is |
| --- | --- |
| `brief.md` | the brief: what it sells, its categories, its comparable brands |
| `snowball.csv` | what `/snowball` found: brands those review sites also review |
| `seeds.csv` | the seed list: the brands we approve |
| `review-sites.csv` | what `/run-seeds` found: one row per review site, everything about it in one file |

**The prompt:**

```
/snowball braise
```

It reads the sitemaps of the sites in `review-sites.csv`, counts what else they've reviewed into
`snowball.csv`, sorts brands from noise, and proposes seeds. (Braise is a demo brief, so it replays the
read it saved: seconds, not minutes.)

| Proposed | Why |
| --- | --- |
| Made In | DTC cookware |
| Ooni | DTC pizza ovens |
| ThermoWorks | DTC kitchen tools |
| Vitamix | premium blenders (also sold in retail) |
| Blue Diamond | ceramic nonstick, the same product. Seed it as "Blue Diamond pan review": it's also an almond brand |

**Dropped:** Lufthansa, Fitbit, Sherwin-Williams, a retractable garden hose. Lifestyle creators review
everything.

**Then approve:**

```
approve Made In, Ooni and ThermoWorks
```

They go into `seeds.csv`. Nothing is searched until a person approves it.

**Which path to take depends on what exists:**

| You have | Run | SerpAPI cost |
| --- | --- | --- |
| A spreadsheet of brands | `/import-seeds <sheet> <client>` → `/run-seeds` | 2 per brand |
| A partner export | `/snowball <client> --sites partners.csv` → approve → `/run-seeds` | 0 to get the brands |
| Categories that overlap a reviewer pool we already have | `/snowball <client> --sites <pool>/site-profiles.csv` → approve → `/run-seeds` | 0 to get the brands |
| Nothing yet | `/create-seeds <client>` with the 3–5 brands → approve → `/run-seeds` → `/snowball` → approve → `/run-seeds` | about 10 searches for the first pass |

**What counts as a result** on page 1:
- a review, a reviews page, a comparison, recommended or sponsored products, or a product-testing article
- skip the brand's own site, unless it carries third-party customer reviews worth having
- skip Reddit and forums, unless we're tracking UGC on purpose

Every seed is approved by a person before anything runs. Already have a seed spreadsheet?
`/import-seeds` brings it in.

---

## 2. Run the seeds

```
/run-seeds braise
```

Live, it prints the cost **before** it spends, and it refuses if a run would go over the monthly cap.
Braise replays the searches it already ran, so it takes seconds and spends nothing. Every run adds the
review sites it finds to `review-sites.csv`, and updates the ones already there.

**When we ran five of `/snowball`'s brands for real** (Made In, Ooni, ThermoWorks, Meatstick, Gozney):
ten searches found 34 review sites we didn't have: BBQ and smoking blogs, pizza-oven testers, a cookware
reviewer. 4 weren't reviewers (two forums, a shop, a Google copy), and the filter now catches those.

*The numbers below are from our real October run: 64 brands across 8 categories.*

**One command, three jobs:**

**Scan.** 125 Google searches, page one only. One day, on a free plan.

**Filter.** Throw out results for the following reasons:

| Reason |
| --- |
| The brand's own site |
| Not a review |
| Retailer |
| Job sites ("what's it like to work there") |
| Directories |
| Forums |
| App stores |

**Sort.** 208 review sites, put into tiers:

| Tier |
| --- |
| Creator blog |
| Niche category site |
| Review site |
| Niche review site |
| YouTube reviewer (video pack) |
| Media (set aside) |
| Check by hand |

How it knows a creator: author names in the RSS feed, "Hi, I'm" on the about page, a ShopMy
storefront, titles written in the first person.

Along the way it also records:
- any email the site publishes on its own pages
- whether ChatGPT and Claude's search crawlers are allowed in. 25 of the 208 block at least one.

---

## 3. Curate

The team picks from the results, removing sites that are not relevant and highlighting any priorities.

It all happens in `review-sites.csv`. Two columns sit right after the domain:
- **`suggested`**: the tool's pre-sort. Yes, check or no, always with the reason: "no: media, set
  aside", "check: newest date seen is 2016".
- **`shortlist`**: ours. Mark yes for the sites to contact.

For Braise: 66 sites → 40 suggested yes, 9 to check, 17 no. **The tool suggests; a person picks.**

---

## 4. Fetch emails

```
/fetch-emails braise
```

It looks up only the sites marked yes in `shortlist`, reuses any contact already verified for another
list (no charge), and fills `email` and `email status` in the same file.

The site's own pages first, Hunter second, verify always. No guessed addresses.

Example:

| Of the 100 |  |
| --- | --- |
| Verified | 65 |
| Can't be confirmed (the domain accepts any address) | 6 |
| Nothing usable | 29 |

- 37 addresses came from the site's own contact or about page, for free. 34 came from Hunter.
- Two sites list an address on their own privacy page. Both bounce.
- The emails go into the same file, `review-sites.csv`, or back into a team's own sheet, in the same row order.
- No email address ever goes to GitHub.

---

## 5. Pitch

Next up. Each draft starts from the review the site actually published, not a merge field.

**The tool never sends.**

---

## What it cost

For example: **$0.** 145 SerpAPI searches, 62 Hunter searches and 78 verifications, all on free tiers.
