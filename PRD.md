# Bellwether — Product Requirements Document

**Owner:** Nicole · NAC Worldwide · **Version:** draft · **Date:** Oct 6, 2026
**Status:** Draft for build. Decisions behind this document are logged in `CHANGELOG.md`.
**Predecessors:** `../bellwether-1.0/` (creator discovery, YouTube lane, key and spend tooling) and
`~/Desktop/serp-tracker/close-demo/` (earned-media pipeline from seeds to Close leads). Both are read-only
reference. Bellwether copies from them and never edits or deletes anything in either folder.

---

## 1. Summary

Bellwether is one pipeline that takes a brand brief and ends with verified contacts loaded into Close,
approved copy armed, and results the client can see. It merges the two halves NAC has already built:

- **close-demo** proved the back half end to end for one client: seeds → SERP research → opportunities
  qualified by motion → Hunter-verified contacts → draft leads in Close → sequences in the client's voice.
- **Bellwether 1.0** built the front half and the plumbing: a YouTube creator lane (scout, geo screen,
  donor trail, farm flag), a SerpAPI web lane with spend caps, a contact finder that verifies every address,
  one key file, a budget file and a usage ledger.

Bellwether makes close-demo's pipeline the spine, adds YouTube as a second discovery lane feeding the same
opportunity list, and makes every brand a brief file rather than code. The first brand through it is
Close.com, rerun to prove the merge lost nothing.

> **The rule carried forward from both:** automate everything up to the inbox. The human owns the inbox.

## 2. Problem

Both predecessors work, but neither is a product NAC can run for a second client without rework:

- close-demo is hardcoded to one client: a Close.com brand-voice skill, Close.com notes in the scripts,
  keys in the serp-tracker's `keys.txt`, and no spend caps.
- Bellwether 1.0 finds creators and web partners but stops at contacts. Drafting, arming sends and
  logging results (Herald and Ledger) were never built. Its skills hardcode the `bellwether/` path, so the
  rename to `bellwether-1.0/` broke `/yt-scan`, `/serp-scan`, `/find-contacts` and `/scout`.
- The two do the same jobs twice: two SERP scripts, three contact finders, two key stores, two storage
  schemas.

## 3. Users

**Primary:** Nicole, as campaign owner. Approves seeds, shortlists, contacts and copy, and presses send.
**Secondary:** the pipeline agent, which does the research, scoring, enrichment, drafting and data entry,
and stops at every gate.
**Client-facing:** the brand, which sees results through the SERP Tracker (§9), never through the
pipeline's working files.

## 4. Goals and non-goals

**Goals**

1. One brief in, a scored shortlist across both lanes out, with a verified contact for each approved
   target and a draft lead in Close.
2. Running a new brand is a new brief folder, not a code change. No company name appears in a script,
   skill, config or template file name.
3. Close.com runs through the merged pipeline first and reproduces the close-demo result (§11) before any other brand runs.
4. Every paid call is checked against `config/budgets.json` before it spends, and logged after.
5. Placements land in the SERP Tracker so the client can see rank and AI-citation results.

**Non-goals**

- Autonomous sending. Sequences are armed by the agent and fired by Nicole. Always.
- Changing the SERP Tracker. `nacww_serp_tracker.py` stays single-file and read-only from here.
- A web app, MCP server or creator-facing surface. Those stay on the 1.0 roadmap (`PRD-mcp.md`, §11a).
- Lanes beyond web and YouTube (newsletters, podcasts, LinkedIn).
- Replacing Google Sheets or Notion as system of record. CSV stays the store; the schema stays
  Notion-shaped.

## 5. The pipeline

```
brief + relationships (intake)
        │
seeds ── GATE 1: Nicole approves seeds
        │
        ├─► web lane:     serp_scan → domains  → qualify by motion + legitimacy ─┐
        └─► YouTube lane: yt_scan   → creators → geo → donor trail → farm flag ──┤
                                                                                 ▼
                           opportunities (lane + motion + score) ── GATE 2: Nicole curates shortlist
                                                                                 ▼
                           find_contacts (published first, Hunter second, verify always)
                                                                                 ── GATE 3: Nicole approves contacts
                                                                                 ▼
                           crm_sync → draft leads in Close → sequence copy per lane + motion
                                                                                 ── GATE 4: Nicole approves copy
                                                                                 ▼
                           SEND ── Nicole only
                                                                                 ▼
                           reply sync ← Close        placements → SERP Tracker (client view)
```

