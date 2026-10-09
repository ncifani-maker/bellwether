# Changelog

All notable changes and decisions for Bellwether. Newest first. Each decision records who made it and
why, so a later session doesn't relitigate it.

---

## 2026-10-09 — Hunter test; contact rule amended

**D14. On a one-person site, the owner's address on the site's own domain is the business contact.** Nicole.
The rule said role or business addresses only. A Hunter test on three team sites that publish no email
(newmodernmom.com, nicolejaques.com, mattressclarity.com) returned for one of them a single personal
address with no role, which the rule would have dropped, though on a one-person blog there is no one else
to reach. close-demo accepted these for the same reason. Amended wording: "On a site run by one person,
that person's address on the site's own domain counts as the business contact. Still verified, still never
guessed." Whether a site is one person is evidence from `site_profile.py` (creator tier, one author), set
by the caller, never assumed.

**Hunter, measured (3 searches, Nicole approved):** one credit per domain search however many addresses
come back (mattressclarity returned five for one credit), against a third-party guide claiming a credit per
address. All three found something, so whether an EMPTY search costs a credit is still open; the contact
step will record Hunter's counter around each search and settle it on the real run. Searches: 45 of 50 left
until Oct 20. Nothing was stored: addresses appeared masked on screen only.

---

## 2026-10-08 — Curation: creators, not publications

**D13. The team gets creator-style blogs and niche review sites; media is set aside.** Nicole.
"Sites like nytimes.com" are not what the team curates. Small niche review businesses (mattressclarity,
housefresh, thegoodtrade) go WITH the creators: they monetize through affiliate links and review exactly
these categories. Media and publishers move to their own sheet, not deleted. Done before the Close.com
replay: the second step ahead of D5, after D9, chosen by Nicole as "review sites before video".

### Built
- `scripts/site_profile.py`: reads each kept site's homepage, about page, contact page and RSS feed (no
  API, no spend) and tiers it creator blog / niche review site / media / check, with the evidence in a
  column so any tier can be argued with. Calibrated on ten hand-judged sites first: 7/10, then 10/10
  after three fixes, all found on creators, the tier the team wants most:
  - **Feeds.** Small WordPress blogs often answer 403 to anything that isn't a browser, yet serve
    `/feed/`, which names every post's author. One author settles it.
  - **About pages live anywhere** (`/about-nicole-jaques/`), so the link is found on the homepage.
  - **Storefronts.** A linked ShopMy or Amazon storefront is a creator; no staff writer has one.
  A last resort uses the site's own article title in the singular first person ("Honest Review ... after
  2 plus years of use"), never "we" or "our", which reads as a team.
- `review_sites.collect()` split out of `build()` so both scripts share one list of kept sites. Lemon8
  (a social app) is now a platform, not a site.
- Output: `site-profiles.csv` (committed, no addresses: `published_email` is yes/blank) and
  `creator-shortlist.xlsx` (gitignored): For the team / Check by hand / Media - set aside / Method.

First run: 208 sites. **115 for the team** (60 creator, 55 niche), 27 media, 66 to check by hand: about
half blocked with no readable feed, the rest ambiguous, including homonyms the brand query caught by
accident (infinityplus.co.uk reviews the Tad Williams novel *Otherland*; dvc-members.com reviews the
Mosaic Canteen at Epcot). Of the 115, 41 publish an email and 80 have a contact page.

---

## 2026-10-06 (late) — Naming

**D12. No version number in the product's name.** Nicole.
The product is Bellwether. The PRD, this changelog, `CLAUDE.md` and `api_check`'s Close message used a
version number as part of the name; that wording is gone. Deliberately left as they are:
- the local folder `bellwether-2.0/` and the paths that point at it, which stay accurate while the folder
  keeps that name;
- `bellwether-1.0/`, the predecessor's real folder name;
- the git history. The first commit message keeps its original wording; changing it meant a force-push.
The GitHub repo has been `bellwether` from the start. Workbooks stay out of GitHub (`.gitignore`).

---

## 2026-10-06 (evening) — Plural run; spend-tracking fixes

