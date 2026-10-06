# Partner discovery lane: build plan

**Owner:** Nicole · NAC Worldwide · **Date:** Sept 18, 2026 · **Status:** Phase 0 and the two scans built, Sept 23
**Parent:** `PRD.md` §7.2 lists "SERP and backlink discovery" as a Bellwether source. This plan makes it real.

> **Built so far (2026-09-23).** Keys consolidated into `nac-worldwide/.env`, with `scripts/_keys.py`, `scripts/_budget.py`, `config/budgets.json` and the `data/api-usage.csv` ledger. Commands live: `/api-check`, `/serp-scan`, `/yt-scan`. `/yt-scan` ran end to end on Rarity7. Decisions 1–3 in §9 are settled; 4–6 are open. Next: `/seed-list` and `/score-partners` (Phase 2).

---

## 1. What this adds

Right now Bellwether only finds YouTube creators. This plan adds a web-partner lane: review sites, roundups, independent blogs and complementary tools, the partners described in the *Partnerships at Scale* one-sheet. Both lanes run from one brief and use the same score, the same review gates and the same `links.csv` → `results.csv` loop. That lets a blog and a Shorts creator compete for the same slate on projected CPA.

Most of this has already been built and run live. It just lives in the wrong place:

| Piece | Where it lives today | State |
| --- | --- | --- |
| YouTube scan | Bellwether: `/scout`, `farm_flag.py`, `donor_trail.py`, `run_study.py` | Working. Used today on rare coins (`outputs/_scratch/`) |
| SERP scan → score → Hunter → hooks | `~/Desktop/serp-tracker/close-demo/scripts/`, run per client in `serp-tracker/clients/` | Run live for Close (40 sites, 29 verified contacts), Rarity7, NAC, dtc-reviews |
| Recruiting rules: target profile, hard ceiling, 4-email sequence, negotiation guardrails | `homeaglow/recruiting/AGENT-SYSTEM-PROMPT.md` | Prompt only, no tooling |
| API keys | YouTube: `~/.config/scout/.env` plus 3 copies. Everything else: `serp-tracker/keys.txt` | Split across two places |

The one-sheet sells five steps. Four of them already exist but aren't connected, and none of them are in Bellwether yet.

## 2. The workflow

Five stages with a gate after each one. Every stage ends with the standard NAC review line.

| # | Stage | Agent | Command | API | Output | Gate |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Seeds | Scout | `/seed-list` | DataForSEO (volume, CPC) | `briefs/seeds/<brand>.csv` | **Nicole approves seeds** |
| 1a | SERP scan | Scout | `/serp-scan` | SerpAPI | `serp-domains.csv` + raw JSON | — |
| 1b | YouTube scan | Scout | `/yt-scan` | YouTube Data API | scout workbook + donor scan | — |
| 2 | Vet & score | Assessor | `/score-partners` | site probe (free), DataForSEO traffic | `<slate>-partner-shortlist.md` + CSV | **Nicole curates shortlist** |
| 3 | Verify contacts | Herald | `/find-contacts` | Hunter.io search + verify | `data/contacts.csv` | **Nicole approves contacts** |
| 4 | Draft pitches | Herald | `/draft-pitches` | none (Claude drafts in-session) | `<slate>-pitches.md` | **Nicole approves each pitch** |
| 5 | Send + log | Nicole, Ledger | `/log-outreach`, `/followups` | — | `data/outreach.csv`, `data/links.csv` | Nicole sends |

`/partner-run <brand>` runs the whole chain in order and stops at every gate. It can be resumed, so re-running it picks up at whichever gate is open.

Contact finding moves into Herald instead of becoming a fifth agent, because activation means finding the right person and writing to them. Herald's first step is verify, and its second is draft.

## 3. Commands

These are Claude Code skills. They live next to `/scout` in `nac-worldwide/.claude/skills/`. Any command that spends money sets `disable-model-invocation: true`, so it only runs when you type it and Claude can't spend credits on its own.

### The two scans

