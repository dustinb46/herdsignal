#!/usr/bin/env python3
"""HerdSignal static site builder.

Reads config.json and issues/YYYY-MM-DD.json, writes the public site to docs/
(GitHub Pages: deploy from branch, folder /docs). Standard library only.

Usage: python3 build.py
The build refuses to publish operator QA text, redirect-wrapped links,
tracking-tailed links, or items with missing fields.
"""
import datetime as dt
import html
import json
import pathlib
import sys
from email.utils import format_datetime

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs"
REQUIRED = ("section", "headline", "body", "why", "url", "source_name")
BANNED_TEXT = ("OPERATOR QA", "DELETE BEFORE SEND", "{{")
BANNED_URL = ("google.com/url", "utm_", "source=gmail")

CSS = """
:root{--bg:#F6F8F9;--ink:#1D2830;--soft:#55646E;--rule:#D3DADF;--tag:#F4C52B;--link:#2A6A3C;
--display:"Archivo","Arial Narrow","Helvetica Neue",Arial,sans-serif;
--text:"Source Serif 4","Iowan Old Style",Georgia,serif}
@media (prefers-color-scheme:dark){:root{--bg:#151D23;--ink:#EEF2F4;--soft:#A3B0B8;--rule:#33414B;--link:#8FCB9B}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:1.125rem/1.6 var(--text)}
.page{max-width:54rem;margin:0 auto;padding:2.5rem 1.25rem 4rem}
a{color:var(--link);text-underline-offset:.15em}
a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid var(--tag);outline-offset:2px}
.mast a{color:inherit;text-decoration:none}
.mast .name{font:800 clamp(3rem,10vw,5.75rem)/.9 var(--display);font-stretch:75%;letter-spacing:-.02em;margin:0}
.mast.small .name{font-size:2.25rem}
.pitch{max-width:34rem;margin:.9rem 0 0;color:var(--soft)}
.signup{margin:1.5rem 0 0;display:flex;flex-wrap:wrap;gap:.5rem;align-items:center}
.signup label{flex-basis:100%;font:600 .95rem/1.3 var(--display)}
.signup input{font:inherit;padding:.55rem .75rem;border:1px solid var(--soft);border-radius:4px;background:transparent;color:inherit;min-width:16rem}
.signup button{font:700 1rem/1 var(--display);padding:.8rem 1.1rem;border:0;border-radius:4px;background:var(--link);color:var(--bg);cursor:pointer}
.note{margin:1.5rem 0 0;color:var(--soft);font-size:1rem}
.issue{margin-top:3rem;border-top:6px solid var(--ink);padding-top:1.25rem}
.issue h1,.issue h2.date{font:700 1.6rem/1.2 var(--display);margin:0}
.intro{font-size:1.3rem;line-height:1.5;margin:1rem 0 0;max-width:40rem}
.item{display:grid;grid-template-columns:9.5rem 1fr;gap:0 1.5rem;padding:2rem 0;border-bottom:1px solid var(--rule)}
.item:first-of-type{margin-top:1.5rem;border-top:1px solid var(--rule)}
.tag{justify-self:start;align-self:start;position:relative;margin-top:.2rem;background:var(--tag);color:#1D2830;
font:700 .85rem/1.15 var(--display);padding:.5rem .7rem .5rem 1.7rem;border-radius:4px 11px 11px 4px}
.tag::before{content:"";position:absolute;left:.6rem;top:50%;width:.5rem;height:.5rem;margin-top:-.25rem;border-radius:50%;background:var(--bg)}
.item h3{font:700 1.5rem/1.2 var(--display);margin:0;max-width:36rem}
.item p{margin:.75rem 0 0;max-width:38rem}
.item .why{border-left:5px solid var(--tag);padding-left:.9rem}
.item .why b{font-family:var(--display)}
.item .src{font:500 1rem/1.4 var(--display)}
.archive{margin-top:3.5rem}
.archive h2{font:700 1.6rem/1.2 var(--display);margin:0 0 .5rem}
.archive ul{list-style:none;margin:0;padding:0}
.archive li{display:grid;grid-template-columns:9.5rem 1fr;gap:0 1.5rem;padding:.7rem 0;border-bottom:1px solid var(--rule)}
.archive time{font:600 1rem/1.6 var(--display);color:var(--soft)}
footer{margin-top:3rem;color:var(--soft);font-size:.95rem;max-width:38rem}
@media (max-width:40rem){.item,.archive li{grid-template-columns:1fr}.item .tag{margin-bottom:.8rem}.signup input{min-width:0;flex:1}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,500..800'
         '&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">')


def e(s):
    return html.escape(str(s), quote=True)


def fail(msg):
    sys.exit("BUILD STOPPED: " + msg)


def load_issues():
    issues = []
    for path in sorted((ROOT / "issues").glob("*.json")):
        raw = path.read_text(encoding="utf-8")
        for bad in BANNED_TEXT:
            if bad in raw:
                fail(f"{path.name} contains '{bad}'. QA text never goes in an issue file.")
        data = json.loads(raw)
        try:
            day = dt.date.fromisoformat(data["date"])
        except (KeyError, ValueError):
            fail(f"{path.name} needs a 'date' in YYYY-MM-DD form.")
        if path.stem != data["date"]:
            fail(f"{path.name} does not match its date field {data['date']}.")
        if not data.get("intro") or not data.get("items"):
            fail(f"{path.name} needs an intro and at least one item.")
        for n, item in enumerate(data["items"], 1):
            missing = [k for k in REQUIRED if not str(item.get(k, "")).strip()]
            if missing:
                fail(f"{path.name} item {n} is missing: {', '.join(missing)}")
            url = item["url"]
            if not url.startswith("https://") or any(b in url for b in BANNED_URL):
                fail(f"{path.name} item {n} link is not a clean https source link: {url}")
            if "—" in json.dumps(item, ensure_ascii=False):
                print(f"note: {path.name} item {n} contains an em dash")
        data["day"] = day
        issues.append(data)
    if not issues:
        fail("no issue files found in issues/")
    return sorted(issues, key=lambda i: i["day"], reverse=True)


def long_date(day):
    return f"{day:%A, %B} {day.day}, {day.year}"


def render_items(issue):
    out = []
    for item in issue["items"]:
        out.append(
            '<article class="item">'
            f'<span class="tag">{e(item["section"])}</span><div>'
            f'<h3>{e(item["headline"])}</h3>'
            f'<p>{e(item["body"])}</p>'
            f'<p class="why"><b>Why it matters:</b> {e(item["why"])}</p>'
            f'<p class="src"><a href="{e(item["url"])}" rel="noopener">Read the source at {e(item["source_name"])}</a></p>'
            '</div></article>')
    return "".join(out)


def signup(cfg, prefix):
    if cfg.get("signup_action"):
        return (f'<form class="signup" method="post" action="{e(cfg["signup_action"])}">'
                '<label for="email">Get the brief by email each morning</label>'
                '<input id="email" name="email" type="email" autocomplete="email" placeholder="you@example.com" required>'
                '<button type="submit">Subscribe</button></form>')
    feed = f' Until then, <a href="{prefix}feed.xml">follow the RSS feed</a>.' if cfg.get("site_url") else ""
    return f'<p class="note">Email delivery is not open yet.{feed}</p>'


def page(cfg, title, desc, body, prefix, path):
    site = cfg.get("site_url", "").rstrip("/")
    og_url = f'<meta property="og:url" content="{e(site + "/" + path)}">' if site else ""
    feed = (f'<link rel="alternate" type="application/rss+xml" title="{e(cfg["name"])}" href="{prefix}feed.xml">'
            if site else "")
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)}</title><meta name="description" content="{e(desc)}">'
            f'<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">'
            f'<meta property="og:type" content="article">{og_url}{feed}{FONTS}'
            f'<style>{CSS}</style></head><body><div class="page">{body}'
            f'<footer><p>{e(cfg["footer"])}</p></footer></div></body></html>')


def build():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    issues = load_issues()
    (OUT / "issues").mkdir(parents=True, exist_ok=True)
    (OUT / ".nojekyll").write_text("")
    if cfg.get("cname"):
        (OUT / "CNAME").write_text(cfg["cname"].strip() + "\n")

    for issue in issues:
        d = issue["date"]
        body = (f'<header class="mast small"><p class="name"><a href="../">{e(cfg["name"])}</a></p></header>'
                f'<section class="issue"><h1>{e(long_date(issue["day"]))}</h1>'
                f'<p class="intro">{e(issue["intro"])}</p>{render_items(issue)}</section>'
                '<p class="note"><a href="../">Latest brief and all past issues</a></p>')
        title = f'{cfg["name"]}: {long_date(issue["day"])}'
        (OUT / "issues" / f"{d}.html").write_text(
            page(cfg, title, issue["items"][0]["headline"], body, "../", f"issues/{d}.html"), encoding="utf-8")

    latest = issues[0]
    rows = "".join(
        f'<li><time datetime="{i["date"]}">{i["day"]:%b} {i["day"].day}, {i["day"].year}</time>'
        f'<a href="issues/{i["date"]}.html">{e(i["items"][0]["headline"])}</a></li>' for i in issues)
    body = (f'<header class="mast"><h1 class="name">{e(cfg["name"])}</h1>'
            f'<p class="pitch">{e(cfg["tagline"])}</p>{signup(cfg, "")}</header>'
            f'<section class="issue"><h2 class="date">{e(long_date(latest["day"]))}</h2>'
            f'<p class="intro">{e(latest["intro"])}</p>{render_items(latest)}</section>'
            f'<section class="archive"><h2>Past issues</h2><ul>{rows}</ul></section>')
    (OUT / "index.html").write_text(page(cfg, cfg["name"], cfg["tagline"], body, "", ""), encoding="utf-8")

    site = cfg.get("site_url", "").rstrip("/")
    if site:
        items = "".join(
            f'<item><title>{e(long_date(i["day"]))}: {e(i["items"][0]["headline"])}</title>'
            f'<link>{e(site)}/issues/{i["date"]}.html</link>'
            f'<guid>{e(site)}/issues/{i["date"]}.html</guid>'
            f'<pubDate>{format_datetime(dt.datetime.combine(i["day"], dt.time(12), dt.timezone.utc))}</pubDate>'
            f'<description>{e(i["intro"])}</description></item>' for i in issues[:30])
        (OUT / "feed.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f'<title>{e(cfg["name"])}</title><link>{e(site)}/</link>'
            f'<description>{e(cfg["tagline"])}</description>{items}</channel></rss>', encoding="utf-8")
    print(f"built {len(issues)} issue(s); latest {latest['date']}")


if __name__ == "__main__":
    build()
