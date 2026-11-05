#!/usr/bin/env python3
"""
site_profile.py — is this review site a creator, a niche review shop, or media?

The curation rule (CHANGELOG D13): the team wants creator-style blogs and small
niche review sites, not publications like nytimes.com. A page title can't tell
them apart (most creator titles don't say "my" or "I"), so this reads each site:
its homepage, its about page, its contact page. No API, no spend.

Signals, all visible in the output so any tier can be argued with:
  publisher     a known media domain, or a parent company in the footer
                (Dotdash Meredith, Hearst, Conde Nast, Future, Ziff Davis...)
  creator       an about page that introduces one person ("Hi, I'm Jenna"),
                or few bylines and a first-person homepage
  niche review  a review business: testing language, a small team, a review-y
                domain (mattressclarity, housefresh)
  check         blocked, timed out, or no clear signal. Never guessed into a tier:
                a 403 is not an absence (close-demo's lesson), and a guess here
                puts a stranger in front of the team or hides a good fit.

Also recorded, because the contact step needs them next: whether there's a
contact or work-with-me page, and whether an email is PUBLISHED on the site
(yes/no only). The address itself is not stored here: this file is committed,
addresses are personal data, and they belong in data/contacts.csv (gitignored)
after the shortlist gate.

Patterns for bylines, dates and analytics IDs come from close-demo's
qualify_targets.py, which needs `requests`; this one is standard library only.

Reads   the kept sites from review_sites.collect(<slug>, <slate>)
Writes  briefs/<slug>/review-sites.csv     the one results file: added to and updated, never
                                          wiped (gitignored: it carries published addresses)
        briefs/<slug>/raw/site-profiles.csv this run's rows, no personal data (committed)

Usage:
  python3 scripts/site_profile.py affiliate-seo-creators --slate 2026-10
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _emails  # noqa: E402
import _paths
import review_sites  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 12
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"}
ABOUT_PATHS = ["/about", "/about-us", "/about-me", "/meet-the-team"]
CONTACT_PATHS = ["/contact", "/contact-us", "/work-with-me", "/advertise", "/media-kit"]

MEDIA = {
    "nytimes.com", "cnet.com", "techradar.com", "tomsguide.com", "healthline.com", "consumerreports.org",
    "foodandwine.com", "apartmenttherapy.com", "purewow.com", "yahoo.com", "nydailynews.com",
    "allrecipes.com", "thekitchn.com", "reviewed.com", "sleepfoundation.org", "sleepdoctor.com",
    "familyhandyman.com", "goodhousekeeping.com", "forbes.com", "usatoday.com", "wired.com", "theverge.com",
    "bonappetit.com", "epicurious.com", "seriouseats.com", "food52.com", "mindbodygreen.com",
    "wellandgood.com", "byrdie.com", "people.com", "menshealth.com", "womenshealthmag.com", "prevention.com",
    "eatingwell.com", "realsimple.com", "thespruce.com", "bhg.com", "marthastewart.com", "msn.com",
    "businessinsider.com", "nymag.com", "buzzfeed.com", "verywellhealth.com", "verywellfit.com", "nbcnews.com",
    "cnn.com", "today.com", "insider.com", "delish.com", "popsugar.com", "bustle.com", "glamour.com",
    "vogue.com", "elle.com", "cosmopolitan.com", "oprahdaily.com", "shape.com", "self.com", "parents.com",
    "whattoexpect.com", "thebump.com", "zdnet.com", "engadget.com", "pcmag.com", "popularmechanics.com",
    "architecturaldigest.com", "housebeautiful.com", "elledecor.com", "countryliving.com", "tasteofhome.com",
    "southernliving.com", "medicalnewstoday.com", "webmd.com", "everydayhealth.com", "health.com",
    "americastestkitchen.com", "livescience.com", "nationalgeographic.com", "tomshardware.com",
}
PUBLISHER_RE = re.compile(
    r"dotdash|meredith corporation|hearst|cond[eé] nast|future (?:plc|us|publishing)|ziff davis|"
    r"red ventures|vox media|buzzfeed,? inc|penske media|gannett|valnet|recurrent ventures|static media|"
    r"a360 media|bustle digital|healthline media|everyday health group|nbcuniversal|warner bros", re.I)
CREATOR_ABOUT_RE = re.compile(
    r"\b(?:hi|hey|hello)[,!]?\s+(?:there[,!]?\s+)?i['’]?m\b|\bmy name is\b|\bwelcome to my\b|"
    r"\bi started this (?:blog|site)\b|\babout me\b|\bi['’]?m a (?:mom|mum|dad|wife|mother|blogger|"
    r"registered dietitian|nurse|teacher|writer)\b", re.I)
TEAM_RE = re.compile(
    r"\bour (?:team|editors|writers|experts|staff|reviewers)\b|\beditorial (?:team|staff|board|standards)\b|"
    r"\bmasthead\b|\bstaff writer\b|\beditor[- ]in[- ]chief\b|\bmedically reviewed\b", re.I)
TESTING_RE = re.compile(r"\bhow we test\b|\bour testing\b|\btesting (?:process|methodology)\b|"
                        r"\bwe(?:'ve)? tested\b|\bhands-on testing\b", re.I)
NICHE_DOMAIN_RE = re.compile(r"review|nerd|lab\b|guide|clarity|advisor|first\b|top10|compare|"
                             r"opolis|testing|quality", re.I)
FIRST_PERSON_RE = re.compile(r"\b(?:i|i'm|i've|my|me)\b", re.I)
# The site's own article title, in the singular first person. "Our experts" is a
# team talking, so "we/our" do not count here.
FIRST_PERSON_TITLE_RE = re.compile(r"\bi\b|\bi['’]m\b|\bi['’]ve\b|\bmy\b|honest review|"
                                   r"years? of use|\bwhy i\b", re.I)
AFFILIATE_RE = re.compile(r"affiliate link|as an amazon associate|may earn (?:a )?commission|"
                          r"contains affiliate|affiliate disclosure", re.I)
# From close-demo qualify_targets.py.
BYLINE_NAME_RE = re.compile(r"\bby\s+([A-Z][a-z]+\s+[A-Z][a-z]+)")
YEAR_RE = re.compile(r'datetime=["\'](\d{4})-\d{2}|"datePublished":\s*"(\d{4})-|'
                     r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2},\s+(\d{4})')
# Creator storefronts. Nobody at a publication links their personal ShopMy.
STOREFRONT_RE = re.compile(r"shopmy|liketoknow|\bltk\b|amazon storefront|amazon\.com/shop/|"
                           r"shop my (?:favorites|home|amazon|faves)|my amazon (?:shop|store|finds)", re.I)
FEED_PATHS = ["/feed/", "/rss.xml", "/feed.xml", "/index.xml"]
FEED_AUTHOR_RE = re.compile(r"<dc:creator>(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?</dc:creator>|"
                            r"<author>\s*<name>\s*(.*?)\s*</name>", re.S)
FEED_YEAR_RE = re.compile(r"<(?:pubDate|published|updated)>[^<]*?(\d{4})")
TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S | re.I)


def fetch(url):
    """-> (status, html). status 0 means no answer at all."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.getcode(), resp.read(600_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception:
        return 0, ""