**`/serp-scan <brand> [--slate 2026-10] [--depth 20|50] [--dry-run]`**
1. Reads the rows marked `approved` in `briefs/seeds/<brand>.csv`. If none are approved, it refuses to run. That's the seed gate.
2. Prints the cost before spending anything (seeds × depth ÷ 10 searches) and asks first if it's over the threshold.
3. Queries SerpAPI with the tracker's params (google.com, desktop, San Francisco, non-personalized) and the tracker's noise filter. It keeps close-demo's retry for contaminated SerpAPI pages.
4. Drops any domain that's already in `creators.csv` or `outreach.csv` for this brand, on the brief's exclusion list, or above the hard ceiling. Every drop is logged with a reason.
5. Writes `outputs/<brand>/<slate>/serp-results.json` (raw) and `serp-domains.csv` (one row per domain: best rank, seeds covered, ranking URLs).
6. Reports the top domains by seeds covered, searches spent and what got filtered. Next step: `/score-partners`.

**`/yt-scan <brand> "<topic>" [scout flags]`** or **`/yt-scan <brand> --study <config.json>`**
1. Takes defaults from the brief (Shorts lane → `--length short`).
2. Runs `scout.py` and writes to `outputs/<brand>/<slate>/`, not the folder root.
3. Runs `farm_flag.py` on the workbook.
4. Runs the geography screen on Channel Country against the brief's geo target. This happens **before** the donor scan, per CLAUDE.md.
5. Runs `donor_trail.py --from-scout … --donors briefs/donors/<brand>.json --depth 90`.
6. Adds the survivors to `data/creators.csv` (`platform=youtube`, `source=yt-scan:<topic>`).
7. Reports the top channels, farm and geo drops, donor hits, and quota used (search calls out of 100/day, units out of 10,000/day).

`--study` hands off to `run_study.py` for multi-topic runs, which are cached and can be resumed.

### The rest of the chain

| Command | What it does | Spends |
| --- | --- | --- |
| `/seed-list <brand>` | Drafts seeds in close-demo's four buckets (commercial/comparison, category/how-to, brand, vertical) from the brief, client site and competitors. Validates volume and CPC with DataForSEO. Writes them as `proposed`. | DataForSEO, cents |
| `/score-partners <brand>` | Probes each site, applies the hard filters, scores on the six-dimension rubric, tags the motion and computes projected CPA (§4). | Free, plus optional DataForSEO traffic estimate |
| `/find-contacts <brand>` | For shortlisted rows only: site's own contact page → Hunter search → Hunter verify (§5). Shows the credit estimate first. | Hunter credits |
| `/draft-pitches <brand>` | Drafts the Day 1 email plus Day 5/12/19 follow-ups for each approved contact, using the motion, the brief's offer and the brief's voice. Uses `_shared/skills/cold-email` and the recruiting agent's email rules. Writes a numbered review file. You reply `APPROVE 1,3,4` / `REVISE 2 [note]`. | None |
| `/partner-run <brand>` | Runs the full chain, gate by gate. | Whatever each stage spends |

### Running it day to day

| Command | What it does |
| --- | --- |
| `/pipeline [brand]` | Status board: count per stage, **what's waiting on you**, follow-ups due today, API balances. |
| `/followups` | Lists anyone due for a Day 5/12/19 follow-up based on `sent_at` and drafts those follow-ups for approval. |
| `/log-outreach <brand> sent 1,3 \| replied 4 \| placed 4` | Records status in `outreach.csv`. On `placed`, asks for the tracker link and logs it in `links.csv` first, because no link goes out until it's logged. |
| `/negotiate <brand>` | Paste in their reply. Returns the recruiting agent's Stage 4 analysis against the brief's guardrails and a draft reply. Anything outside the guardrails gets escalated, never countered. |
| `/api-check` | Checks every key: present, valid, remaining balance. Uses zero-cost account endpoints only and never prints a key. |

## 4. Scoring web partners on the Bellwether rubric

Sites use the same six dimensions and default weights as PRD §7.3, so a blog and a creator get a comparable score. Each score carries a high, medium or low confidence band, as in PRD-mcp §5.

