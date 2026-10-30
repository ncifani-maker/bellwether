# Changelog

All notable changes and decisions for Bellwether. Newest first. Each decision records who made it and
why, so a later session doesn't relitigate it.

---

## 2026-10-30 — /snowball: seed brands from what our reviewers already review

**D22. Seed brands can come from the reviewers, not from memory.** Nicole asked to automate the
category / brand seed list. Until now the operator supplied both: the team's sheet had 19 categories and
159 brands, chosen by hand, and Bellwether only ran them. `scripts/snowball_brands.py` reads each review
site's sitemap and RSS feed, keeps "[X] review(s)" and "[X] vs [Y]" posts, and counts how many different
sites cover each name. It's free: public pages only, no paid API.

Measured on the 2026-10 run (179 non-media sites, 136 readable): 3,222 names on 2+ sites, with 30+
credible DTC brands that weren't on the team's list, each covered by at least two creator blogs (Nolah,
Casper, Puffy, LMNT, Eight Sleep, HelloFresh, Aera and others).

Why it counts but doesn't judge: the raw list mixes ordinary words, retailers, legacy brands, tech
giants and closed companies (Freshly), and some brands are ordinary words (Casper, Puffy), so a
dictionary filter can't decide. Sorting brands from noise is the /snowball command's in-session step, and
its proposals go in as `proposed`. Nicole approves them, as with every seed.

What a good seed looks like, measured on the same run: product brands with buzz found creator blogs
(Caraway 8, Pura 6, AirDoctor 4); service and franchise brands found none (The Cleaning Authority, Two
Maids, Mr. Handyman, Lawn Love: zero review sites, only job sites). A brand that many of our sites already
cover is proven but mostly re-finds the same sites, so the command prefers creator coverage in thinly
covered categories.

Limit: it can only grow categories whose reviewers are already in the data. The 10 categories pulled by
hand in June and July have no reviewer sites in Bellwether yet.

---

## 2026-10-22 (later) — Outputs live in the repo's outputs folder

**D21. Future outputs go in `bellwether-2.0/outputs/`, not Downloads.** Nicole.
Including the files handed back to her: `emails_into_sheet.py` now writes
`outputs/<brief>/<slate>/<name> (with emails).csv` instead of next to the source. Because that folder is
inside the repo, the D16 protections now matter on every run: `.gitignore` covers `*with emails*.csv`, the
pre-commit hook refuses email addresses, and the script asks git whether the file is ignored before
writing it, and refuses if not (a renamed file can't slip through). Tested: written, invisible to
`git status`, and a non-matching name is refused. Supersedes D16's "never writes into the repo".

**Re-filling a sheet the team already works in.** The team's "For outreach" export came back with the
first run's columns pasted in (32 rows still "waiting"). `emails_into_sheet.py` used to refuse a sheet
that already had an `email` column; it now fills it in place. Blank cells get the address; a cell the
team filled is never overwritten (a different address is printed as "check it"); the status column is
refreshed only where it still holds one of the script's own statuses, so a team note survives.
`--status-column` names that column when it isn't "email status" (theirs is headed `contact_page`).
Tested both guards on a throwaway copy. Result on the real sheet: exactly the 32 waiting rows changed.

---

## 2026-10-22 — Hunter reset: the last 32 contacts

**D20. Bellwether's Hunter budget counts from the 20th, Hunter's own reset day, with a 40-search cap.**
Nicole. The cap counted by calendar month, so October's 30 searches blocked a fresh Hunter cycle (reset
Oct 20) until Nov 1. `config/budgets.json` gains `cycle_reset_day: 20` and `_budget.window_start()`;
SerpAPI still counts by calendar month. 40 of Hunter's 50 leaves room for anything else on the account.

### The run
The 32 sites waiting since Oct 9: 32 searches, 18 verifications. 16 verified, 1 accept-all, 15 nothing
usable (12 where Hunter found nothing, 2 where it found a personal address on a multi-author site, which
D14 does not cover). **The whole list of 100: 64 verified, 6 to decide, 30 nothing usable.** Nicole has
the team CSV back with emails filled (Downloads, local only).

### Caught before or during the run
- **Re-running a list redid every site.** `find_contacts --from-sites` had no memory of what was already
  resolved: it would have re-verified the 41 published addresses and re-searched 27 sites, about 60
  credits for nothing. Resolved sites are now skipped; `--refresh` redoes them.
- **`_budget` counted verifications as searches** ("88 of 30 searches"). The per-unit cap lookup turned
  "searches" into "searche", matched nothing, and fell back to counting every Hunter unit. Fixed; the
  earlier test passed only because no verifications had been logged yet.
- **The run detached from its terminal mid-way** (the shell exited 144; the process kept going) and only
  saved because it happened to finish. Saving and spend logging now sit in a `finally`: an interrupted
  run keeps verified rows, keeps found-but-unchecked addresses as `pending` for `--verify-only`, and logs
  what it sent. Tested with a fake Hunter and a forced interruption.
