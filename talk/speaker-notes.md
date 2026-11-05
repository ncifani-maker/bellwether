# Speaker notes · 10 min

For your phone. Updated Nov 5: Braise replays saved results, so every demo step takes seconds.

## Open with this

**Problem.** I used to work with other people who did the site and email hunting manually. Google the brand, open the tabs, paste the sites into a sheet, guess the email. My team did 95 brands that way, from June 2 to July 7: five weeks, and the list started going stale on day one.

**Solution.** Bellwether: a handful of commands in Claude Code. It finds the sites that already review brands like ours, sorts them, finds a verified email, and drafts the pitch. A person approves every step that spends or sends. The other 64 brands took one day of searching, and $0.

> **Keep the human in the loop. The human owns the inbox.**

---

## Have open

- `talk/walkthrough.md` on screen
- Claude Code, opened in `bellwether-2.0/`
- `briefs/braise/` in the file list

## Run of show

- **0:00** Problem → solution
- **0:30** Objective · md
- **1:00** What we're going to do · md
- **1:30** Seeds + Braise demo · Claude Code
- **4:30** Run the seeds · Claude Code
- **6:30** Curate · `review-sites.csv`
- **7:00** Fetch emails · md
- **8:00** Pitch · md
- **8:30** Cost + close · md

## The demo in 5 steps

All in `briefs/braise/`. Braise is a demo brief: every command replays what's saved. Seconds, nothing spent.

1. **Open** `brief.md`
2. **Type** `/snowball braise` → `snowball.csv`
3. **Type** `approve Made In, Ooni and ThermoWorks` → `seeds.csv`
4. **Type** `/run-seeds braise` → about 3 seconds
5. **Open** `review-sites.csv` → 66 sites. Stay scrolled left: email is the last column.

**The loop:** sites we know → `/snowball` finds brands → I approve → Google searches → new sites → repeat.

---

## Script

Say it, don't read it. Land the **bold** lines.

### 0:00 · Problem → solution

Say the two paragraphs at the top, in your own words.

### 0:30 · Objective

Here's what we're going to do. Find the review, comparison, listicle and creator sites that already review brands like ours, and that rank. Get a verified email for each one. Draft a pitch built on what they actually wrote.

**Keep the human in the loop. The human owns the inbox.**

### 1:00 · What we're going to do

Five steps, most of them one command in Claude Code. Watch the last column: a person decides at every step that matters, and the operator sends.

### 1:30 · Seeds + the Braise demo

A seed is a brand to search for: "[brand] review." **We're not trying to rank for these. We're finding who already ranks.** A site that reviewed Caraway is a good bet for the next cookware brand.

Three ways to get seeds:

- **Import** a list you already have. Our 159 brands came in with `/import-seeds`.
- **Draft** them from the brief: `/create-seeds`, for a brand-new client.
- **Snowball**: `/snowball` reads the sitemaps of review sites we already know and counts what else they've reviewed. **A brand that three creator blogs already reviewed is a proven seed, not a guess.**

For a new client I need three things: the categories, three to five comparable brands, and their affiliate partner list if they have one.

**Do:** point at the Braise box. Braise is fictional: non-toxic ceramic cookware. Its competitors are Caraway, Our Place, GreenPan, Great Jones and HexClad. We already know 66 review sites for them.

**Do:** show `briefs/braise/` in the file list. **Everything lives in one folder.** Open `brief.md` for ten seconds.

**Type:**

```
/snowball braise
```

**While Claude sorts (20–40 seconds):** It read every post those sites titled "something review": their sitemaps, public pages, free. Braise replays that saved read, so it doesn't depend on the wifi. One thing the data taught us: **pick product brands, not service brands.** Caraway found 8 creator blogs. The cleaning franchises found none, just Glassdoor.

**When results appear, read the noise first:** Lufthansa. Fitbit. Sherwin-Williams. A retractable garden hose. **Lifestyle creators review everything.** That's why the tool counts, Claude sorts, and I approve.