| Dimension (weight) | Web-partner evidence |
| --- | --- |
| Conversion-profile fit (30) | Ranks for buyer-intent seeds (the commercial/comparison bucket counts most). Page format is a review, roundup or comparison. Number of seeds covered. |
| Audience purchase behavior (25) | **Affiliate-network fingerprint** on the ranking page: Impact, ShareASale, CJ, Awin, Skimlinks, Amazon, LTK/ShopMy link patterns. Donor-brand mentions from `briefs/donors/<brand>.json`. Disclosure language. |
| Audience-ICP match (20) | Niche vs the brief's ICP, US signals, resemblance to the brief's reference sites. |
| Format nativeness (10) | Actually publishes (bylines, dated posts, an editorial surface). SERP position. |
| Price discipline (10) | Projected CPA at the brief's offer (see below). |
| Responsiveness (5) | Last post within 90 days, a work-with-us page, a verified contact found. |

The affiliate-network fingerprint is the site-level version of the donor trail and the one genuinely new signal. A site already carrying Impact links is one click from joining a program on Impact, like Homeaglow's. `qualify_targets.py` doesn't do this today.

**Projected CPA for a site.** This keeps the core math. For a flat fee: effective CPM = fee ÷ (estimated page views over the attribution window ÷ 1,000), then CPA = CPM ÷ (10 × sign-up rate %). Page views come from DataForSEO's traffic estimate for the ranking URL. Pure CPA offers pass price discipline by construction. The per-page-view sign-up rates (median and optimistic) are a brief field, separate from the Shorts rates.

