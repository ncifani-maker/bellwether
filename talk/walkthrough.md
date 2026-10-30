# Partner discovery, from search results to a sent pitch

## The objective

Find the review, comparison, listicle, and creator sites that already review brands like ours and rank highly in SERP. Get a verified email contact for each one.
Draft a pitch customized towards their content.

> Keep the human in the loop. The human owns the inbox.

## What we're going to do

|  | Step | In Claude Code | Who decides |
| --- | --- | --- | --- |
| 1 | **Seeds**: pick the category/top brand name searches | `/import-seeds` | operator |
| 2 | **Run the seeds**: scan, filter, sort | `/run-seeds` | the tool |
| 3 | **Curate**: pick the sites | the shortlist | the operator |
| 4 | **Fetch emails**: published, then Hunter, then verify | `/fetch-emails` | the tool, then operator |
| 5 | **Pitch**: draft, don't send | next | the operator; the operator sends |

---

## 1. Create seeds using /Snowball run

### What the input should be for a new client

Two things, plus one optional file. Every new brief asks for them:
1. **Categories (1–4):** what the client sells into or sits next to. `/snowball` won’t propose anything outside them.
2. **3–5 comparable brands:** *product* brands the client’s buyers also buy, the kind independent sites review. Not direct service competitors; your run showed those turn up Glassdoor, not reviewers.
3. **Optional, but the best start:** an export of the client’s **current affiliate or creator partners**, for example from Impact. Any CSV with a domain or website column works. Those sites already promote the client, so whatever else they review is the strongest seed list you can get.

**Which path to take depends on what exists:**
| You have | Run | SerpAPI cost |
| A partner export | `/snowball <client> --sites partners.csv` → approve → `/run-seeds` | 0 to get the brands |
| Categories that overlap your existing reviewer pool | `/snowball <client> --sites outputs/affiliate-seo-creators/2026-10/site-profiles.csv` | 0 to get the brands |
| Nothing yet | `/create-seeds <client> brand-review` with the 3–5 brands → approve → `/run-seeds` → `/snowball` → approve → `/run-seeds` | about 10 searches for the first pass |
For each brand, we'll search “[brand] review” and “[brand] reviews” in Google. Pull any unique site ranking on page 1 where the result is a review, reviews page, comparison review, recommended/sponsored products, or product testing article. Skip the brand’s own site unless it has third-party customer reviews that could be useful. Skip Reddit/forums unless we’re intentionally tracking UGC. We're not trying to rank for these yet. We're finding who already ranks. For example, a site that reviewed Caraway is a good bet for the next cookware brand.

The resulting spreadsheet becomes the seed list. Every seed is approved by a person before anything runs.

---

## 2. Run the seeds

```
/run-seeds affiliate-seo-creators --dry-run
```

It prints the cost **before** it spends, and it refuses if a run would go over the monthly cap.

**One command, three jobs:**

**Scan.** 125 Google searches, page one only. One day, on a free plan.

**Filter.** Throw out results for the following reason: 

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

---

## 4. Fetch emails

```
/fetch-emails "For the team.csv" affiliate-seo-creators
```

The site's own pages first, Hunter second, verify always. No guessed addresses.

Example:
| Of the 100 |  |
| --- | --- |
| Verified | 65 |
| Can't be confirmed (the domain accepts any address) | 6 |
| Nothing usable | 29 |

- 37 addresses came from the site's own contact or about page, for free. 34 came from Hunter.
- Two sites list an address on their own privacy page. Both bounce.
- The emails go back into the team's own sheet, in the same row order.
- No email address ever goes to GitHub.

---

## 5. Pitch

Next up. Each draft starts from the review the site actually published, not a merge field.

**The tool never sends.**

---

## What it cost

For example:
**$0.** 145 SerpAPI searches, 62 Hunter searches and 78 verifications, all on free tiers.