# AI crawlers, per OpenAI's and Anthropic's own documentation (checked 2026-10-11).
# SEARCH bots decide whether a page can be cited in an answer now; TRAINING bots
# only decide what future models learn. A site can block one and allow the other.
#   OpenAI:    OAI-SearchBot  "won't appear in ChatGPT search answers" if blocked
#              ChatGPT-User   user-requested fetch; "robots.txt rules may not apply"
#              GPTBot         training
#   Anthropic: Claude-SearchBot  search indexing; blocked = "lower visibility"
#              Claude-User       user-requested fetch; blocked "may reduce visibility"
#              ClaudeBot         training
AI_SEARCH = {"ChatGPT": ("OAI-SearchBot", "ChatGPT-User"), "Claude": ("Claude-SearchBot", "Claude-User")}
AI_TRAINING = ["GPTBot", "ClaudeBot"]


def fetch_with_headers(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.getcode(), resp.read(300_000).decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, "", dict(exc.headers or {})
    except Exception:
        return 0, "", {}


def ai_access(domain, page_url):
    """robots.txt read against the page that actually ranked. -> (ai_search, ai_training, cdn).

    Stated policy, not proof: robots.txt is advisory, Cloudflare can block AI
    bots at the network edge without a word in robots.txt (hence `cdn`), and
    allowed is not the same as cited.
    """
    import urllib.robotparser
    status, text, headers = fetch_with_headers("https://" + domain + "/robots.txt")
    low = {k.lower(): v for k, v in headers.items()}
    cdn = "cloudflare" if ("cloudflare" in (low.get("server") or "").lower() or "cf-ray" in low) else ""
    if status in (401, 403):
        return "unknown: robots.txt refused our check", "unknown", cdn
    if status == 0 or status >= 500:
        return "unknown: robots.txt unreachable", "unknown", cdn
    if status != 200 or "<html" in text[:600].lower():
        return "ChatGPT yes · Claude yes (no robots.txt)", "allowed (no robots.txt)", cdn
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    url = page_url or "https://" + domain + "/"
    parts = []
    for name, (search_bot, user_bot) in AI_SEARCH.items():
        if rp.can_fetch(search_bot, url):
            parts.append(name + " yes")
        elif rp.can_fetch(user_bot, url):
            parts.append(name + " fetch-only")
        else:
            parts.append(name + " no")
    blocked = [b for b in AI_TRAINING if not rp.can_fetch(b, url)]
    return " · ".join(parts), ("blocks " + ", ".join(blocked) if blocked else "allowed"), cdn


def text_of(html):
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", html or ""))


def feed_info(base):
    """A WordPress feed usually answers when the homepage's bot shield says 403,
    and it names the author of every post: one person or a team, settled."""
    for path in FEED_PATHS:
        status, xml = fetch(base + path)
        if status == 200 and ("<rss" in xml or "<feed" in xml):
            authors = {a or b for a, b in FEED_AUTHOR_RE.findall(xml) if (a or b)}
            years = [int(y) for y in FEED_YEAR_RE.findall(xml)]
            return {"authors": authors, "latest_year": max(years) if years else ""}
    return None


def about_link(domain, html):
    """The about page wherever it lives: /about-nicole-jaques/ is not /about."""
    for m in re.finditer(r'href=["\'](https?://(?:www\.)?' + re.escape(domain) +
                         r'/[^"\'#?]*about[^"\'#?]*)["\']', html or "", re.I):
        url = m.group(1)
        # Not a stylesheet or a plugin asset: mybalancedspace.com's "about page"
        # came back as wp-content/plugins/.../widget-about/...css.
        if "/wp-content/" in url or re.search(r"\.(?:css|js|png|jpe?g|svg|webp|woff2?)$", url, re.I):
            continue
        return url
    return ""


def first_ok(base, paths):
    for path in paths:
        status, html = fetch(base + path)
        if status == 200 and html:
            return base + path, html
    return "", ""


def profile(job):
    if isinstance(job, tuple):
        domain, title, page_url = (job + ("",))[:3]
    else:
        domain, title, page_url = job, "", ""
    base = "https://" + domain
    status, home = fetch(base + "/")
    out = {"domain": domain, "http": status, "tier": "", "evidence": "", "authors_on_home": 0,
           "latest_year": "", "affiliate_disclosure": "", "about_page": "", "contact_page": "",
           "published_email": "", "published_email_address": ""}
    out["ai_search"], out["ai_training"], out["cdn"] = ai_access(domain, page_url)
    # robots.txt can say yes while the network edge says no. If the edge refused
    # even our browser-like request, AI crawlers very likely meet the same wall.
    if status in (401, 403, 429) and out["cdn"] and not out["ai_search"].startswith("unknown"):
        out["ai_search"] += " · but the edge refused our fetch (HTTP {}): bots may be blocked".format(status)
    feed = feed_info(base)
    if status != 200 or not home:
        blocked = "homepage blocked (HTTP {})".format(status or "no answer")
        if feed and feed["authors"]:
            n = len(feed["authors"])
            out["tier"] = "creator blog" if n <= 2 else ("niche review site" if n <= 6 else "check")
            out["evidence"] = "{}; RSS feed shows {} author(s)".format(blocked, n)
            out["authors_on_home"], out["latest_year"] = n, feed["latest_year"]
        else:
            out["tier"], out["evidence"] = "check", blocked + "; no readable feed"
        return out

    found = about_link(domain, home)
    about_url, about = (found, fetch(found)[1]) if found else ("", "")
    if not about:
        about_url, about = first_ok(base, ABOUT_PATHS)
    contact_url, contact = first_ok(base, CONTACT_PATHS)
    home_t, about_t = text_of(home), text_of(about)
    everything = " ".join((home_t, about_t, text_of(contact)))

    authors = {m for m in BYLINE_NAME_RE.findall(home_t)}
    if feed and feed["authors"]:
        authors = feed["authors"]
    years = [int(y) for groups in YEAR_RE.findall(home) for y in groups if y]
    if feed and feed["latest_year"]:
        years.append(feed["latest_year"])
    out.update({
        "authors_on_home": len(authors),
        "latest_year": max(years) if years else "",
        "affiliate_disclosure": "yes" if AFFILIATE_RE.search(everything) else "",
        "about_page": about_url, "contact_page": contact_url,
    })
    # CHANGELOG D18: a published address is captured as soon as research sees
    # it. It goes to the LOCAL workbook only; the committed CSV keeps yes/blank.
    found = _emails.published_emails(domain, [(contact_url, contact), (about_url, about), (base + "/", home)])
    out["published_email"] = "yes" if found else ""
    out["published_email_address"] = found[0][0] if found else ""

    root = review_sites.root_domain(domain)
    publisher = PUBLISHER_RE.search(everything)
    creator = CREATOR_ABOUT_RE.search(about_t) or CREATOR_ABOUT_RE.search(home_t[:4000])
    team = TEAM_RE.search(everything)
    testing = TESTING_RE.search(everything)
    first_person = len(FIRST_PERSON_RE.findall(home_t[:6000])) >= 8
    ev = []

    if domain in MEDIA or root in MEDIA:
        tier = "media / publisher"; ev.append("known media domain")
    elif publisher and len(authors) >= 3:
        tier = "media / publisher"; ev.append("parent company: " + publisher.group(0))
    elif creator and len(authors) <= 2:
        tier = "creator blog"; ev.append('about page: "' + creator.group(0) + '"')
    elif len(authors) <= 2 and first_person and not team:
        tier = "creator blog"; ev.append("first-person homepage, {} author(s)".format(len(authors)))
    elif STOREFRONT_RE.search(home_t) and len(authors) <= 2:
        tier = "creator blog"; ev.append("creator storefront linked: " + STOREFRONT_RE.search(home_t).group(0))
    elif NICHE_DOMAIN_RE.search(root) or testing or (team and len(authors) <= 6):
        tier = "niche review site"
        ev.append("; ".join(x for x in ("review-business domain" if NICHE_DOMAIN_RE.search(root) else "",
                                        "testing language" if testing else "",
                                        "small team" if team else "") if x))
    elif publisher:
        tier = "media / publisher"; ev.append("parent company: " + publisher.group(0))
    elif len(authors) <= 2 and FIRST_PERSON_TITLE_RE.search(title or ""):
        tier = "creator blog"; ev.append('first-person article title: "{}"'.format((title or "")[:50]))
    else:
        tier = "check"; ev.append("no clear signal")
    if creator and tier != "creator blog":
        ev.append('also: "' + creator.group(0) + '"')
    if len(authors) >= 3:
        ev.append("{} bylines on the homepage".format(len(authors)))
    out["tier"], out["evidence"] = tier, "; ".join(e for e in ev if e)
    return out


def main():
    ap = argparse.ArgumentParser(description="Tier review sites: creator, niche review, media.")
    ap.add_argument("slug")
    ap.add_argument("--slate", default=date.today().strftime("%Y-%m"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--suggest-only", action="store_true",
                    help="just refresh the `suggested` column in review-sites.csv; read no sites")
    ap.add_argument("--live", action="store_true",
                    help="on a demo brief, visit the sites instead of reusing saved profiles (D27)")
    args = ap.parse_args()

    if args.suggest_only:
        path = _paths.review_sites(args.slug)
        write_review_sites(path, [], [])
        from collections import Counter
        with path.open() as fh:
            got = Counter((r["suggested"] or "").split(":")[0]
                          for r in csv.DictReader(l for l in fh if not l.startswith("#")))
        print("refreshed `suggested` in {}: {}".format(path.relative_to(ROOT), dict(got)))
        return 0

    raw_path, _, ranked, _, _ = review_sites.collect(args.slug, args.slate)
    demo = _paths.is_demo(args.slug) and not args.live
    if demo:
        # Visiting 30 sites takes minutes; a talk can't wait (D27). Reuse each
        # site's saved profile; a site never profiled is listed and left out.
        saved_path = raw_path.parent / "site-profiles.csv"
        profiles = {}
        if saved_path.exists():
            with saved_path.open() as fh:
                profiles = {r["domain"]: r for r in csv.DictReader(l for l in fh if not l.startswith("#"))}
        missing = [d for d, _ in ranked if d not in profiles]
        ranked = [(d, s) for d, s in ranked if d in profiles]
        print(_paths.DEMO_LINE)
        print("reusing the saved profiles of {} site(s); visiting none".format(len(ranked)))
        if missing:
            print("not profiled yet, so left out (--live visits them): {}".format(", ".join(missing)))
    else:
        jobs = [(d, s["example"]["title"], s["example"]["url"]) for d, s in ranked]
        sys.stderr.write("profiling {} sites, {} at a time (no API calls)\n".format(len(jobs), args.workers))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            profiles = {p["domain"]: p for p in pool.map(profile, jobs)}

    rows = []
    for d, s in ranked:
        p = profiles[d]
        rows.append(dict(p, brands_reviewed=len(s["brands"]), categories=", ".join(s["categories"]),
                         brands=", ".join(s["brands"]), best_rank=s["best"], result_types=", ".join(s["types"]),
                         example_title=s["example"]["title"], example_url=s["example"]["url"]))

    fields = ["domain", "tier", "evidence", "brands_reviewed", "categories", "brands", "best_rank", "result_types",
              "ai_search", "ai_training", "cdn", "authors_on_home",
              "latest_year", "affiliate_disclosure", "about_page", "contact_page", "published_email",
              "http", "example_title", "example_url"]
    csv_path = raw_path.parent / "site-profiles.csv"
    if not demo:                       # a replay learned nothing new: the saved file stays as it is
        with csv_path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})
    # The one results file, beside the brief and the seed list (CHANGELOG D25). It's
    # local (gitignored; the commit hook refuses addresses), so it alone carries the
    # published address, in the `email` column the team's sheet already has.
    results = write_review_sites(_paths.review_sites(args.slug), rows, fields)

    from collections import Counter
    c = Counter(r["tier"] for r in rows)
    print("{} {} sites".format("replayed" if demo else "profiled", len(rows)))
    for tier in ("creator blog", "niche review site", "media / publisher", "check"):
        print("  {:<20} {}".format(tier, c.get(tier, 0)))
    team = [r for r in rows if r["tier"] in ("creator blog", "niche review site")]
    print("for the team: {} sites · {} publish an email · {} have a contact page".format(
        len(team), sum(1 for r in team if r["published_email"]),
        sum(1 for r in team if r["contact_page"])))
    if not demo:
        print("wrote {}".format(csv_path.relative_to(ROOT)))
    print("updated {} ({} sites)".format(results.relative_to(ROOT), count_rows(results)))
    return 0


