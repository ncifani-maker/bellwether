---
name: reset-demo
description: "Put a demo brief (for example Braise) back the way it started after a rehearsal: restores briefs/<slug>/seeds.csv from its baseline and keeps the morning's /snowball read. Only works on briefs that have a seeds.baseline.csv, so a real client's seeds can't be reset. Use when the user says 'reset the demo', 'reset braise', or after rehearsing the talk."
argument-hint: "<demo-brief-slug>"
allowed-tools: Bash
user-invocable: true
disable-model-invocation: true
---

# /reset-demo

```bash
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/reset_demo.py" <slug> --dry-run
python3 "${CLAUDE_SKILL_DIR}/../../../scripts/reset_demo.py" <slug>
```

Show the dry run (what it removes and restores), then run it. Report in one line: what's back to the
baseline, and that the morning's `/snowball` read was kept.

If the brief has no `raw/seeds.baseline.csv`, it isn't a demo brief: say so and change nothing.

The same file is what makes a brief a demo brief everywhere else (D27). `/snowball`, `/run-seeds` and
`/fetch-emails` replay what's saved on it and spend nothing unless given `--live`. So the stage flow
after a reset takes seconds.