**Then the picks:** Ooni, ThermoWorks, Made In. Exactly what a cookware creator reviews.

**Type:**

```
approve Made In, Ooni and ThermoWorks
```

**Nothing runs until I approve it.** They land in `seeds.csv`, in the same folder.

*Optional:* I approved two earlier picks, Abbio and Misen, and searched them. Zero new sites, just the same four cookware reviewers. Small world, and good to know before you pitch.

*If it stalls:* go back to the md. The table there shows what it returns. Don't debug on stage.

### 4:30 · Run the seeds

**Type:**

```
/run-seeds braise
```

**Say:** Live, **it tells me what a run will cost before it spends anything**, and it refuses past the monthly cap. Braise replays the searches I already ran, so we don't sit and wait on Google.

**Do:** open `review-sites.csv`, the last file in the folder. **"This is what a run produces: one file, one row per site."** Point at site type, the AI crawler columns and the example review. Stay scrolled left.

**Say:** **"Five brands snowball suggested, ten searches: 34 review sites we didn't have."** Scroll to the BBQ blogs, a pizza-oven tester, thecookwareadvisor.com. Four weren't reviewers at all: two forums, a barbecue shop, and a copy of a review on Google. The filter catches those now.

**Back to the md.** These numbers are from the real October run. One command, three jobs:

- **Scan.** 125 Google searches, page one only. One day, on a free plan.
- **Filter.** Every result thrown out gets a reason. My favourite: "Mosaic Foods review." Mosaic makes frozen meals. The top result was Indeed Canada: employee reviews for a different company called Mosaic. **Wrong Mosaic. Wrong kind of review. Wrong country.**
- **Sort.** The team said creator blogs, not nytimes.com. It doesn't guess: it reads the RSS feed for author names, the about page for "Hi, I'm," and looks for a ShopMy storefront.

It also checks whether ChatGPT's and Claude's search crawlers can get in. 25 of 208 block at least one. **Blocking AI training and blocking AI search are different switches.**

> **Careful:** the tool sorts into four tiers by itself: creator blog, niche review site, media, and check by hand. "Niche category site" and "review site" are categories added by hand for Braise. The YouTube video pack is planned, not built.

### 6:30 · Curate

The team takes out what isn't relevant and flags the priorities. In `review-sites.csv`, the two columns after the domain:

- `suggested`: the tool's pre-sort. Yes, check or no, always with the reason.
- `shortlist`: mine. I mark yes.

Braise: 40 yes, 9 to check, 17 no.

**Do:** point at thecookwareadvisor.com, the best cookware reviewer in the file. The tool says "check: newest date seen is 2016," because its homepage shows an old date. **The tool suggests; a person picks.**

*Optional, cut first:* Otherland makes candles. The pipeline kept a review of a London play called Otherland, and one of a fantasy novel. **It can tell a page is a review. It can't tell what's being reviewed.**

### 7:00 · Fetch emails

`/fetch-emails braise` looks up only the sites I marked yes, and puts the email in the same file. If a site was already looked up for another list, it reuses that contact, at no charge.

The site's own pages first, Hunter second, verify always. No guessed addresses.