# review-sites.csv is site-profiles.csv, column for column, plus the two columns
# the team's sheet ends with (Nicole, 2026-11-04). /fetch-emails fills those two in
# place, so one layout runs from research to outreach.
EMAIL_COLUMNS = ["email", "email status"]
PUBLISHED = "published on site, not yet verified"
ORDER = ["creator blog", "niche review site", "check", "media / publisher"]   # the team's tiers first
# A brief whose sites were categorized by hand has "site type" instead of "tier".
SITE_TYPE = {"creator blog": "Creator blog", "niche review site": "Niche review site",
             "media / publisher": "Media", "check": "Check by hand"}


CURATION = ["suggested", "shortlist"]       # right after `domain`, so they're visible scrolled left


def suggest(r):
    """The tool's pre-sort for the shortlist: "yes", "check: why" or "no: why".
    A suggestion, never a decision: `shortlist` is the person's column (D26)."""
    kind = (r.get("site type") or r.get("tier") or "").strip().lower()
    if kind in ("media", "media / publisher"):
        return "no: media, set aside"
    if kind == "wrong match":
        return "no: not a review site"
    if kind == "competitor brand":
        return "no: a competitor"
    if kind in ("check", "check by hand", ""):
        return "check: couldn't tell what kind of site it is"
    year = str(r.get("latest_year") or "").strip()   # an int on freshly profiled rows
    if year.isdigit() and int(year) < date.today().year - 1:
        return "check: newest date seen is {} (homepages can show old dates)".format(year)
    if not (r.get("contact_page") or r.get("published_email") or r.get("email")):
        if (r.get("http") or "") not in ("", "200"):
            return "yes: it blocked our reader, so no contact found yet"
        return "check: no contact page or published email"
    return "yes"


