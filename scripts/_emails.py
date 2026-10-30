#!/usr/bin/env python3
"""
_emails.py — what counts as an email a site publishes, in one place.

Used by site_profile.py at research time (CHANGELOG D18: a published address is
captured as soon as it is seen) and by find_contacts.py at the contact step, so
the two can never disagree about what counts. Moved here from find_contacts.py
on 2026-10-09.

What counts (the contact rule, CHANGELOG D14 and D16):
  - an address on the site's own domain;
  - a webmail address the site publishes itself (small blogs use Gmail);
  - another domain only when the page introduces it as the business line, such
    as a manager or an agency. Anything else on a page may not be theirs.
Never counted: junk from page scaffolding (sentry, wix, image filenames) and
addresses nobody pitches (privacy@, abuse@, legal@).

Found is not verified. Verification happens at the contact step, always.
"""

from __future__ import annotations

import re
import urllib.parse

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# "for business inquiries", "collabs", "management": the line a creator writes
# when they mean "this is the address to pitch me at".
BUSINESS_CUE = re.compile(r"business|inquir|collab|sponsor|partnership|press|booking|management|"
                          r"work with me|brand deal", re.I)
JUNK_EMAIL = ("sentry", "wixpress", "example.com", "godaddy", "squarespace", "cloudflare", "jsdelivr",
              "googleapis", "gstatic", "w3.org", "schema.org", "domain.com", "yourdomain", "noreply",
              "no-reply", "donotreply", "@2x", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
              "your@", "name@", "email@", "user@", "wix.com", "bootstrap", "sentry.io")
NOT_A_PITCH = ("privacy", "abuse", "dmca", "legal", "unsubscribe", "postmaster", "webmaster")
WEBMAIL = ("gmail.com", "outlook.com", "yahoo.com", "hotmail.com", "icloud.com", "proton.me",
           "protonmail.com", "me.com", "aol.com", "live.com")
PITCH_LOCALPART = ("partnerships", "partner", "collabs", "collab", "business", "brands", "pr", "press",
                   "media", "hello", "hi", "hey", "contact", "team", "info", "editor", "editorial")
# The address that handles a partnership pitch, ahead of every other pitch address.
# A company publishes support@ and press@ next to merchants@; only one of them
# answers "list our gift card" (2026-10-29, gift-card partner list).
PARTNER_CUE = re.compile(r"partner|merchant|retail|bizdev|^bd$|alliance|brands?$|collab", re.I)


def partner_rank(local, position=""):
    """0 = a partnerships address or person, 1 = business or marketing, 2 = anything else."""
    if PARTNER_CUE.search(local) or re.search(r"partner|business development|alliance|merchant", position, re.I):
        return 0
    if re.search(r"^(business|sales|marketing|growth)$", local) or re.search(r"marketing|growth|sales", position, re.I):
        return 1
    return 2
TAG_RE = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S | re.I)


def text_of(html):
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", html or ""))


def site_root(domain):
    return ".".join(domain.lower().split(".")[-2:])


def published_emails(domain, pages):
    """pages: [(url, html), ...] already fetched. -> [(email, url, business_cue)], best first.

    Best first means: the site's own domain before anything else, a pitch
    address (partnerships@, hello@) before a person's, a business-cued line
    before an unlabelled one.
    """
    root = site_root(domain)
    found = {}
    for url, html in pages:
        if not html:
            continue
        text = text_of(html)
        candidates = re.findall(r"mailto:([^\"'?>\s]+)", html, re.I) + EMAIL_RE.findall(text)
        for raw in candidates:
            email = urllib.parse.unquote(raw).strip(".,;:()<>[]\"'").lower()
            if "@" not in email or any(j in email for j in JUNK_EMAIL):
                continue
            local, _, host = email.partition("@")
            if local.split("+")[0] in NOT_A_PITCH:
                continue
            i = text.lower().find(email)
            cue = bool(BUSINESS_CUE.search(text[max(0, i - 120): i + 40])) if i >= 0 else False
            own = site_root(host) == root
            if own or host in WEBMAIL or cue:
                found.setdefault(email, (url, cue, own))

    def rank(item):
        email, (url, cue, own) = item
        local = email.split("@")[0]
        return (not own, partner_rank(local), local not in PITCH_LOCALPART, not cue)
    return [(e, u, c) for e, (u, c, o) in sorted(found.items(), key=rank)]
