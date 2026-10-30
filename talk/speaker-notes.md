# Speaker notes — partner discovery, 10 minutes

**Show:** `talk/walkthrough.md` on screen. Switch to Claude Code (open in `bellwether-2.0/`) at the
cues below. These notes are for you; nobody else sees them.
**Audience:** peer marketers · **Updated:** 2026-10-29. The numbers come from the
affiliate-seo-creators run and were checked against the output files.

About 750 spoken words: six minutes of talking, eight or nine minutes with the switches and pauses.
Leave the slack alone; nerves and laughs fill it.

> Automate everything up to the inbox. The human owns the inbox.

---

## Run of show

| Time | Section of `walkthrough.md` | Screen |
| --- | --- | --- |
| 0:00 | The objective | md |
| 0:45 | What we're going to do | md |
| 1:30 | 1. Seeds | md |
| 2:30 | 2. Run the seeds | **Claude Code**, then back to md |
| 5:30 | 3. Curate | md |
| 6:15 | 4. Fetch emails | md |
| 7:45 | 5. Pitch | md |
| 8:30 | What it cost, and close | md |

---

## Script

Say it, don't read it. Land the **bold** lines; everything else you can paraphrase.

**0:00 · The objective**
Here's what we're going to do. Find the creator sites that already review brands like ours. Get a
verified email for each one. Draft a pitch built on what they actually wrote.
**Automate everything up to the inbox. The human owns the inbox.**

**0:45 · What we're going to do**
Five steps. Most of the time it's a command in Claude Code. Watch the last column: a person decides
at every step that matters, and the send is mine alone.
Why bother? My team did 95 brands by hand, across 10 categories. It took from June 2 to July 7:
Google it, open the tabs, paste domains into a sheet, guess the email. This is how we did the other 64.

**1:30 · 1. Seeds**
The seeds are 159 DTC brands across 19 categories, each searched as "[brand] review."
**I'm not trying to rank for these. I'm using them to find who already ranks.** A site that reviewed
Caraway is a good bet for the next cookware brand.
The team's spreadsheet goes in with one command, and nothing runs until a person approves the seed.

**2:30 · 2. Run the seeds** — *switch to Claude Code*
Type: `/run-seeds affiliate-seo-creators --dry-run`
While it prints: **"It tells me what a run will cost before it spends anything."**
- *In October* it ends in REFUSED, because this month's search cap is used up. Say: "And it refuses.
  The searches my client rank checks depend on come out of the same account."
- *In November* it prints the plan and "nothing spent." Say: "Eight searches. Nothing spent until I
  say so."

*Back to the md.* One command does three jobs.
**Scan.** 125 Google searches, page one only. One day, on a free plan.
**Filter.** 281 results were thrown out, each with a reason. Here's my favourite. I searched "Mosaic
Foods review." Mosaic makes frozen meals. The top result was Indeed Canada: employee reviews for a
different company called Mosaic. **Wrong Mosaic. Wrong kind of review. Wrong country.** For one brand in
five, Google decided "[brand] review" meant "what's it like to work there."
**The filters are the product.** Anyone can pull a SERP. What's worth having is the list of what you
threw out, and why.
**Sort.** The team said: creator blogs, not nytimes.com. So it sorts every site into a tier, and it
doesn't guess. It reads the RSS feed for author names, the about page for "Hi, I'm," and it looks for
a ShopMy storefront.
It also checks whether ChatGPT and Claude's search crawlers are allowed in. 25 of the 208 block at
least one. **Blocking AI training and blocking AI search are different switches.**
**What still gets through:** Otherland makes candles. It kept a review of a London play called
*Otherland*, and a review of a fantasy novel. **It can tell a page is a review. It can't tell what's
being reviewed.** That's why the next step is a person.

**5:30 · 3. Curate**
The team picked 100 from the shortlist: 56 creator blogs and 43 niche review sites. This is the gate
that catches the play and the novel.

**6:15 · 4. Fetch emails**
The site's own pages first, Hunter second, verify always. No guessed addresses.
65 are verified. 6 are on domains that accept any address, so they can't be confirmed. That's a
judgment call. 29 have nothing usable.
37 of the addresses came free, from the site's own contact page.
**Two sites list an address on their own privacy page. Both bounce.** Verify always.
The emails go back into the team's own sheet, in the same row order, and no address ever goes to GitHub.

**7:45 · 5. Pitch**
The drafts are next. Each one starts from the review the site actually published, not a merge field.
**And the tool never sends.** Your reputation, the relationship, the last five percent of judgment:
that's the job.

**8:30 · What it cost, and close**
Zero dollars. Free tiers all the way.
**Automate everything up to the inbox. The human owns the inbox.**
**What stays human isn't what's left over. It's the part that carries the risk.**
Thank you.

---

## Numbers card (for questions)

| | |
| --- | --- |
| Brands / categories | 159 / 19 |
| Done by hand first | 95 brands, 10 categories, June 2 – July 7 |
| Pipeline searches | 125 (page 1 only), Oct 6 |
| Results dropped, with reasons | 281: brand's own site 76 · not a review 67 · retailer 58 · job sites 37 · directories 19 · forums 13 · app stores 6 · noise 5 |
| Review sites kept | 208 → 59 creator · 55 niche review · 29 media (set aside) · 65 check by hand |
| Team's curated list | 100 (56 creator blogs, 43 niche review sites, 1 to check) |
| AI search crawlers | 25 of 208 block at least one · of the curated 100: 97 allow both, 2 block, 1 unknown |
| AI training crawlers | 44 of 208 block one; 18 of those still allow AI search |
| Contacts | 71 of 100: 37 from the site's own pages, 34 from Hunter · 65 verified · 6 accept-all · 29 nothing usable |
| Spend | $0. SerpAPI 145 searches, Hunter 62 searches + 78 verifications, all free tiers |

## If they ask

- **"How long did it take?"** The scan took one day. Contacts took two passes, because Hunter's free tier
  resets on the 20th. The slow parts are the human gates, on purpose.
- **"Why not buy an influencer email database?"** I want the sites that reviewed the category this
  year, and an address verified this month.
- **"Does it send?"** No. It drafts. I send.
- **"Can I have it?"** It's Claude Code plus a handful of commands: create seeds, import seeds, run
  seeds, fetch emails.
- **"What about AI answers?"** Google rank tells you what a placement wins on the SERP. The crawler
  check tells you whether ChatGPT or Claude can even read the page. Whether they cite it is the next
  check.
- **Compliance:** the plan is a dedicated sending domain, never the client's primary, with an opt-out.
  Sending isn't built yet, so say "the plan is."

## Before you go on

- [ ] Open Claude Code **in `bellwether-2.0/`**. That's what loads `/run-seeds` and the other
      commands. Run the dry run once that morning so you've seen what it prints.
- [ ] Open `talk/walkthrough.md` in a separate window, so you can switch with one keystroke.
- [ ] Don't type `/api-check` on stage: the Close line shows a red FAIL (the CRM key is pending).
- [ ] If you show any spreadsheet: hide the `published email (unverified)` column in
      `creator-shortlist.xlsx`. Never open `data/contacts.csv` or a "(with emails)" file on screen.
- [ ] Say the objective out loud three times. If the first 45 seconds go well, the rest follows.
- [ ] One timed run-through. If it runs long, cut the Otherland paragraph first.

## Cut, and why

- **Motions** (editorial, referral partner, marketplace): a whole idea that doesn't fit in ten minutes.
- **Plural vs singular queries, and the off-query guard:** good stories, too long.
- **The Covey demo:** see `old-15min-draft.md`. Keep it as a backup if a client-safe live run is ever
  needed.
