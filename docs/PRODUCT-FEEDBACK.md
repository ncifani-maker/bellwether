# Product feedback log
*What client review taught us about the pipeline. Each entry: what we got wrong, why, and what changed.*

---

## 2026-07-31 — Rarity7 shortlist review (Owen, via Nicole)

First real client pass over a generated shortlist. 25 targets reviewed. **Three were wrong because of
faulty reasoning, not bad data** — those are the valuable ones.

### 1. We never asked the client what relationships they already have — and that's the top signal

Every enthusiastic yes traced to a pre-existing relationship the pipeline had no way to know:

| Target | What we saw | What Owen knew |
| --- | --- | --- |
| greysheet.com | "bot-blocked, unverified, known publisher" | *They email our offers to their ~100k list.* Easiest win in the set |
| forums.collectors.com | "community venue, probe blocked" | *Owen already posts there regularly* |
| money.org | "trade body, has a blog" | *ANA Life Member — Owen can write for them* |

Meanwhile the coldest targets (Chubb, Cabrella) were rejected precisely *because* no relationship existed.
Relationship strength predicted the verdict better than rank, fit score, or seed coverage — all of which we
compute, none of which decided anything.

**Changed:** `qualify_targets.py` now reads a client-supplied `relationships.csv`
(`domain,relationship,strength,detail`), joins it onto every row, and **sorts by relationship strength
first**. When the file is missing it prints a warning saying so. Rarity7's is filled in from this review.

**Process change:** relationship intake belongs at the *start* of a client engagement, before research —
it's a 15-minute conversation that reorders the entire output.

### 2. A commercial relationship is not editorial access

We scored PCGS / NGC / PMG / CAC as "**warmest pitch available**" because Rarity7 is an authorized dealer of
all four. Owen rejected all four: *"we're listed in their dealer directory but otherwise not a good fit —
big grading company, hard to get on their content radar without a PR team."* He used to work at PCGS.

Being in a company's dealer directory is a transactional fact. Their content team is a separate, gatekept
function. We collapsed the two and produced our most confident wrong recommendation of the batch.

**Changed:** `relationships.csv` distinguishes `vendor-active` / `presence-active` / `member` (real access)
from `listing-only` (transactional, weak). The four grading services are marked `listing-only, weak`.

### 3. "Competitor" is category-specific, and we defined it too narrowly

We defined competitor as *sells the client's product*, so auction houses became `referral-partner`. Owen:
*"auction site — not a good fit (competitor even though friendly)."* In collectibles the competition is
**two-sided** — auction houses compete for the same *consignments*, i.e. the supply side, not just buyers.

**Lesson:** the competitor test must be defined per vertical at client intake, covering both sides of the
transaction. Ask "who else is trying to get the same inventory?" not just "who sells the same thing?"

### 4. A verified blog says nothing about whether a site is real

Owen flagged two targets as *"vibe-coded"* AI/SEO sites. Every structural check we ran — has `/news`, no
cart, ranks on page 1 — passed them. That's now a common failure mode: generated SEO sites are structurally
indistinguishable from publications.

**Changed:** `qualify_targets.py` added a legitimacy pass scoring things that are harder to fake —
domain registration age (RDAP, free, no key), author bylines, spread of publication dates — emitting
`legitimacy: established | thin | suspect`. It **independently confirmed Owen's instinct**:
`uscoinshows.com` and `findcoinshows.com` are both registered *this year*.

### 5. Pay-to-play is a different motion, not a worse pitch

`uscoinshows.com` reached out to Owen already: *"pay to play but maybe worth it?"* Paid placement isn't
earned media — it's advertising, and it needs a budget decision from the client rather than an outreach
sequence. Filing it under `editorial-outreach` would have sent a pitch to someone waiting for an invoice.

**Changed:** pay-to-play marker detection (`advertise with us`, `sponsored post`, `media kit`, `submit your
listing`) and a new `paid-placement` motion with a `4-Budget call` priority. Flagged
uscoinshows, findcoinshows, financialpoise, money.org, chubb.

### 6. Same-operator and same-entity duplicates inflate the list

Owen on findcoinshows: *"Similar (same?) as above."* He was probably right — both registered this year, both
pay-to-play. Separately, `money.org` and `blog.money.org` are **one organization and one pitch**, but we
listed them as two targets, which double-counts the opportunity.

**Changed:** analytics/tag-ID fingerprinting (`UA-`, `G-`, `GTM-`) clusters domains under one operator via
a `same_operator_as` column — it caught `learn.apmex.com` ↔ `apmex.com`. It did *not* catch
uscoinshows/findcoinshows, so this needs a second signal (shared registrar/nameserver, template hash).
**Open.** Subdomain-to-parent collapsing is also still manual.

### 7. Organizational scale has to match

Chubb: *"would be a big corporate thing. Probably not a good fit for now."* A two-person dealer cannot
transact with a multinational insurer's marketing org. We have no scale-fit dimension; relationship strength
is currently the proxy. **Open.**

### 8. "Worth researching more" ×4 means qualification stopped too early

Four targets got that response — meaning we handed the client homework instead of a decision. The legitimacy
signals now answer part of it (coinsite.com has 3 bylines across 7 years; coinvalues.com has none in 27
years), but the unanswered question is **"do they accept contributed articles?"** — which is what the ask
actually is for most of these.

**Open:** detect contribution surfaces (`write for us`, `contribute`, `editorial guidelines`, submission
forms) and surface them as the concrete ask.

---

### Recurring theme

The pipeline is good at **discovery** (who ranks) and increasingly good at **verification** (do they publish,
are they real, do they sell). It is blind to **access** — who the client already knows, who returns their
calls, who they've worked with. That's the highest-value input and it can only come from the client.
It should be collected first, not reverse-engineered from a review pass.
