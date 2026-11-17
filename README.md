# HerdSignal

A daily read for dairy operators. This repo is the whole publication: the issue files,
the script that turns them into the site, and the two workflows that publish it.

## How a brief gets published

1. The scheduled run writes `issues/YYYY-MM-DD.json`, appends to `ledger.json`, and pushes
   its working branch (named `claude/...`).
2. `collect.yml` copies only `issues/` and `ledger.json` from that branch onto `main`,
   checks that the site builds, and starts `publish.yml`.
3. `publish.yml` runs `python3 build.py` and deploys the result to GitHub Pages.

Nothing else on a run's branch can reach `main`. The built site (`docs/`) is not stored
in the repo.

## The build's guards

`build.py` stops, and nothing is published, if an issue file contains operator QA text,
a redirect-wrapped or tracking-tailed link, or an item with a missing field.

## Unpublishing

Delete the issue file from `issues/` on `main`. The site rebuilds without it.

## Settings

`config.json` holds the name, tagline, footer, site address (`site_url`), email signup
address (`signup_action`) and custom domain (`cname`). Leave `cname` empty until the
domain is registered and pointed at GitHub Pages.

## Issue file format

```json
{
  "date": "2026-11-16",
  "intro": "Two sentences on the day's throughline.",
  "items": [
    {
      "section": "Animal health",
      "headline": "Short, plain, specific",
      "body": "What happened.",
      "why": "Why it matters to a dairy operator.",
      "url": "https://canonical-source-link",
      "source_name": "USDA"
    }
  ]
}
```

Items appear in the order listed. The first item's headline is the issue's title in the
archive and the feed.
