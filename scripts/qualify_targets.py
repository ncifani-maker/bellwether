#!/usr/bin/env python
"""Qualify scored opportunities into actually-pitchable targets (client-agnostic).

Usage:
  qualify_targets.py <client_dir> --category "coin,currency,numismatic,bullion"

score_opportunities.py answers "who ranks?". This answers the two questions that
decide whether a ranking domain is worth an outreach email:

  1. Does it SELL what our client sells?  -> competitor, park it
  2. Does it PUBLISH?                     -> no editorial surface means there is
                                             nothing for us to be included in

Both are checked by fetching the site, not guessed.

Notes on the two things that made a naive version wrong:
  * "Has a cart" is NOT "is a competitor" — a trade body with a membership store
    and a trade publication with a subscription checkout both have carts. We
    require a real product INVENTORY in the client's category: a shop/inventory
    page carrying several priced items alongside category terms.
  * Big publishers bot-block (403/406/429). A block is not an absence. We retry
    against the URL that actually ranked (known-good), and fall back to
    ranked-URL evidence rather than silently scoring the domain as dead.

Writes <client_dir>/qualified.csv. Read-only over the network; no API cost.
"""
import os
import re
import sys
import csv
import json
import time
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor

import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9"}
TIMEOUT = 12
BLOCKED_CODES = {401, 403, 406, 418, 429, 503}

EDITORIAL_PATHS = ["/blog", "/news", "/articles", "/learn", "/guides", "/resources", "/insights"]
SHOP_PATHS = ["/shop", "/inventory", "/store", "/collections", "/buy", "/catalog", "/products"]

EDITORIAL_RE = re.compile(
    r'href=["\'][^"\']*(/blog|/news|/articles?|/learn|/guides?|/resources|/education|/insights)', re.I)

# --- Legitimacy signals -------------------------------------------------------
# Added 2026-07-30 after client review: a verified /blog path says nothing about
# whether a site is REAL. Owen flagged two targets as "vibe-coded" AI/SEO sites
# and one as pay-to-play. Structural checks alone can't tell those from a genuine
# publication, so we score the things that are hard to fake.
BYLINE_RE = re.compile(
    r'(rel=["\']author|class=["\'][^"\']*author|"@type":\s*"Person"|\bby\s+[A-Z][a-z]+\s+[A-Z][a-z]+)')
DATE_RE = re.compile(
    r'(datetime=["\'](\d{4})-\d{2}|"datePublished":\s*"(\d{4})-|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+(\d{4}))')
# Paid placement is a different motion (advertising), not earned media.
PAYWALL_RE = re.compile(
    r'(advertise with us|advertising opportunities|sponsored post|sponsored content|'
    r'paid (guest )?post|submit (your )?(a )?(guest )?(article|listing|post)|media kit|'
    r'partner with us|list your business|featured listing|premium listing)', re.I)
# Shared analytics/tag IDs are the cleanest tell that two domains are one operator.
ANALYTICS_RE = re.compile(r'\b(UA-\d{4,}-\d+|G-[A-Z0-9]{8,}|GTM-[A-Z0-9]{6,})\b')

# --- The concrete ask ---------------------------------------------------------
# For most editorial targets the ask is "can our expert write for you?". A site
# that publishes contributor guidelines has pre-answered that, and turns a vague
# "worth researching more" into a specific next action.
CONTRIB_RE = re.compile(
    r'href=["\']([^"\']*(write[\-_ ]for[\-_ ]us|contribut|guest[\-_ ]post|submit[\-_ ](an[\-_ ])?'
    r'(article|story|post)|editorial[\-_ ]guidelines|submission[\-_ ]guidelines|become[\-_ ]a[\-_ ]writer)[^"\']*)',
    re.I)
CONTRIB_PATHS = ["/write-for-us", "/contribute", "/guest-post", "/submit-article",
                 "/editorial-guidelines", "/contributors", "/submissions"]
CART_RE = re.compile(
    r'(add[\s\-_]?to[\s\-_]?cart|add to bag|/checkout\b|shopify|woocommerce|bigcommerce|'
    r'data-product-id|"@type":\s*"Product")', re.I)
PRICE_RE = re.compile(r'\$\s?\d[\d,]{2,}')
URL_EDITORIAL_RE = re.compile(
    r'/(blog|news|articles?|learn|guides?|resources|education|insights|post)(/|$)', re.I)


def get(url):
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
        return r
    except Exception:
        return None