### The plural run
61 "[brand] reviews" queries (D10, D11). 53 returned; 8 are held for the SerpAPI reset (Nicole):
- 3 timed out at SerpAPI's end: The Cleaning Authority, Hungryroot, Nectar mattress.
- 5 had their whole page wrongly dropped by the off-query guard: Mosaic Foods, Misen, Boy Smells,
  Easyplant, Moon Juice. **Claude's bug.** The guard wanted the word "reviews" and the titles said
  "Review"; after three flags it discards the page. Four more queries passed on a retry. The fix landed
  while the run was going, too late for the running process. Cost: about 24 searches of retries.

Merged with the singular run: 125 queries, **209 review sites, 41 reviewing 2+ brands** (from 162 and 25
on singular alone), consistent with the D10 test. Account at 50 searches left, the new reserve.

**Ledger gap, documented not patched:** this run logged 75 searches; the account fell 78. The old code
dropped the tally of any query that errored, so up to 5 requests from the 3 timed-out queries went
uncounted (whether SerpAPI billed the timeouts is unknown). The ledger records what the code counted;
the gap is recorded here rather than guessed into it.

### Fixed in `serp_scan.py`
- **Off-query guard** ignores spacing and a plural s: "Hungry Root" matches "hungryroot", "Review"
  matches "reviews". Re-checked against all 67 SERPs on file at the time: none flagged; the magnesium
  and dictionary-page failures it was built for are still caught.
- **Spend is counted per request sent**, at the moment it is sent, so a query that errors still reports
  its spend. Logged in a `finally`, so even a crashed run records what it spent.
- **The reserve is checked before every query**, not only before the run, and the account balance is
  re-read every 10 queries so spend from elsewhere (the tracker) is seen. Tested offline with fake calls:
  a timeout, a three-try query and 5 searches spent in parallel; it stopped at exactly the reserve.
- **Noise filter covers subdomains.** `ie.trustpilot.com` and `nz.trustpilot.com` had slipped through.
- Retry message reads "attempt 3/3", not "retry 3/2".

### Fixed in `review_sites.py`
- Marketplaces and local directories (homeadvisor.com, reviews.birdeye.com) skipped with their own
  reason: they are the providers' storefront, not reviewers. samsclub.com added to retail. The tracker's
  noise list is matched on the root domain.

---

## 2026-10-06 (afternoon) — Phase 0 scaffold; first scan

### Phase 0 done
Done-criteria from PRD §12 both pass from `bellwether-2.0/`: `/api-check` runs, and `/serp-scan --dry-run`
runs and enforces the seed gate.

- **Copied in (copy only, sources untouched):** all 13 scripts from `bellwether-1.0/scripts/`;
  `qualify_targets.py`, `score_opportunities.py`, `generate_hooks.py`, `dataforseo_kw.py`,
  `aeo_citations.py` from close-demo, plus `close_sync.py` as `crm_sync.py`; `config/budgets.json`;
  `vendor/youtube-scout/` with its patch; the five skills; `predictive-discovery-spec.md`,
  `partner-discovery-plan.md`, and close-demo's `PRODUCT-FEEDBACK.md` into `docs/`.
- **The spend ledger was copied too.** `data/api-usage.csv` carries October's spend from 1.0. A fresh ledger
  would have reset Bellwether's monthly count to zero and let the cap undercount.
- **Paths fixed.** Skills call scripts as `${CLAUDE_SKILL_DIR}/../../../scripts/`, relative to the skill,
  so a folder rename can no longer break them the way `bellwether/` → `bellwether-1.0/` did. `/scout`'s
  `scout.py` is a relative symlink into this repo's `vendor/`. `serp_scan`, `_brief`, `yt_scan` read the
  `briefs/<slug>/` layout (D4). `find_contacts --brand` no longer defaults to a company name.
- `briefs/_template/` created per PRD §6. `CLAUDE.md` written. `git init` done; **nothing committed.**
- `api_check`'s Close message no longer says "not used by Bellwether". Here it is the CRM (D3).
- **D8 noise list:** close-demo's `NOISE_DOMAINS` and 1.0's are identical. Nothing to fold in.