| # | Stage | Command | Paid API | Output | Gate |
| --- | --- | --- | --- | --- | --- |
| 0 | Intake | — | — | `briefs/<slug>/brief.md`, `relationships.csv` | Brief complete |
| 1 | Seeds | `/seed-list` | DataForSEO | `briefs/<slug>/seeds.csv` | **Seeds** |
| 2a | Web scan | `/serp-scan` | SerpAPI | `outputs/<slug>/<slate>/serp-domains.csv` | — |
| 2b | YouTube scan | `/yt-scan` | YouTube Data API | scout workbook + donor scan | — |
| 3 | Qualify + score | `/score` | DataForSEO (optional) | `data/opportunities.csv`, shortlist workbook | **Shortlist** |
| 4 | Contacts | `/find-contacts` | Hunter | `data/contacts.csv` | **Contacts** |
| 5 | Load CRM | `/crm-sync` | Close | Close draft leads, `close_lead_id` written back | — |
| 6 | Copy | `/draft-copy` | none | sequences per lane + motion, in the brief's voice | **Copy** |
| 7 | Send | Nicole, in Close | — | — | **Send (human only)** |
| 8 | Sync + results | `/crm-sync --pull`, tracker | Close | status back to `opportunities` / `contacts`; placements tracked | — |

Each stage ends with the NAC review line:
`→ Ready for review. Reply: APPROVE to proceed, REVISE [note] to adjust, NEXT to move to the next stage.`

## 6. Briefs: one per brand

A brand is a folder under `briefs/`, created from `briefs/_template/`. The folder slug is data chosen at
intake. Nothing in `scripts/`, `.claude/skills/`, `config/` or `agents/` is named after a company, and no
script refers to a brand by name.

```
briefs/<slug>/
  brief.md            what it sells, ICP, conversion event, asks by motion, exclusions, competitor test
  seeds.csv           seed keywords; only `approved` rows run (the seed gate)
  relationships.csv   domain,relationship,strength,detail — collected at intake, before research
  voice.md            brand voice for all copy drafted for this brand
  donors.json         YouTube lane only: which sponsor brands count as conversion evidence
```

**Required before anything runs:** a conversion event, the asks by motion, and hard exclusions. The
YouTube lane also needs the `bellwether:economics` block (CPM cap, sign-up rate assumptions, CPA
threshold); any command that prices a creator refuses to run while a value it needs is null.

**Intake comes first.** close-demo's client review (Rarity7, 2026-07-31) showed that existing relationships
predicted the client's verdict better than rank, fit or coverage. `relationships.csv` is collected in a
15-minute intake conversation before research, and qualification sorts by relationship strength first.
The brief also defines the competitor test for the vertical, covering both sides of the transaction
("who else wants the same inventory?", not just "who sells the same thing?").

## 7. Scoring: one table, two methods

Both lanes write to one `data/opportunities.csv` with a `lane` column (`web` | `youtube`). Each lane keeps
its own scoring method, because the evidence differs.

**Web lane: motion + legitimacy.** Every domain is qualified into a motion, which decides both the
contact to find and the message to write. A low fit score means the wrong motion, not "skip".

| Motion | What it is | Contact | The ask |
| --- | --- | --- | --- |
| `profile-claim` | Self-service review platforms | none, the brand's own team | Claim the profile, solicit reviews |
| `editorial-outreach` | Independent publishers, review media | an editor | Inclusion, or a refresh of existing coverage |
| `referral-partner` | Complementary tools, agencies, consultancies | founder / partnerships lead | Co-marketing, integration, referral |
| `paid-placement` | Pay-to-play sites | — | Budget call for the client, not a pitch |
| `marketplace` | Deal and listing marketplaces | listings team | List an offer |
| `off-core` | Irrelevant audience | — | Parked, documented |

The legitimacy pass (domain age via RDAP, bylines, publication-date spread) labels each site
`established` / `thin` / `suspect`. Same-operator detection (analytics tag IDs) groups duplicates.

**YouTube lane: Bellwether Score + projected CPA.** Six weighted dimensions (conversion-profile fit 30,
purchase behavior 25, ICP match 20, format nativeness 10, price discipline 10, responsiveness 5), with
projected CPA = CPM ÷ (10 × sign-up rate %) at the brief's median and optimistic rates. Creators get
`motion = creator-sponsorship`. The two hard rules from 1.0 still hold: never count sponsorships from the
channel-search page or from a truncated description, and screen geography before the donor scan.