def domain_age_years(domain):
    """Registration age via RDAP (free, no key). A 'numismatic news' site registered
    18 months ago is a very different proposition from one registered in 1998."""
    reg = domain.split(".")
    reg = ".".join(reg[-2:]) if len(reg) >= 2 else domain
    try:
        r = requests.get("https://rdap.org/domain/" + reg, timeout=10,
                         headers={"Accept": "application/rdap+json"})
        if r.status_code != 200:
            return None
        for ev in r.json().get("events") or []:
            if ev.get("eventAction") == "registration":
                yr = int(str(ev.get("eventDate"))[:4])
                return max(0, 2026 - yr)
    except Exception:
        return None
    return None


def editorial_quality(html):
    """Cheap proxies for 'is this a real publication': named authors and a spread
    of publication dates. Templated AI/SEO sites usually have neither."""
    if not html:
        return {"bylines": 0, "years": 0}
    years = set()
    for m in DATE_RE.finditer(html):
        for g in m.groups()[1:]:
            if g and g.isdigit() and len(g) == 4:
                years.add(g)
    return {"bylines": len(BYLINE_RE.findall(html)), "years": len(years)}


def make_probe(category_terms):
    cat_re = re.compile("|".join(re.escape(t) for t in category_terms), re.I) if category_terms else None

    def probe(job):
        domain, ranked_url = job
        out = {"domain": domain, "status": "", "sells": False, "editorial": False,
               "editorial_url": "", "title": "", "note": "",
               "age": None, "bylines": 0, "date_years": 0, "pay_to_play": False,
               "analytics": "", "contrib_url": ""}
        base = "https://" + domain
        r = get(base)

        # Bot-block or a subdomain whose root isn't a page: fall back to the URL
        # that actually ranked, which we know resolves.
        if r is None or r.status_code in BLOCKED_CODES or r.status_code == 404:
            code = "err" if r is None else r.status_code
            if ranked_url and ranked_url.rstrip("/") != base.rstrip("/"):
                time.sleep(0.5)
                r2 = get(ranked_url)
                if r2 is not None and r2.status_code < 400:
                    out["note"] = "root {}; used ranked url".format(code)
                    r = r2
                else:
                    out["status"] = "blocked" if code in BLOCKED_CODES or code == "err" else "gone"
                    out["note"] = "root {}, ranked url {}".format(
                        code, "err" if r2 is None else r2.status_code)
                    return out
            else:
                out["status"] = "blocked" if code in BLOCKED_CODES or code == "err" else "gone"
                out["note"] = "root {}".format(code)
                return out

        html = r.text or ""
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        out["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:70] if m else ""

        em = EDITORIAL_RE.search(html)
        if em:
            out["editorial"] = True
            out["editorial_url"] = base + em.group(1)
        else:
            for p in EDITORIAL_PATHS[:4]:
                rr = get(base + p)
                if rr is not None and rr.status_code == 200 and len(rr.text or "") > 2000 \
                        and p.strip("/").lower() in (rr.url or "").lower():
                    out["editorial"] = True
                    out["editorial_url"] = rr.url
                    break

        # Inventory test: a real shop page carrying several priced items in-category.
        def inventory(page_html):
            if not page_html:
                return False
            prices = len(PRICE_RE.findall(page_html))
            in_cat = bool(cat_re.search(page_html)) if cat_re else True
            return prices >= 4 and in_cat and bool(CART_RE.search(page_html))

        if inventory(html):
            out["sells"] = True
        else:
            for p in SHOP_PATHS[:4]:
                rr = get(base + p)
                if rr is not None and rr.status_code == 200 and inventory(rr.text or ""):
                    out["sells"] = True
                    break

        # Legitimacy pass — judged on the editorial surface itself where we found one.
        ed_html = html
        if out["editorial_url"]:
            er = get(out["editorial_url"])
            if er is not None and er.status_code == 200:
                ed_html = er.text or html
        q = editorial_quality(ed_html)
        out["bylines"], out["date_years"] = q["bylines"], q["years"]

        # Contribution surface — the concrete ask, if they publish one.
        cm = CONTRIB_RE.search(html) or CONTRIB_RE.search(ed_html)
        if cm:
            href = cm.group(1)
            out["contrib_url"] = href if href.startswith("http") else base + "/" + href.lstrip("/")
        else:
            for p in CONTRIB_PATHS[:5]:
                rr = get(base + p)
                if rr is not None and rr.status_code == 200 and len(rr.text or "") > 1200 \
                        and p.strip("/").split("-")[0].lower() in (rr.url or "").lower():
                    out["contrib_url"] = rr.url
                    break
        out["pay_to_play"] = bool(PAYWALL_RE.search(html) or PAYWALL_RE.search(ed_html))
        ids = ANALYTICS_RE.findall(html)
        out["analytics"] = ";".join(sorted(set(ids))[:3])
        out["age"] = domain_age_years(domain)
        out["status"] = "ok"
        return out
    return probe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("client_dir")
    ap.add_argument("--category", default="",
                    help="comma-separated product terms that define a competitor, e.g. 'coin,currency'")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--relationships", default="relationships.csv",
                    help="client-supplied relationship inventory (domain,relationship,strength,detail)")
    args = ap.parse_args()
    d = args.client_dir
    terms = [t.strip() for t in args.category.split(",") if t.strip()]

    def rows_of(path):
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return list(csv.DictReader([ln for ln in fh if not ln.lstrip().startswith("#")]))

    opps = rows_of(os.path.join(d, "opportunities.csv"))

    ranked_editorial, ranked_any = {}, {}
    # "What does a win here actually look like?" — the best-ranking page we've already
    # observed on this domain IS the worked example: a real URL, the query it wins, and
    # the position it holds. That's the expected result of a placement, evidenced.
    best_example = {}
    for row in rows_of(os.path.join(d, "results.csv")):
        u, dom = row.get("url") or "", row.get("domain") or ""
        try:
            rank = int(row.get("rank") or 99)
        except ValueError:
            rank = 99
        ranked_any.setdefault(dom, u)
        if URL_EDITORIAL_RE.search(u):
            ranked_editorial.setdefault(dom, u)
        prev = best_example.get(dom)
        # Prefer a real article URL over a homepage, then prefer the better rank.
        deep = len([s for s in u.split("/")[3:] if s]) > 0
        score = (0 if deep else 1, rank)
        if prev is None or score < prev["score"]:
            best_example[dom] = {"score": score, "url": u, "rank": rank,
                                 "keyword": row.get("keyword", ""),
                                 "title": row.get("title", "")}

    # Client relationship inventory. Added 2026-07-30: in client review, EVERY
    # enthusiastic yes traced to a pre-existing relationship (Greysheet emails their
    # 100k list for us; Owen already posts on the PCGS forum; ANA life membership),
    # and the worst miss was assuming a commercial listing implied editorial access.
    # This is the highest-signal input we have and it can only come from the client.
    rel = {}
    rel_path = args.relationships
    if not os.path.isabs(rel_path):
        rel_path = os.path.join(d, rel_path)
    for row in rows_of(rel_path):
        if row.get("domain"):
            rel[row["domain"].strip().lower()] = row
    if rel:
        sys.stderr.write("loaded {} client relationships\n".format(len(rel)))
    else:
        sys.stderr.write("NOTE: no {} — relationship strength is the single best predictor "
                         "of a yes; ask the client to fill it in.\n".format(os.path.basename(rel_path)))

    # LLM citation set, if aeo_citations.py has been run for this client.
    llm_cited = {}
    lc_path = os.path.join(d, "llm_citations.json")
    if os.path.exists(lc_path):
        try:
            with open(lc_path) as fh:
                llm_cited = json.load(fh)
            sys.stderr.write("loaded LLM citations for {} domains\n".format(len(llm_cited)))
        except ValueError:
            llm_cited = {}

    jobs = [(o["domain"], ranked_editorial.get(o["domain"]) or ranked_any.get(o["domain"], ""))
            for o in opps]
    sys.stderr.write("probing {} domains (category: {})...\n".format(len(jobs), terms or "n/a"))
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        probes = {p["domain"]: p for p in ex.map(make_probe(terms), jobs)}

    rows = []
    for o in opps:
        dom = o["domain"]
        p = probes.get(dom, {})
        pub = bool(p.get("editorial")) or dom in ranked_editorial
        pub_url = p.get("editorial_url") or ranked_editorial.get(dom, "")
        sells = bool(p.get("sells"))
        st = p.get("status")

        if st in ("blocked", "gone"):
            verdict = "publisher?" if pub else "unverified"
        elif sells and pub:
            verdict = "competitor-with-blog"
        elif sells:
            verdict = "competitor-no-blog"
        elif pub:
            verdict = "publisher"
        else:
            verdict = "no-editorial-surface"

        # Legitimacy verdict: young domain + no bylines + single-year dates is the
        # signature of a templated AI/SEO site. Pay-to-play is a separate finding —
        # not disqualifying, but it makes this advertising, not earned media.
        age, byl, yrs = p.get("age"), p.get("bylines", 0), p.get("date_years", 0)
        if st in ("blocked", "gone"):
            legit = "unknown"
        elif age is not None and age <= 3 and byl == 0 and yrs <= 1:
            legit = "suspect"
        elif (age is not None and age >= 10) or byl >= 3 or yrs >= 3:
            legit = "established"
        else:
            legit = "thin"

        rl = rel.get(dom.lower(), {})
        ex = best_example.get(dom, {})
        cited = llm_cited.get(dom, {})
        rows.append({
            "domain": dom, "verdict": verdict,
            "relationship": rl.get("relationship", ""),
            "rel_strength": rl.get("strength", ""),
            "rel_detail": rl.get("detail", ""),
            "accepts_contributions": "yes" if p.get("contrib_url") else (
                "?" if st in ("blocked", "gone") else "not published"),
            "contribution_url": p.get("contrib_url", ""),
            "example_url": ex.get("url", ""),
            "example_query": ex.get("keyword", ""),
            "example_rank": ex.get("rank", "") if ex.get("rank", 99) < 99 else "",
            "llm_cited_by": ";".join(sorted(cited.get("engines", []))),
            "llm_cited_queries": ";".join(sorted(cited.get("queries", []))[:3]),
            "publishes": "yes" if pub else ("?" if st in ("blocked", "gone") else "no"),
            "sells": "yes" if sells else ("?" if st in ("blocked", "gone") else "no"),
            "legitimacy": legit,
            "domain_age_yrs": "" if age is None else age,
            "bylines": byl, "date_years": yrs,
            "pay_to_play": "yes" if p.get("pay_to_play") else "",
            "analytics_id": p.get("analytics", ""),
            "seeds_covered": o.get("brands_covered", ""),
            "fit_score": o.get("fit_score", ""), "best_rank": o.get("best_rank", ""),
            "editorial_url": pub_url, "site_title": p.get("title", ""),
            "probe_note": p.get("note", ""), "sample_url": o.get("sample_url", ""),
        })

    # Same-operator clustering: shared analytics/tag IDs across domains.
    by_id = collections.defaultdict(list)
    for r in rows:
        for tag in (r["analytics_id"] or "").split(";"):
            if tag:
                by_id[tag].append(r["domain"])
    shared = {d: sorted(set(g) - {d}) for tag, g in by_id.items() if len(set(g)) > 1 for d in g}
    for r in rows:
        r["same_operator_as"] = ";".join(shared.get(r["domain"], []))

    order = {"publisher": 0, "publisher?": 1, "unverified": 2, "competitor-with-blog": 3,
             "no-editorial-surface": 4, "competitor-no-blog": 5}
    strength = {"strong": 0, "medium": 1, "weak": 2, "": 3}
    # A warm relationship outranks a cold high-ranking domain — that is the whole lesson.
    rows.sort(key=lambda r: (strength.get((r["rel_strength"] or "").lower(), 3),
                             order.get(r["verdict"], 9), -int(r["seeds_covered"] or 0)))

    fields = ["domain", "verdict", "relationship", "rel_strength", "rel_detail",
              "accepts_contributions", "contribution_url",
              "example_url", "example_query", "example_rank",
              "llm_cited_by", "llm_cited_queries",
              "publishes", "sells", "legitimacy", "domain_age_yrs",
              "bylines", "date_years", "pay_to_play", "same_operator_as", "analytics_id",
              "seeds_covered", "fit_score", "best_rank", "editorial_url", "site_title",
              "probe_note", "sample_url"]
    with open(os.path.join(d, "qualified.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    c = collections.Counter(r["verdict"] for r in rows)
    sys.stderr.write("\nWROTE {}/qualified.csv\n  {}\n\n".format(d, dict(c)))
    for label in ("publisher", "publisher?", "unverified"):
        sel = [r for r in rows if r["verdict"] == label]
        if not sel:
            continue
        sys.stderr.write("{} ({}):\n".format(label.upper(), len(sel)))
        for r in sel:
            flags = []
            if r["pay_to_play"]:
                flags.append("PAY-TO-PLAY")
            if r["same_operator_as"]:
                flags.append("same-op:" + r["same_operator_as"][:28])
            sys.stderr.write("  {:<30} {:<12} age={:<4} byl={:<3} yrs={:<3} seeds={:<3} {}\n".format(
                r["domain"][:30], r["legitimacy"], r["domain_age_yrs"], r["bylines"],
                r["date_years"], r["seeds_covered"], " ".join(flags)))
        sys.stderr.write("\n")


if __name__ == "__main__":
    main()
