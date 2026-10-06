---
name: api-check
description: "Check every NAC API key: present, valid, and how much is left — SerpAPI searches, Hunter credits, DataForSEO balance, YouTube, Anthropic, OpenAI, Close. Free account endpoints only, costs nothing. Use when the user asks about API keys, quota, credits or balances, when something returns a 401 or 403, or before a run that will spend."
argument-hint: "[--only serpapi,hunter]"
allowed-tools: Bash, Read
user-invocable: true
---

# /api-check

Every key NAC uses lives in one file: `/Users/nicolecifani/Documents/nac-worldwide/.env`
(mode 600). Any project can read it. The SERP Tracker keeps its own `keys.txt` and
its Render env vars, so a rotated key has to be changed in both.

```bash
python3 ${CLAUDE_SKILL_DIR}/../../../scripts/api_check.py [--only slug,slug]
```

Slugs: `youtube`, `serpapi`, `hunter`, `dataforseo`, `anthropic`, `openai`, `close`.

Every check uses the provider's free account endpoint, so this costs nothing and
can be run whenever. Exit code 1 means a key Bellwether needs failed.

## Reporting

Print the table as-is. Then say what it means for what Nicole is about to do —
the numbers that matter are the ones about to run out:

- **SerpAPI** is shared with the SERP Tracker's daily client rank checks. Searches
  left is the real constraint on `/serp-scan`.
- **Hunter** free is 50 searches and 100 verifications a month. Say the reset date.
- **DataForSEO** is pay-as-you-go. Under a dollar means seed validation is fine
  and traffic estimates are not.
- **YouTube** can't report a balance. 10,000 units a day, a scout search costs 100,
  a donor scan about 4 per channel. `data/api-usage.csv` is the only running count.

Never print a key, a fragment of one, or paste one into a file. If a key is
missing or rejected, say which one and where it goes — don't ask her to paste it
into the chat.