**Hard filters** reject a site before it's scored, and the reason is logged. They come from the recruiting agent's ceiling but live as brief fields, so they aren't hardcoded to Homeaglow:
- media companies and sites with editorial teams
- sites above the DR ceiling, or with a rate card above the cap
- agencies and multi-creator networks
- content farms and PBNs (`qualify_targets.py` already catches shared analytics IDs through `same_operator_as`)
- sites that sell what the client sells
- sites with no post in the last 90 days
- existing program partners (the brief's exclusion file, e.g. an Impact partner export)

**Motion** comes from close-demo's taxonomy plus one new motion. It decides both who you contact and what you ask for:

| Motion | Ask |
| --- | --- |
| `editorial-outreach` | Inclusion or refresh in coverage (editor) |
| `affiliate-recruit` *(new)* | Join the program on the brief's offer, e.g. Homeaglow's $500 flat / $7 CPA |
| `referral-partner` | Co-marketing or mutual referral (founder/BD) |
| `profile-claim`, `marketplace` | Not an email campaign; handled separately |
| `off-core` | Parked, with a reason |

close-demo learned that a low fit score usually means the wrong motion, not a reject.

**DR:** there's no Ahrefs API today. The Ahrefs connector is installed but needs authorizing in claude.ai connector settings. Until then, `/score-partners` uses the recruiting agent's DR proxy signals and labels the result as an estimate.

## 5. Contacts: the Hunter step

The order, cheapest and most defensible first:
1. **The site's own contact, about or work-with-us page.** Free, and it's the business contact the owner chose to publish.
2. **Hunter domain search**, filtered to role addresses (editor@, hello@, partnerships@) or named people whose Hunter position is founder, owner, editor, partnerships or marketing.
3. **Hunter verifier on every address** from steps 1 and 2, including addresses found on the site. close-demo's verify gate caught a 99-confidence address that would have bounced.

| Verifier result | What happens |
| --- | --- |
| `valid` | Usable |
| `accept_all` (catch-all domain) | Flagged and you decide. This is common on small blogs running Google Workspace. |
| `unknown`, `risky` | Use the contact form instead |
| `invalid` | Dropped |

Never used:
- pattern-guessed addresses
- personal addresses the owner didn't publish
- the captcha-gated email on a YouTube About page (you can reveal that one by hand; the agent never does)

For YouTube creators, the steps are:
1. A business email in the channel or video descriptions (`donor_trail.py` already reads full descriptions).
2. Hunter on the creator's own website.
3. The management contact.

**Rule conflict to settle before Phase 3.** Bellwether's CLAUDE.md says "no email scraping." Hunter's index is built by crawling the web, so the rule needs to say precisely what's allowed. Proposed wording:

> Contacts come only from the partner's own published pages or Hunter.io, restricted to role addresses and business roles. Every address is Hunter-verified before a pitch is drafted against it. No guessed addresses, no harvesting beyond the target's own domain, no captcha-gated sources.

## 6. APIs and keys

| API | Key | Lives now | Also used by | Bellwether use | Spend unit |
| --- | --- | --- | --- | --- | --- |
| YouTube Data v3 | `YOUTUBE_API_KEY` | `~/.config/scout/.env`, plus copies in `nac-worldwide/.env`, `.scout.env`, `serp-tracker/keys.txt` | — | `/yt-scan` | Free, 10,000 units/day (search = 100) |
| SerpAPI | `SERP_API_KEY` | `serp-tracker/keys.txt`, Render | **SERP Tracker daily rank checks for PR clients** | `/serp-scan` | 1 search per 10 results, monthly plan |
| DataForSEO | `DATAFORSEO_LOGIN`, `_PASSWORD` | `serp-tracker/keys.txt` | close-demo | Seed volume/CPC, page traffic | Pay per request |
| Hunter.io | `HUNTER_API_KEY` | `serp-tracker/keys.txt` | close-demo | `/find-contacts` | Monthly credits |
| Anthropic | `ANTHROPIC_API_KEY` | `keys.txt`, Render | SERP Tracker AEO | Optional AEO citation check. Drafting doesn't need it. | Tokens |
| OpenAI | `OPENAI_API_KEY` | `keys.txt`, Render | SERP Tracker AEO | Optional ChatGPT citation check | Tokens. `keys.txt` notes an earlier key returned 401 |
| Close | `CLOSE_API_KEY` | `keys.txt` | close-demo | None. Close is that client's CRM only. | — |

**What the accounts actually hold** (measured 2026-09-23 with `/api-check`, and it changes the sizing):

| Account | Reality |
| --- | --- |
| SerpAPI | **Free plan. 250 searches/month, 213 left, 37 used.** A 15-seed scan at depth 20 costs 30. That is roughly seven scans a month, shared with the tracker. |
| Hunter | **Free. 50 searches + 100 verifications/month**, resets the 20th. close-demo's 29 contacts would have eaten most of a month. |
| DataForSEO | **$0.54 left.** Enough for seed validation, not for traffic estimates. Needs a top-up before `/score-partners` uses them. |
| YouTube | Free, 10,000 units/day. Not the constraint. |
| Anthropic, OpenAI | Valid. |
| Close | **401 — key rejected.** Only close-demo needs it; nothing in Bellwether does. |

What changed (decided 2026-09-23):
1. **One key file: `nac-worldwide/.env`** (mode 600), inside the folder every project already lives in, so any of them can reference it. Scripts read it through `scripts/_keys.py`: env var → `NAC_KEYS_FILE` → `nac-worldwide/.env` → `~/.config/scout/.env`. The SERP Tracker keeps its own `keys.txt` and Render env and isn't touched.
2. **The duplicates are gone.** `nac-worldwide/.scout.env` was deleted after confirming its key matched, and `~/.config/scout/.env` is now a symlink to the canonical file, so the vendored tools resolve unchanged. It does sit in iCloud — that's the trade for it being reachable from every project and from Nimbalyst, which only sees `Documents/`.
3. **Standard library only.** Your `python3` is 3.7.2, which has openpyxl but not `requests`. Homebrew's 3.14 has neither. Bellwether's scripts already use `urllib` only, so the close-demo ports switch to `urllib` too and every command runs on plain `python3` with no pip step.
4. **Spend guard, in `config/budgets.json`.** Three checks before the first call: a **reserve** (never leave the account below 80 searches, so the tracker's client rank checks keep running), a **monthly cap** (100 searches of Bellwether's own, counted from `data/api-usage.csv`), and a **confirm threshold** (over 20 searches the command stops, prints the plan and spends nothing until it's re-run with `--yes`). Hunter: 30 searches/month, confirm above 10. DataForSEO: confirm above $0.25.
5. **SerpAPI stays the provider, capped** (decided 2026-09-23). DataForSEO's SERP endpoint stays the fallback if the cap starts biting; at $0.54 of balance it isn't a real alternative today anyway.

## 7. Files

**New**
- `scripts/_keys.py`, `serp_scan.py` (from close-demo `serp_research.py`), `site_probe.py` (from `qualify_targets.py`, plus the network fingerprint), `score_partners.py` (from `score_opportunities.py`, plus the rubric), `find_contacts.py` (from `hunter_enrich.py`, `find_emails.py` and `find_emails_web.py`), `outreach_log.py`. Each ported file names its close-demo source and port date in its docstring, the same way `vendor/` pins its commit.
- `briefs/seeds/<brand>.csv`: `keyword,intent,bucket,priority,status,added_by,date`
- A `## Partner lane` section in each brief: offer per motion, per-page-view sign-up rates, CPA threshold, ceiling (DR, rate card), exclusion file, pitch voice, sender. The refuse-to-run rule applies: no offer, threshold or conversion event means no scan.
- `data/sites.csv`: site-only probe fields keyed by `creator_id` (publishes, sells, networks, donor hits, traffic estimate, DR estimate, `same_operator_as`, last post)
- `data/contacts.csv`: **gitignored**, because it holds PII
- `data/outreach.csv`: one row per pitch (`creator_id, contact_id, motion, step, drafted_at, approved_at, sent_at, reply, status`)
- `agents/scout.md`, `assessor.md`, `herald.md` (`agents/` is empty today)
- The skills in `nac-worldwide/.claude/skills/`

**Changed**
- `data/creators.csv`: sites become rows with `platform=web`, `handle=domain`. With the same score columns there's one ranking across both lanes, and `links.csv` and `results.csv` work unchanged.
- `CLAUDE.md`: tooling table and the contact rule
- `PRD.md` §7.2 (the SERP source is live), §7.5 (contact step), §8 (new files)
- `.gitignore`: add `data/contacts.csv`

**Not changed:** `nacww_serp_tracker.py` stays read-only. close-demo stays as the Close sandbox; its scripts are the port source, not a dependency.

## 8. Build order

| Phase | Scope | Done when |
| --- | --- | --- |
| 0 | Key file, `_keys.py`, `/api-check` | Every key is confirmed working, with real balances for SerpAPI, Hunter and DataForSEO |
| 1 | `/yt-scan`, `/serp-scan`, `/pipeline` | Both scans run from Claude Code on one brief |
| 2 | `/seed-list`, `/score-partners` | Partner shortlist on the same score as creators |
| 3 | `/find-contacts` *(after the §5 rule decision)* | Verified contacts for a shortlist |
| 4 | `/draft-pitches`, `/log-outreach`, `/followups`, `/negotiate`, `/partner-run` | End-to-end run with every gate |
| 5 | PRD, CLAUDE.md, `agents/` | The docs match what actually runs |

`/yt-scan` comes first because it serves the Sept 21–30 milestone: the first Homeaglow longlist for the bake-off.

**Pilot on Rarity7.** It already has approved seeds, a scored and client-reviewed shortlist in `serp-tracker/clients/rarity7/`, and today's YouTube scout run. Re-running it through the new commands gives a before/after check against answers you already trust.

## 9. Decisions

1. ~~**Contact rule wording** (§5).~~ **Settled 2026-09-23: Hunter approved.** The wording in §5 is now in `CLAUDE.md`, replacing the blanket "no email scraping".
2. ~~**Key file location.**~~ **Settled: `nac-worldwide/.env`,** one file, reachable from any project. Duplicates removed.
3. ~~**SerpAPI or DataForSEO.**~~ **Settled: SerpAPI, capped** — see §6.

Still open:

4. **Pilot brand:** Rarity7 first, then Homeaglow's site lane?
5. **`serp-tracker/clients/`** (adbliss, nac-worldwide, rarity7): move into Bellwether briefs, or leave them where they are?
6. **Send path:** copy-paste into Mailspring (default), or export approved pitches as `mailto:` links?