- **The summary file covered only the latest batch**, so this run had cut it from 100 sites to 32. It is
  now built from `data/contacts.csv` for the whole list, and was rebuilt.
- **The empty-search measurement was lost** with that terminal, because it was only printed. It now goes
  to `outputs/<slug>/<slate>/hunter-charges.csv` (domains and counts, no addresses). Still open.

### Unexplained, again
Hunter shows 29 searches and 58 verifications used since the reset; Bellwether's ledger has 32 and 18.
Fewer searches than sent (some empties free, or counter lag), and 40 verifications that were not this
pipeline, the same pattern as last cycle.

---

## 2026-10-11 — AI crawler access at research time

**D19. Research records whether ChatGPT and Claude can read each site.** Nicole's idea.
A placement on a page that AI answer engines can't read is worth less to a buyer who asks them. Read
from each site's robots.txt, against the page that actually ranked, not just the homepage. Three columns
in `site_profile.py`, so in `/run-seeds` output and the committed `site-profiles.csv` (no personal data):

- `ai_search`: can the SEARCH crawlers read it? `yes` / `no` / `fetch-only` (search crawler blocked,
  user-requested fetcher allowed). This decides citation in answers now.
- `ai_training`: which TRAINING crawlers are blocked. Future models, not today's answers.
- `cdn`: `cloudflare` when the site is behind it, since the edge can block AI bots whatever robots.txt
  says. When the edge also refused our own browser-like fetch, `ai_search` says so.