## 8. Contacts and Close

- **Contacts:** published business or role addresses on the target's own pages first (free), Hunter domain
  search second, Hunter verification of every address always. No guessed addresses, no harvesting beyond
  the target's domain, no captcha-gated sources. On a site run by one person, that person's address on
  the site's own domain counts as the business contact (CHANGELOG D14). Motion decides the role searched for. `usable` decides:
  `valid` and self-published `webmail` yes; `accept_all` is Nicole's call; `unknown` and `risky` no.
- **No unverified address enters Close.** This is the quiet fourth gate.
- **Close is the CRM for every brand.** `scripts/crm_sync.py` creates draft leads, writes `close_lead_id`
  back to `data/contacts.csv`, and pulls status on sync. Lead creation and sequence arming are automated;
  the send is not. Each brand's leads carry a brand field so one Close account can hold several brands
  (see open question 1).
- **Compliance:** dedicated outreach domain per sending brand, never the brand's primary; CAN-SPAM
  address and working opt-out on every sequence; unsubscribes confirmed on in Close.

## 9. SERP Tracker: the client-facing view

The SERP Tracker (`serp.nac-worldwide.com`) stays. It is what the client sees: the rank of each earned
placement across the brand's keywords, and whether AI answer engines cite it.

- **Discovery** runs through `scripts/serp_scan.py` (SerpAPI with spend caps), not through the tracker.
- **Results** flow the other way: when a placement goes live, its URL is added to the brand's tracker
  workspace, and the tracker's CSV export (`/w/<slug>/export`) is read back into `data/results.csv`.
- **The tracker is never modified from here.** No routes, tables or templates are added to
  `nacww_serp_tracker.py`. Adding a URL through its own UI is an operator action, not a code change.
- **Shared quota.** SerpAPI is shared with the tracker's daily rank checks. `config/budgets.json` keeps a
  reserve (50 searches since CHANGELOG D11; 80 at creation) the pipeline will not spend below.

## 10. Architecture and sources

Agent-first, file-based, Python scripts with thin API clients. Open `bellwether-2.0/` directly: its skills
live in its own `.claude/skills/`, so nothing depends on opening the parent folder.

```
bellwether-2.0/
├── PRD.md  CLAUDE.md  CHANGELOG.md
├── .claude/skills/     api-check, seed-list, serp-scan, yt-scan, score, find-contacts, crm-sync, draft-copy, scout
├── agents/             Scout, Assessor, Herald, Ledger
├── briefs/_template/   brief.md, seeds.csv, relationships.csv, voice.md, donors.json
├── briefs/<slug>/      one per brand
├── config/budgets.json
├── scripts/            all pipeline scripts + _keys.py, _budget.py, _brief.py
├── data/               opportunities, contacts, links, results, api-usage (contacts gitignored: PII)
├── outputs/<slug>/     per-run outputs by slate
├── docs/               method docs carried forward
└── vendor/youtube-scout/
```

**Keys** stay in one file, `nac-worldwide/.env` (mode 600), read through `scripts/_keys.py`. Never printed,
never copied into the repo, never passed on a command line. The tracker keeps its own `keys.txt` and Render
env vars; a rotated key is changed in both.

**What comes from where (copy only):**

