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
Writes  outputs/<slug>/<slate>/site-profiles.csv   (no personal data)
        outputs/<slug>/<slate>/creator-shortlist.xlsx (gitignored)

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
MAILTO_RE = re.compile(r"mailto:[^\"'?>\s]+@", re.I)
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
    m = re.search(r'href=["\'](https?://(?:www\.)?' + re.escape(domain) +
                  r'/[^"\'#?]*about[^"\'#?]*)["\']', html or "", re.I)
    return m.group(1) if m else ""


def first_ok(base, paths):
    for path in paths:
        status, html = fetch(base + path)
        if status == 200 and html:
            return base + path, html
    return "", ""


def profile(job):
    domain, title = job if isinstance(job, tuple) else (job, "")
    base = "https://" + domain
    status, home = fetch(base + "/")
    out = {"domain": domain, "http": status, "tier": "", "evidence": "", "authors_on_home": 0,
           "latest_year": "", "affiliate_disclosure": "", "about_page": "", "contact_page": "",
           "published_email": ""}
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
        "published_email": "yes" if MAILTO_RE.search(home + about + contact) else "",
    })

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
    args = ap.parse_args()

    raw_path, _, ranked, _, _ = review_sites.collect(args.slug, args.slate)
    jobs = [(d, s["example"]["title"]) for d, s in ranked]
    sys.stderr.write("profiling {} sites, {} at a time (no API calls)\n".format(len(jobs), args.workers))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        profiles = {p["domain"]: p for p in pool.map(profile, jobs)}

    rows = []
    for d, s in ranked:
        p = profiles[d]
        rows.append(dict(p, brands_reviewed=len(s["brands"]), categories=", ".join(s["categories"]),
                         brands=", ".join(s["brands"]), example_title=s["example"]["title"],
                         example_url=s["example"]["url"]))

    fields = ["domain", "tier", "evidence", "brands_reviewed", "categories", "brands", "authors_on_home",
              "latest_year", "affiliate_disclosure", "about_page", "contact_page", "published_email",
              "http", "example_title", "example_url"]
    csv_path = raw_path.parent / "site-profiles.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    xlsx = write_shortlist(raw_path.parent / "creator-shortlist.xlsx", rows, fields, args)

    from collections import Counter
    c = Counter(r["tier"] for r in rows)
    print("profiled {} sites".format(len(rows)))
    for tier in ("creator blog", "niche review site", "media / publisher", "check"):
        print("  {:<20} {}".format(tier, c.get(tier, 0)))
    team = [r for r in rows if r["tier"] in ("creator blog", "niche review site")]
    print("for the team: {} sites · {} publish an email · {} have a contact page".format(
        len(team), sum(1 for r in team if r["published_email"]),
        sum(1 for r in team if r["contact_page"])))
    print("wrote {}".format(csv_path.relative_to(ROOT)))
    print("wrote {}".format(xlsx.relative_to(ROOT)))
    return 0


def write_shortlist(out, rows, fields, args):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    head = Font(name="Arial", bold=True, color="1F3864", size=10)
    body = Font(name="Arial", size=10)
    link = Font(name="Arial", size=10, color="1155CC", underline="single")
    fill = PatternFill("solid", fgColor="D9E2F3")
    widths = {"domain": 28, "tier": 16, "evidence": 44, "brands_reviewed": 9, "categories": 30, "brands": 36,
              "authors_on_home": 8, "latest_year": 8, "affiliate_disclosure": 9, "about_page": 32,
              "contact_page": 32, "published_email": 9, "http": 6, "example_title": 50, "example_url": 44}

    wb = Workbook(); wb.remove(wb.active)

    def sheet(title, subset):
        ws = wb.create_sheet(title)
        ws.append(fields)
        for c in ws[1]:
            c.font, c.fill, c.alignment = head, fill, Alignment(wrap_text=True, vertical="center")
        for r in subset:
            ws.append([r.get(k, "") for k in fields])
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.font = body
                if isinstance(c.value, str) and c.value.startswith("http"):
                    c.hyperlink, c.font = c.value, link
        for i, f in enumerate(fields, 1):
            ws.column_dimensions[get_column_letter(i)].width = widths.get(f, 14)
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions

    sheet("For the team", [r for r in rows if r["tier"] in ("creator blog", "niche review site")])
    sheet("Check by hand", [r for r in rows if r["tier"] == "check"])
    sheet("Media - set aside", [r for r in rows if r["tier"] == "media / publisher"])
    ws = wb.create_sheet("Method")
    for line in [
        ("Rule", "Creator-style blogs and small niche review sites go to the team. Media and publishers are "
                 "set aside, not deleted (CHANGELOG D13)."),
        ("How", "Each site's homepage, about page and contact page are fetched and read. No API calls."),
        ("Creator", "An about page introducing one person, or a first-person homepage with 1-2 bylines."),
        ("Niche review", "Testing language, a small team, or a review-business domain."),
        ("Media", "A known media domain, or a parent publisher named on the site with several bylines."),
        ("Check by hand", "Blocked, unreachable, or no clear signal. Never guessed: a 403 is not an absence."),
        ("published_email", "Whether an email is published on the site: yes or blank. The address is not "
                            "stored here; it is collected at the contact step, after the shortlist gate."),
        ("Sorted by", "Brands reviewed, most first: a site that reviewed four brands in a category is the "
                      "person to pitch the fifth."),
        ("Built", date.today().isoformat()),
    ]:
        ws.append(line)
    for r in ws.iter_rows():
        r[0].font, r[1].font = head, body
        r[1].alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 16, 100
    wb.save(out)
    return out


if __name__ == "__main__":
    sys.exit(main())
