# What's in a brief folder

One folder per brand, `briefs/<brand>/` (CHANGELOG D25). Everything a brand needs, and everything the
commands make for it, sits together, so nobody has to jump between folders. Every file is CSV (D24): it
opens in Google Sheets, Nimbalyst or Excel as is.

| File | Made by | What it is | On GitHub? |
| --- | --- | --- | --- |
| `brief.md` | you | What it sells, who buys it, its categories and comparable brands | yes |
| `starting-sites.csv` | you (optional) | Sites `/snowball` should start from, such as a client's partner export | yes |
| `snowball.csv` | `/snowball` | Brands the review sites also review, and how many sites cover each | yes |
| `seeds.csv` | `/import-seeds`, `/create-seeds`, `/snowball` | The seed list. Only `approved` seeds are searched; searched ones become `done` | yes |
| `review-sites.csv` | `/run-seeds` | **The results: one row per review site, everything about it in one file** | **no**: it holds emails |
| `… (with emails).csv` | `/fetch-emails` | A team sheet handed back with emails filled in | **no** |
| `raw/` | the commands | The detail behind the results: no need to open (below) | yes, except anything with emails |

## review-sites.csv

It's a living file. Each `/run-seeds` adds the new sites it finds and updates the research columns of the
ones already there. It never touches:
- a column a person added (site type, niche, notes)
- an email that `/fetch-emails` verified or a person typed in

Only a blank or still-unverified published address gets refreshed. New rows come in with the team's tiers
first.

| Column | Meaning |
| --- | --- |
| `suggested` | The tool's pre-sort for the shortlist: "yes", "check: why" or "no: why" (D26). Recomputed on every write |
| `shortlist` | **Yours.** Mark yes for the sites to contact; `/fetch-emails <brief>` looks up only those. Never touched by the pipeline |
| `tier` | **creator blog**: an about page introducing one person, or a first-person homepage with 1–2 bylines. **niche review site**: testing language, a small team, or a review-business domain. **media / publisher**: a known media domain, or a parent publisher with several bylines; set aside, not deleted (D13). **check**: blocked, unreachable, or no clear signal; never guessed, since a 403 isn't an absence. A brief whose sites were categorized by hand uses `site type` (and `niche`) instead. |
| `evidence` | Why it got that tier |
| `brands_reviewed`, `categories`, `brands` | Which seed brands it reviewed. Ranked by brands reviewed: a site that reviewed four brands in a category is the one to pitch the fifth |
| `best_rank`, `result_types` | Its best Google position for any seed, and what kind of result it was |
| `ai_search` | Can ChatGPT's and Claude's **search** crawlers (OAI-SearchBot, Claude-SearchBot) read the page that ranked, per robots.txt? This decides whether it can be cited in an AI answer now. "fetch-only" means only the user-requested fetcher is allowed. |
| `ai_training` | Whether robots.txt blocks the **training** crawlers (GPTBot, ClaudeBot). It affects what future models learn, not today's citations. |
| `cdn` | `cloudflare` means the site can block AI bots at the network edge, whatever robots.txt says. A caution, not a verdict. |
| `authors_on_home`, `latest_year`, `affiliate_disclosure` | Bylines on the homepage, the newest year seen, and whether it discloses affiliate links |
| `about_page`, `contact_page` | Where to look first for a contact |
| `published_email` | `yes` if the site publishes an email on its own pages |
| `http` | The homepage's status (403 = blocked us) |
| `example_title`, `example_url` | Its best-ranking review |
| `email` | At research time, the address the site publishes (D18). After `/fetch-emails`, the verified address. |
| `email status` | `published on site, not yet verified` → then verified / unconfirmed / bounces / none found. A bounced address is cleared, so a dead address never looks live. |

The AI columns are information, never a filter (Nicole, 2026-11-04). robots.txt is stated policy, not
proof, and being allowed isn't the same as being cited.

## raw/

| File | What it is |
| --- | --- |
| `serp-results.json` | Every page-1 result for every seed searched, kept across runs |
| `serp-domains.csv` | One row per domain, by how many seeds it ranked for |
| `review-results.csv` | Every result kept: brand, query, rank, type, title, URL |
| `review-excluded.csv` | Every result thrown out, with the reason: the brand's own site, forums, retailers, app stores, and job sites (for service brands, "[brand] review" is full of employee reviews on Indeed and Glassdoor). The screen is a heuristic, so check it. |
| `site-profiles.csv` | The last run's sites, without emails: the committed record |
| `snowball-reads.json` | What each site's sitemap said, reused for 24 hours |
| `contacts-summary.csv`, `hunter-charges.csv` | How each contact was found and what Hunter charged, without addresses |
| `seeds.baseline.csv` | Demo briefs only: what `/reset-demo` restores, and the marker that makes every command replay saved results instead of going live (D27) |

Source for all of it: SerpAPI, google.com, desktop, page 1, no cache. Then each site's own homepage, about
page, contact page, robots.txt and sitemap. No paid API after the search.