def count_rows(path):
    with path.open() as fh:
        return sum(1 for _ in csv.DictReader(l for l in fh if not l.startswith("#")))


def write_review_sites(path, rows, fields):
    """The brief's one results file, kept up to date rather than rewritten.

    New sites are added, the team's tiers first. A site already in the file gets
    this run's research columns, but a column a person added (site type, niche,
    notes) is never touched, and neither is an email that /fetch-emails or a
    person put there: only a blank or still-unverified published address is
    refreshed. An editor's "# ..." settings line stays on top. `suggested` is
    recomputed for every row; `shortlist`, the person's column, is never touched.
    """
    head, header, existing = [], None, {}
    if path.exists():
        lines = path.read_text().splitlines(keepends=True)
        head = [l for l in lines if l.startswith("#")]
        reader = csv.DictReader(l for l in lines if not l.startswith("#"))
        header = list(reader.fieldnames or [])
        existing = {r["domain"]: r for r in reader}
    if header is None:
        header = fields + EMAIL_COLUMNS
    hand_typed = "site type" in header and "tier" not in header
    for f in fields:                       # research columns the file doesn't have yet
        if f in header or (f == "tier" and hand_typed):
            continue
        header.insert(header.index("email") if "email" in header else len(header), f)
    for f in EMAIL_COLUMNS:
        if f not in header:
            header.append(f)
    for i, f in enumerate(CURATION):
        if f not in header:
            header.insert(header.index("domain") + 1 + i, f)

    new = []
    for r in rows:
        cur = existing.get(r["domain"])
        if cur is None:
            cur = {"domain": r["domain"]}
            if hand_typed:
                cur["site type"] = SITE_TYPE.get(r.get("tier"), "Check by hand")
            new.append(cur)
        for f in fields:
            if f in header:
                cur[f] = r.get(f, "")
        published = r.get("published_email_address") or ""
        if published and (cur.get("email status") or "") in ("", PUBLISHED):
            cur["email"], cur["email status"] = published, PUBLISHED

    for r in list(existing.values()) + new:
        r["suggested"] = suggest(r)          # the tool's column: always current
        r.setdefault("shortlist", "")        # the person's column: never touched
    with path.open("w", newline="") as fh:
        fh.writelines(head)
        w = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        w.writeheader()
        w.writerows(existing.values())
        w.writerows(sorted(new, key=lambda r: ORDER.index(r.get("tier")) if r.get("tier") in ORDER else len(ORDER)))
    return path


if __name__ == "__main__":
    sys.exit(main())