### Carried into Phase 1 (found, not fixed)
- Brand names still inside copied script logic, against D4: `run_study.py`'s default brand-channel pattern
  (meal kits), `build_shortlist.py`'s competitor panel, and close-demo's `generate_hooks.py` (Close.com in
  the system prompt) and `serp_research`-era seed defaults. Most other hits are provenance comments.
- close-demo scripts still write to `output/` (singular) and find keys via `../../.env`, which happens to
  resolve to `nac-worldwide/.env`. Switch them to `_keys.py` and `outputs/<slug>/` in Phase 1.
- 1.0's skills in `nac-worldwide/.claude/skills/` are still broken (PRD §14 Q6, still open). This repo's copies
  are separate and work.

**D9. A prospecting list can be a brief folder, and it ran ahead of the Close.com replay.** Nicole.
`briefs/affiliate-seo-creators/` holds a list, not a brand: "[brand] review" queries for 159 DTC brands,
imported from `~/Downloads/Affiliate SEO-Creator Seed List.xlsx`. Its conversion event, asks and exclusions
are N/A; they belong to whichever brand a site is later pitched for. Nicole chose to scaffold this repo and run
this list rather than run it on 1.0 (would have broken D2) or wait for the replay (D5). Scope: the 64 brands
with no Category Completion Date. The 95 dated brands were pulled by hand and are not re-run.

**D10. The plural query is worth running.** Tested by Claude; decision on budget pending with Nicole.
The source sheet asks for "[brand] review" AND "[brand] reviews". Tested on Saatva, Caraway and Pura
(6 searches): the plural added 13 usable sites to the singular's 15, about +87%, and they were
independent blogs (makinghomebase, mybalancedspace, jennakateathome, whimsysoul), not the aggregators
Claude had predicted. The prediction was wrong; the sheet was right. The 61 remaining plural queries are
held: with the singular run they exceed this month's cap and the tracker reserve.

**D11. SerpAPI reserve lowered 80 → 50, Bellwether's monthly cap raised 100 → 160.** Nicole.
To run the 61 plural queries D10 held. The reserve was sized for the tracker's daily client rank checks,
and those are not happening: the account read 213 searches left on Oct 2 and still 213 on the morning of
Oct 6. Tracker use is manual and occasional. After this run about 65 searches remain until the plan resets.
Supersedes the 80 in PRD §9. Revisit if the tracker's checks become daily.

### Built
- `scripts/review_sites.py`: applies a brand-review brief's rules (keep reviews, reviews pages,
  comparisons, product tests; skip the brand's own site, forums, retailers) and writes
  `review-sites.xlsx` with Sites, Results, Excluded and Method sheets. Nothing is dropped silently.
- First run on the list: 61 queries, 63 searches (two wrong-SERP retries), 162 review sites, 25 reviewing
  2+ brands. Two screen fixes came out of it, both now in the script:
  - **Job sites.** Indeed and Glassdoor topped the first build: for franchise brands (The Maids, Two Maids,
    Mr. Handyman) "[brand] review" is employee reviews. Supply side again. Now skipped, with its own reason.
  - **Padded brand domains.** helixsleep.com, bearmattress.com and hiyahealth.com were counted as reviews of
    themselves; the own-site check now matches the brand as a domain prefix.

---

## 2026-10-06 — Project created

### Added
- `PRD.md` (draft): one pipeline merging close-demo's seed-to-Close spine with Bellwether 1.0's YouTube
  lane and key, spend and contact tooling.
- `CHANGELOG.md` (this file).

### Decisions

**D1. close-demo is the baseline; Bellwether is rebuilt in a new folder.** Nicole.
close-demo's pipeline (stages, four gates, motion taxonomy, Close sync) is the spine. It lives at
`nac-worldwide/bellwether-2.0/` with its own git repo, next to `bellwether-1.0/` so it shares
`nac-worldwide/.env`.