| Piece | Source | Treatment |
| --- | --- | --- |
| Pipeline stages, gates, motion taxonomy, storage schema, compliance rules | close-demo `CLAUDE.md`, `PRD.md` | Rewritten brand-neutral |
| `qualify_targets.py`, `score_opportunities.py`, `generate_hooks.py`, `dataforseo_kw.py`, `aeo_citations.py` | close-demo `scripts/` | Copied; switched from `keys.txt` to `_keys.py`; brand references moved into the brief |
| `close_sync.py` | close-demo `scripts/` | Copied as `crm_sync.py` |
| Close.com brand voice | close-demo `skills/close-brand-voice/` | Becomes the first brief's `voice.md`; one generic drafting skill reads any brief's voice |
| Close.com seeds, opportunities, contacts, saved SERP and Hunter results | close-demo `output/`, `state/` | Copied into the first brief and used for the replay (§11) |
| Lessons from client review | close-demo `PRODUCT-FEEDBACK.md` | Copied to `docs/`; relationships, legitimacy, paid-placement built in |
| `yt_scan.py`, `run_study.py`, `donor_trail.py`, `farm_flag.py`, `expand_candidates.py`, `vendor/youtube-scout/` | bellwether-1.0 | Copied as-is; `/scout` link re-pointed |
| `serp_scan.py`, `find_contacts.py`, `build_shortlist.py`, `build_workbook.py` | bellwether-1.0 | Copied; close-demo noise list and motion-based role targeting merged in |
| `_keys.py`, `_budget.py`, `_brief.py`, `api_check.py`, `config/budgets.json` | bellwether-1.0 | Copied; `_brief.py` reads the new brief folder layout |
| Skills | `nac-worldwide/.claude/skills/` | Copied into `bellwether-2.0/.claude/skills/` with paths fixed |
| `predictive-discovery-spec.md`, `partner-discovery-plan.md` | bellwether-1.0 `docs/` | Copied |

**Not carried forward:** close-demo's `serp_research.py` (replaced by `serp_scan.py`) and `hunter_enrich.py`,
`find_emails.py`, `find_emails_web.py` (replaced by `find_contacts.py`). They stay where they are.

## 11. Validation: Close.com first

Close.com is the first brief. The run proves the merge reproduces close-demo before any new brand runs.

**Replay (no spend).** Run stages 2a–4 against close-demo's saved SerpAPI and Hunter results.
Pass: the same 15 seeds produce the same 40 opportunities with the same motion split (5 profile-claim,
20 editorial, 12 referral-partner, 3 parked) and the 29 contacts match, including the catch of the
Geekflare address Hunter scored 99 and verification rejected.

**Live (small, budgeted).** With a fresh Close key: re-verify a sample of contacts, rerun a few seeds live
through `serp_scan`, create draft leads in Close and sync status back. Pass: no unverified address in
Close, every `close_lead_id` written back, spend matches `api-usage.csv`.

**YouTube lane.** One `/yt-scan` on a topic from the brief, with a donor list Nicole approves, writing
creators into the same opportunities table.

## 12. Build order

| Phase | Work | Done when |
| --- | --- | --- |
| 0 | Scaffold: copy the pieces in §10, fix paths, own git repo, skills and `/scout` working | `/api-check` and `/serp-scan --dry-run` run from `bellwether-2.0/` |
| 1 | Brand-neutral schema and brief layout; Close.com brief; replay | Replay passes (§11) |
| 2 | YouTube lane writes into `opportunities.csv` | Close.com YouTube scan lands in the shared table |
| 3 | Live Close.com run with the fresh key | Live pass (§11) |
| 4 | Activation: drafts per lane + motion, arming in Close, reply sync, placements into the tracker | One sequence armed and synced end to end; Nicole sends |
| 5 | Second brand as a config change | A new brief runs with no script edits |

## 13. Success metrics

| Metric | Target |
| --- | --- |
| Close.com replay matches close-demo | 40 opportunities, same motion split, 29 contacts |
| Contacts entering Close unverified | **0** |
| Sends fired without Nicole | **0** |
| Script, skill or config files named after a company | **0** |
| New brand onboarded with code changes | **0** |
| Paid runs that skipped the budget check | **0** |
| Opportunities with a verified contact | > 60% of shortlisted |
| Outreach-domain bounce rate | < 3% |

## 14. Open questions

1. **One Close account or one per brand?** One account with a brand field is simpler; separate accounts
   keep client data apart. Matters before a second real client.
2. **Sending domains.** Close.com was never given a dedicated outreach domain (close-demo open decision 4).
   Needed before the first send.
3. **Close.com YouTube donors.** Which sponsor brands count as conversion evidence for a sales CRM's
   audience is a brief decision, not the agent's.
4. **Close.com economics block.** The YouTube lane needs a conversion event, CPM cap and sign-up rate
   assumptions. close-demo never set these.
5. **Same-operator detection, scale fit, contribution surfaces.** Still open from close-demo's client
   review (items 6–8 in `docs/PRODUCT-FEEDBACK.md`).
6. **Bellwether 1.0's broken skills.** The `nac-worldwide/.claude/skills/` copies still point at
   `bellwether/`. Fix them in place, or retire them once this repo's work?