Bot names from the companies' own pages, checked today: OpenAI's OAI-SearchBot (blocked sites "won't
appear in ChatGPT search answers"), ChatGPT-User (user fetches; "robots.txt rules may not apply"),
GPTBot (training); Anthropic's Claude-SearchBot (search indexing), Claude-User (user fetches),
ClaudeBot (training). Search and training are separate on purpose: healthline.com blocks training and
allows search, so a single "blocked" column would have called a citable site blocked.

Rules: a robots.txt that refuses our check is `unknown`, not blocked; no robots.txt means allowed. It
is stated policy, not proof, and allowed is not cited. Tested on six synthetic robots.txt files with
known answers (one expected value was wrong in the test, not the code) and on real sites: nytimes.com
and mashable.com block search and training; the creator blogs allow everything.

---

## 2026-10-10 (evening) — /create-seeds

### Built
- **`/create-seeds <slug>`**: stage 1 of the pipeline, named to match `/import-seeds` and `/run-seeds`
  (the PRD called it `/seed-list`; renamed there). Claude drafts in-session, in one of two modes:
  *category* (close-demo's four buckets, now in `docs/seed-list-framework.md`) or *brand-review*
  ("[brand] review" and "[brand] reviews", with the product word added to ambiguous names). The
  skill carries the seed lessons logged so far: intent over volume, how-to queries pull medical
  publishers, unknown brand names pull homonyms, franchise brands pull employee reviews. Everything
  lands as `proposed`; nothing runs until Nicole approves.
- `scripts/seed_status.py`: approve, hold or retire seeds with who and when in the note. Retiring
  refuses to run without a reason.
- `scripts/seed_volume.py`: Google volume and cost-per-click from DataForSEO, one request, balance
  checked first (free), confirm threshold respected, actual cost read back into the ledger. Standard
  library port of close-demo's `dataforseo_kw.py`. Writes `briefs/<slug>/seed-volume.csv`.
- `import_seeds.py` carries an intent/bucket column, and after a `--hold` import points at approval
  rather than at running.
- Tested end to end on a throwaway brief (both modes, approve, retire, the refusal, the volume dry
  run), spending nothing; the test brief was deleted.

---

## 2026-10-10 (later) — Commands for the web lane

### Built
Three commands so the steps run the same way every time, instead of as one-off scripts in a session:
- **`/import-seeds <file> <slug>`** (`scripts/import_seeds.py`): a downloaded seed spreadsheet into
  `briefs/<slug>/seeds.csv`. Columns matched loosely; a completion date marks a row done. Re-importing
  keeps every existing seed's status, so a run, a hold or a retirement is never undone. Tested: the
  original sheet re-imported changes nothing; into a fresh brief it gives the same 190 done and 128
  approved worked out by hand on Oct 6. Reads a file because the Google Sheets connector has been
  failing to connect.
- **`/run-seeds <slug>`** (`scripts/run_seeds.py`): `serp_scan` → `review_sites` → `site_profile`, page 1
  by default, budget gates respected (exit 3 waits for Nicole, exit 2 is a refusal).
- **`/fetch-emails <csv> <slug>`**: `find_contacts --from-sites`, then the new
  `scripts/emails_into_sheet.py`, which hands back the team's own CSV with `email` and `email status`
  added, same rows and order. Tested on a copy of their list: the same 53 addresses as the file Nicole
  already has. It never writes into the repo; `.gitignore` also covers `*with emails*.csv`.

### Noted
SerpAPI showed 25 searches left on Oct 10, down from 50 on Oct 6, with no Bellwether scan in between:
the tracker or the `serp-tracker` session. The 50 reserve now refuses any Bellwether scan until the plan
resets, which is the reserve doing its job. Bellwether's own October count is 162 against the 160 cap,
because the plural run's retries (pre-fix code) went past its estimate.

---

## 2026-10-10 — Published emails captured at research time

**D18. If research finds a published email, it goes in a new column straight away.** Nicole.
Until now `site_profile.py` only flagged `published_email` yes/blank and left the address for the contact
step. Now the address itself lands in the local workbook (`creator-shortlist.xlsx`) as
`published email (unverified)`, right after the flag. Unchanged: the committed `site-profiles.csv` carries
yes/blank only (D16), and every address is still verified at the contact step before it is used.

### Built
- `scripts/_emails.py`: the one definition of "an email this site publishes" (own domain, self-published
  webmail, or a business-cued manager/agency line; junk and privacy@-type addresses dropped), moved out of
  `find_contacts.py` and now used by both research and the contact step, so they cannot disagree.
- Tested: the contact step picks the same address as before for 6 of 6 sites; research captures the same
  address the contact step would; the committed CSV has no address column.
- Side effect: research previously detected only `mailto:` links. With the shared check it also reads the
  page text, so future runs will flag more sites as publishing an email.

---

## 2026-10-09 (evening) — Email addresses stay local

**D16. No document containing an email address is pushed. Contacts stay on this Mac.** Nicole.
Audit before the rule: every file in all 7 commits on GitHub scanned for email-shaped strings, with
controls (the scan reads every commit, catches a test address, and finds the 58 real ones in the local
`data/contacts.csv`): **none**. `data/contacts.csv` has never been committed.

Enforced, not remembered: `.githooks/pre-commit` refuses a commit that adds an email address to any text
file, or adds a spreadsheet at all (binary, so a scan can't see inside; the team's workbooks hold
contacts). Masked forms (`h***@domain.com`) pass. Tested both refusals and the pass before committing.
Activated locally with `git config core.hooksPath .githooks`, which a fresh clone must repeat.

Not covered by the hook: commit METADATA carries the author's address. Resolved by D17. (The hook's
first real refusal was this entry, which quoted two addresses verbatim.)

**D17. Commits in this repo are authored with Nicole's GitHub noreply address.** Nicole.
Set with a repo-local `git config user.email`, looked up from GitHub (her user id plus login at GitHub's
noreply domain), the same one her serp-tracker commits already use. Her global git identity is unchanged,
so other repos are unaffected. The 7 earlier commits keep her work address: rewriting history was not
asked for. Like the hook, this is per-clone; a fresh clone needs the same `git config user.email`.

---

## 2026-10-09 (later) — Contacts for the curated list

**D15. The team's curated list is sourced as curated.** Nicole.
The team cut 115 to 100 (`briefs/affiliate-seo-creators/shortlist.csv`, saved as the record of the gate).
Claude flagged 16 more: 4 homonyms (the *Otherland* novel and play, a Delaware student paper's Mosaic
café), 6 shop or brand blogs, 6 media or listicle sites. Nicole: "just source from the first tab". All 100
were sourced; the flags stand in this entry, not in the data.

### The run
`find_contacts.py --from-sites`, new: the site's own contact, about and home pages first (free), Hunter
domain search for the rest in the team's order, every address verified.
- 41 of 100 publish an address themselves; 31 verified usable, 5 accept-all for Nicole, 5 not usable.
- 27 Hunter searches (Bellwether's monthly cap): 17 usable addresses, 10 with nothing usable.
- **48 ready to send, 5 to decide, 15 not usable, 32 waiting.** Addresses in `data/contacts.csv`
  (gitignored); `outputs/.../contacts-summary.csv` has none.

### Retracted: "empty Hunter searches are free"
The first run printed "empty searches charged: 0 of 10". Wrong on both counts. (1) Those ten were not all
empty: newmodernmom.com returned an address in the morning's test, and this time the contact rule
filtered it out (the site check counts 2 authors there, so D14's one-person exception did not apply);
the code logged that as "found nothing". (2) Hunter's counter had reached the plan limit, and a counter
at its limit cannot move, so zero deltas proved nothing. Fixed: the source now says "found nothing",
"found N, none fit the contact rule", or "error", and charging is only measured below the limit. The
question stays open.

### Unexplained Hunter usage
After the run Hunter showed 50/50 searches and 100/100 verifications used until Oct 20. Bellwether's
ledger accounts for 30 searches and 63 verifications this cycle (3 + 27; 5 + 58). The rest was not this
pipeline. The `serp-tracker` session, open at the time, has close-demo's Hunter scripts. The 32 waiting
sites therefore wait for Hunter's reset on Oct 20, whatever Bellwether's own cap says.

### Fixed along the way
- `_budget.py`: caps per unit. Hunter searches and verifications were summed against one cap, so a
  verification run would have eaten the search budget. `budgets.json` gains
  `monthly_verification_cap: 100`.
- `site_profile.py`: the about-page finder had returned a plugin stylesheet as mybalancedspace.com's
  about page; asset paths are skipped.

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