**D2. Copy only. Never delete or edit anything in close-demo.** Nicole.
Everything it needs is copied in. `~/Desktop/serp-tracker/close-demo/` and `bellwether-1.0/` stay as they
are, as reference. Scripts it replaces are simply not copied.

**D3. Close is the CRM for every brand.** Nicole.
`close_sync.py` is copied as `scripts/crm_sync.py` and sits at the core of the pipeline, not as an
optional output. Lead creation and arming are automated; the send stays with Nicole. Nicole is getting a
fresh Close API key: the current one returned HTTP 401 on `/api-check` (2026-10-06). Phase 3 waits on it.

**D4. Every brand is a brief. No company names in file names.** Nicole.
A brand is `briefs/<slug>/` (brief, seeds, relationships, voice, donors), created from `briefs/_template/`.
No script, skill, config or template file is named after a company, and no script refers to a brand by
name. As a result:
- `close_sync.py` → `crm_sync.py` (avoids confusing the CRM with the Close.com client).
- The `close-brand-voice` skill → the first brief's `voice.md`, read by one generic drafting skill.
- 1.0's `briefs/<brand>.md`, `briefs/seeds/<brand>.csv` and `briefs/donors/<brand>.json` → one folder per
  brand.
The brief folder slug is the one place a brand name appears in a path, as data chosen at intake.

**D5. Close.com is the first brand to run, to validate the merge.** Nicole.
Replay against close-demo's saved results first (no spend), then a small live run. Pass criteria are in
PRD §11: the same 40 opportunities, the same motion split and the same 29 contacts.

**D6. Keep the SERP Tracker as the client-facing view.** Nicole.
Clients see results in the tracker: rank and AI-citation visibility for earned placements. Discovery runs
through `serp_scan.py`. Placements go into the tracker, and its CSV export is read back into
`data/results.csv`. `nacww_serp_tracker.py` is never modified from here. SerpAPI quota is shared, protected
by the reserve in `config/budgets.json`.

**D7. Build order approved.** Nicole.
Scaffold → brand-neutral schema + Close.com replay → YouTube lane into the shared table → live Close.com
run → activation (drafts, arming, reply sync, tracker hand-off) → second brand as config only.

**D8. Where the two predecessors overlap, one version is kept.** Proposed by Claude; approved with the build order.
- SERP: keep 1.0's `serp_scan.py` (spend caps, usage ledger); fold in close-demo's noise-domain list.
  close-demo's `serp_research.py` is not copied.
- Contacts: keep 1.0's `find_contacts.py` (verifies every address, handles creators and sites); add
  close-demo's motion-based role targeting. `hunter_enrich.py`, `find_emails.py` and `find_emails_web.py`
  are not copied.
- Keys: `nac-worldwide/.env` via `_keys.py`. close-demo's `keys.txt` pattern is dropped.
- Scoring: keep both methods in one `opportunities.csv` with a `lane` column. Motion + legitimacy for
  web, Bellwether Score + projected CPA for YouTube.

### Known issues carried in
- Bellwether 1.0's skills in `nac-worldwide/.claude/skills/` (`/yt-scan`, `/serp-scan`, `/find-contacts`,
  `/scout`, `/api-check`) point at `nac-worldwide/bellwether/`, which was renamed to `bellwether-1.0/`.
  They fail until fixed in place or replaced by this repo's copies. Not touched here (PRD §14 Q6).
- close-demo has uncommitted edits in the serp-tracker repo (`PRD.md`, `dataforseo_kw.py`,
  `score_opportunities.py`, `serp_research.py`). Phase 0 copies the working tree as it stands.

### Account state at creation (`/api-check`, 2026-10-06)
| Service | State |
| --- | --- |
| SerpAPI | Free plan, 213 searches left this month; shared with the SERP Tracker |
| Hunter | 48 searches and 95 verifications left; resets 2026-10-20 |
| DataForSEO | $0.54; enough for seed validation, not for traffic estimates |
| YouTube | Valid; 10,000 units/day |
| Anthropic, OpenAI | Valid |
| Close | **401, key rejected.** Fresh key pending (D3) |
