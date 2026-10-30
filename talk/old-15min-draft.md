# Partner discovery, from search results to a sent pitch

**Speaker:** Nicole · **Audience:** peer marketers · **Length:** 15 minutes, her portion
**Demo:** live, on a fictional brand — **Covey**, DTC women's supplements · **Status:** draft flow, updated 2026-10-02

**The spine, said twice — once early, once at the end:**

> Automate everything up to the inbox. The human owns the inbox.

Three ideas, one live moment, and the failure modes in the open. Fifteen minutes will not hold more than that, and a peer audience will forgive a missing feature faster than a claim that does not survive a question.

---

## Beat sheet

| Time | Beat | On screen | The line that lands |
| --- | --- | --- | --- |
| 0:00 | **The pitch I almost sent** | A finished, personalized outreach email | "Hunter rated this address 99 out of 100. It was a guaranteed bounce. Everything in this talk is the checks between a good idea and that email." |
| 1:00 | **The problem** | Nothing, or a screenshot of a domains spreadsheet | Partner discovery is still: google it, skim it, paste domains in a sheet, guess the email. It is stale before you send. |
| 2:00 | **The spine** | One slide, the line only | Automate everything up to the inbox. Three gates stay human: the seed list, the copy, the send. |
| 2:30 | **Seeds: intent over volume** | `briefs/seeds/covey.csv` — 8 approved, 6 retired with reasons | "I am not trying to rank for these. I am using them to find who already ranks." So a seed is judged on what its SERP *contains*, not on volume. |
| 4:00 | **Retired seeds** *(same file, scroll down)* | The `note` column | Six retirements, each a real finding: *women's multivitamin reviews* is all retail, nothing to be included in. *How to choose a women's multivitamin* is health systems and medical publishers. And the brand seed — I invented this company, and the name is still taken three times over: FranklinCovey, a restaurant in Wilmington, and a shopping tool. A brand nobody has heard of has no SERP of its own to defend. |
| 5:00 | **LIVE: the scan** | Terminal, `/serp-scan` | Cost printed before a single call. The cap that refuses. Results aggregated per domain, not per link — "the unit of decision is a partner, not a URL." |
| 7:00 | **The SERP that lied** | The magnesium results, on screen | "magnesium glycinate benefits for women" returned UN Women, Wikipedia's *Woman*, healthcare.gov and the NCAA women's tournament. Ten results, none about magnesium. My own guard missed it: it checked that the *later* query words appeared, and "women" was everywhere. It now anchors on the query's most distinctive word — *glycinate* — and this SERP is the test case. |
| 8:00 | **The idea to steal: motions** | The motion table | A ranked domain is not a target, it is a *motion*. Profile-claim, editorial, referral-partner, marketplace. Same person, different ask, never the same email. **A low fit score usually means the wrong motion, not a reject.** |
| 10:00 | **Qualifying, briefly** | `qualified.csv`, two columns | Does it publish? Does it sell what we sell? Both checked by fetching the site, not guessed. Two things that made the naive version wrong: a cart is not a competitor, and a 403 is not a dead site. |
| 11:00 | **Contacts, and the gate** | `contacts.csv`, addresses masked | Published role address first. Hunter second. Verify always. Costs: Hunter's free tier is 50 searches and 100 verifications a month. Limit: this week, 8 of 12 creators published no address at all. No tool fixes that. |
| 12:30 | **Draft, don't send** | A real draft next to the evidence it came from | Personalized off the roundup they actually published, not a merge field. Then: the agent never sends. Reputation, relationships, and the last five percent of judgment is the job. |
| 13:30 | **Where it breaks** | Two screenshots | Marketplace brands show up in their *contractors'* descriptions — the supply side, the exact inverse of the audience. And a creator with 65 Instacart placements whose audience is gig workers, not people who hire them. The screens are the product. |
| 14:30 | **Close** | The spine line again | What stays human is not what is left over. It is the part that carries the risk. |

---

## The live section (5:00–8:00)

Three minutes, two commands, one fallback. Rehearse it once the morning of.

```bash
/serp-scan covey --limit 1 --depth 20
```

- Costs **2 SerpAPI searches**, about 20 seconds. Everything after the scan is shown from a previous run, on screen, labeled as such.
- Say the budget line out loud while it prints: "it tells me what it will cost before it spends anything, and it refuses if that would eat the quota my client rank checks depend on." That is the whole governance story in one sentence, for free.
- **Fallback if the network dies:** the full 14-seed run from 2026-10-02 is already on disk at `bellwether/outputs/covey/2026-10/`. Open it and keep talking. Do not debug on stage.

**Seed to use:** `--limit 1` takes the first approved row, deliberately ordered best-demo-first: **`best supplements for busy moms`**. It returns six genuine vehicles including theeverygirl.com's "15 Women Share The Supplements They Take" — a real roundup, the exact shape of thing you want to be in. To demo a different seed, move it to the top of the file.

---

## Cut, and why

Not in fifteen minutes. Keep these as backup slides for questions.

- **The AI-answer check** (which domains Claude and ChatGPT cite for the same buyer question). The freshest material and the hardest to explain in under three minutes. One sentence at 10:00 if it fits: "a Google rank tells you what the placement wins on the SERP; the citation check tells you whether that domain is in the set an LLM draws from." Full slide in the back pocket — this is the most likely question.
- **PBN detection** via shared analytics IDs across domains. One clause, not a beat.
- **The Angi / Agni Parthene homonym** — a Greek Orthodox chant outranking every real placement on an `#AngiPartner` search. Wonderful, but it is the YouTube lane and switching lanes mid-talk costs more than the laugh is worth. Use it in Q&A if someone asks about noise.
- **Compliance detail** (CAN-SPAM, dedicated sending domain, opt-out). Compress to the phrase "sent from a dedicated domain, never the client's primary" inside the contacts beat.
- **The scoring rubric weights.** Nobody remembers six weights from a slide.

---

## Prep checklist

- [x] `briefs/seeds/nac-worldwide.csv` ported into Bellwether (2026-09-30): 12 approved, 6 retired with their reasons in a `note` column. That file is a beat in the talk, not just an input.
- [x] `--limit N` on `serp_scan.py` (2026-09-30). Verified both ways: `--limit 1` plans 2 searches; the unlimited run plans 24 and stops at the confirm gate, which is the stumble this avoids.
- [ ] Pre-run artifacts open in tabs: `serp-domains.csv`, `opportunities.csv` (motion column visible), `qualified.csv`, `contacts.csv` with addresses masked.
- [ ] One real pitch draft, with the evidence it was built from beside it.
- [x] Demo brand written up: `briefs/covey.md`, labelled fictional.
- [ ] Check the SerpAPI balance the morning of (`/api-check`). Free tier is 250 a month and the tracker draws from the same pool.
- [ ] Decide the client-naming line (below) and make every screenshot match it.

## Open decisions

1. **Naming clients.** Settled for the demo: a fictional brand carries it, so no client pipeline goes on a screen. Still open for the *evidence* beats — the 40-sites/29-pitches numbers come from the Close run. Named, anonymized ("a CRM"), or left out?
2. **Whether the numbers go on a slide.** 15 seeds, 220 results, 40 qualified sites, 29 verified contacts, 29 drafts. Concrete and true, and it invites "how long did that take" — which is a good question to be asked if the answer is rehearsed.
3. **Where the talk ends.** On the method, or on an offer. For a peer room, the method. The offer belongs in the bio slide.