October's 100: 65 verified. 6 can't be confirmed (the domain accepts any address, so it's a judgment call). 29 had nothing usable. 37 addresses came free, from the site's own contact page.

**Two sites list an address on their own privacy page. Both bounce.** Verify always.

No address ever goes to GitHub.

### 8:00 · Pitch

The drafts are next. Each one starts from the review the site actually published, not a merge field. **And the tool never sends.**

### 8:30 · Cost + close

Zero dollars. Free tiers all the way.

**Keep the human in the loop. The human owns the inbox.**

**What stays human isn't what's left over. It's the part that carries the risk.**

Thank you.

---

## If they ask

- **How does /snowball know what's a brand?** It doesn't, on its own: it counts names. Claude sorts brands from noise and shows what it dropped. Then I approve.
- **Why seeds, if /snowball has the brief?** Snowball finds brands, not sites: it only reads sites we already know. A Google search finds the ones we don't, and a seed is that search. Searches cost budget, so I approve them.
- **What do you need from a new client?** Categories, three to five comparable product brands, and their affiliate partner list if they have one.
- **How long did it take?** The scan took one day. Contacts took two passes, because Hunter's free tier resets on the 20th. The slow parts are the human steps, on purpose.
- **Why not buy an email database?** I want the sites that reviewed the category this year, and an address verified this month.
- **Does it send?** No. It drafts. I send.
- **Can I have it?** It's Claude Code plus a handful of commands: snowball, run seeds, fetch emails.
- **What about AI answers?** Google rank tells you what a placement wins on the SERP. The crawler check tells you whether ChatGPT or Claude can even read the page. Whether they cite it is the next check.
- **Compliance?** The plan is a dedicated sending domain, never the client's primary, with an opt-out. Sending isn't built yet, so say "the plan is."

## Numbers card

**October run (real)**

- 159 brands, 19 categories. 95 done by hand first, June 2 – July 7.
- 125 searches, page one only, on Oct 6.
- 281 results dropped: brand's own site 76 · not a review 67 · retailer 58 · job sites 37 · directories 19 · forums 13 · app stores 6 · noise 5.
- 208 sites kept: 59 creator · 55 niche review · 29 media · 65 check.
- Team's pick: 100 (56 creator blogs, 43 niche review, 1 to check).
- AI search: 25 of 208 block at least one crawler. Of the 100, 97 are open to both.
- AI training: 44 of 208 block one; 18 of those still allow AI search.
- Contacts: 71 of 100. 37 free from site pages, 34 from Hunter. 65 verified, 6 accept-all, 29 nothing usable.
- Spend: $0. SerpAPI 145 searches, Hunter 62 searches + 78 verifications, all free tiers.

**/snowball**

- Full pool: 139 of 179 sites read, 3,244 names, 30+ new DTC brands with 2+ creator blogs (Nolah, Casper, Puffy, Tuft & Needle, LMNT, Eight Sleep, HelloFresh, Aera).
- Product vs service: Caraway 8 creator blogs, Pura 6, AirDoctor 4. The cleaning franchises, Mr. Handyman and Lawn Love: 0 review sites.

**Braise (fictional)**

- 66 review sites: 32 from October, 34 from five snowball brands (Made In, Ooni, ThermoWorks, Meatstick, Gozney).
- Suggested: 40 yes, 9 check, 17 no.
- Snowball reads 43 of them (the 17 newest aren't read yet), 189 names.
- Abbio + Misen: 4 searches, 0 new sites.
- Replay: every step in seconds, $0.

## Before you go on

- Claude Code open **in `bellwether-2.0/`**. That's what loads the commands.
- `talk/walkthrough.md` in a separate window, one keystroke away.
- **Type `/reset-demo braise`** before the talk, and after any rehearsal where you approved something. It makes Made In, Ooni and ThermoWorks approvable again; all 66 sites stay.
- No morning refresh needed: Braise replays its saved read, whatever its age.
- `/api-check` is safe on screen: Close says "later," not a red FAIL.
- In `review-sites.csv`, stay scrolled left: email is the last column. Never open `data/contacts.csv` or a "(with emails)" file on screen.
- Say the opening problem out loud three times. If the first 30 seconds go well, the rest follows.
- One timed run-through. Running long? Cut Otherland first, then the AI crawler line.

## Cut, and why

- **Motions** (editorial, referral, marketplace): too big for ten minutes.
- **Plural vs singular queries, the off-query guard:** good stories, too long.
- **The Covey demo:** see `talk/notes.md` (the old 15-minute draft).
