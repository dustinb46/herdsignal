#!/usr/bin/env python3
"""HerdSignal static site builder.

Reads config.json and issues/YYYY-MM-DD.json, writes the public site to docs/
(GitHub Pages: deploy from branch, folder /docs). Standard library only.

Usage: python3 build.py
       python3 build.py --check-repeats   (report repeat stories across all issues; builds nothing)
The build refuses to publish operator QA text, redirect-wrapped links,
tracking-tailed links, or items with missing fields. It drops items that repeat a story
from the previous 30 days (see drop_repeats) and stops if that leaves the newest issue empty.
"""
import datetime as dt
import difflib
import html
import json
import pathlib
import re
import sys
from email.utils import format_datetime

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "docs"
REQUIRED = ("section", "headline", "body", "why", "url", "source_name")
BANNED_TEXT = ("OPERATOR QA", "DELETE BEFORE SEND", "{{")
BANNED_URL = ("google.com/url", "utm_", "source=gmail")

# Repeat-story filter. Issues dated on or after REPEATS_FROM have items that repeat a story
# from the previous REPEAT_WINDOW_DAYS dropped at build time. The issue files are not
# changed. Earlier issues render as they were first published.
REPEATS_FROM = dt.date(2026, 11, 27)
REPEAT_WINDOW_DAYS = 30
HEADLINE_SIMILARITY = 0.70   # difflib ratio on normalized headlines
FIGURE_SHARE = 0.5           # share of the new item's figures already in the earlier item
TOPIC_OVERLAP = 0.25         # content-word overlap that counts as "same topic"
BODY_TOPIC_OVERLAP = 0.40    # stricter overlap when only the body figures match
BODY_FIGURE_SHARE = 0.6      # share of figures repeated when the headline has none

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
footer .disclaimer{font-size:.8rem;line-height:1.45;margin-top:1rem}
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


# ---------------------------------------------------------------- repeat-story filter

STOPWORDS = set("""
a an the and or but of to in on at for from by with as is are was were be been being it its this that
these those than then now just still has have had not no up down over under into out off more most less
only all any each per one two three week weeks year years month months day days new first last same
while after before about who what which when where why how your you our their they them he she we us
also can will would may says said get got make made since through again another other some such very
much many usda dairy milk
""".split())
ORDINALS = set("""second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth
thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth""".split())
MONEY_RE = re.compile(r"((?:NZ|A|C|US)?\$)\s?(\d[\d,]*(?:\.\d+)?)\s*(million|billion|trillion)?", re.I)
CENTS_RE = re.compile(r"(\d+(?:\.\d+)?)[\s-]*cents?\b", re.I)
PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|per cent\b)", re.I)
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _num(s):
    return ("%.4f" % float(s.replace(",", ""))).rstrip("0").rstrip(".")


def key_figures(text):
    """Dollar amounts (cents converted to dollars) and percentages, normalized."""
    out = set()
    for cur, n, mag in MONEY_RE.findall(text):
        out.add(cur.upper() + _num(n) + (" " + mag.lower() if mag else ""))
    for n in CENTS_RE.findall(text):
        out.add("$" + _num(str(float(n) / 100)))
    for n in PCT_RE.findall(text):
        out.add(_num(n) + "%")
    return out


def _stem(w):
    for suf in ("ings", "ing", "ies", "es", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def content_words(text):
    return {_stem(w) for w in re.findall(r"[a-z][a-z0-9\-]+", text.lower())
            if w not in STOPWORDS and len(w) > 2}


def numbers_in(text):
    """Every number (years aside) and ordinal word, for the 'headline brings a new number' guard."""
    found = {_num(n) for n in NUMBER_RE.findall(text) if not re.fullmatch(r"(19|20)\d\d", n)}
    return found | (set(re.findall(r"[a-z]+", text.lower())) & ORDINALS)


def fingerprint(item):
    head, full = item["headline"], item["headline"] + " " + item["body"]
    return {
        "norm": " ".join(re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", head.lower())),
        "head_figs": key_figures(head),
        "all_figs": key_figures(full),
        "head_nums": numbers_in(head),
        "all_nums": numbers_in(full),
        "words": content_words(full),
    }


def repeat_reason(new, old):
    """Why `new` repeats `old`, or None. Both are fingerprints."""
    # 1. Headline closely matches, and the new headline brings no number the earlier
    #    item did not already have ("44th herd" vs "40 herds" is new, not a repeat).
    ratio = difflib.SequenceMatcher(None, new["norm"], old["norm"]).ratio()
    if ratio >= HEADLINE_SIMILARITY and new["head_nums"] <= old["all_nums"]:
        return f"headline {ratio:.0%} similar"
    words = len(new["words"] & old["words"]) / max(1, min(len(new["words"]), len(old["words"])))
    if words < TOPIC_OVERLAP:
        return None
    shared = new["all_figs"] & old["all_figs"]
    share = len(shared) / max(1, len(new["all_figs"]))
    # 2. Same lead figures: every dollar/percent figure in the new headline was already reported,
    #    at least one of them in the earlier headline, and most of the new item's figures too.
    if (new["head_figs"] and new["head_figs"] <= old["all_figs"] and new["head_figs"] & old["head_figs"]
            and share >= FIGURE_SHARE):
        return "same figures " + ", ".join(sorted(new["head_figs"]))
    # 3. No figure in the headline, but the body repeats the earlier item's numbers on a
    #    closely matching topic (stricter, so a new angle that recaps old prices survives).
    if (not new["head_figs"] and len(shared) >= 3 and share >= BODY_FIGURE_SHARE and words >= BODY_TOPIC_OVERLAP
            and new["head_nums"] <= old["all_nums"]):
        return "same figures " + ", ".join(sorted(shared)[:4])
    return None


def find_repeats(issue, issues):
    """Return [(item_index, earlier_issue, earlier_item_index, reason)] for one issue."""
    start = issue["day"] - dt.timedelta(days=REPEAT_WINDOW_DAYS)
    earlier = [(i, n, fingerprint(it)) for i in issues if start <= i["day"] < issue["day"]
               for n, it in enumerate(i["source_items"])]
    hits = []
    for n, item in enumerate(issue["source_items"]):
        fp = fingerprint(item)
        for old_issue, old_n, old_fp in sorted(earlier, key=lambda x: x[0]["day"], reverse=True):
            reason = repeat_reason(fp, old_fp)
            if reason:
                hits.append((n, old_issue, old_n, reason))
                break
    return hits


def drop_repeats(issues):
    """Drop repeat items from issues dated on or after REPEATS_FROM. Issue files are untouched."""
    for issue in issues:
        issue["source_items"] = list(issue["items"])
    newest = issues[0]
    for issue in issues:
        if issue["day"] < REPEATS_FROM and issue is not newest:
            continue
        hits = find_repeats(issue, issues)
        if not hits:
            continue
        for n, old_issue, old_n, reason in hits:
            print(f"repeat dropped: {issue['date']} item {n + 1} \"{issue['source_items'][n]['headline']}\" "
                  f"matches {old_issue['date']} item {old_n + 1} \"{old_issue['source_items'][old_n]['headline']}\" "
                  f"({reason})")
        dropped = {n for n, *_ in hits}
        kept = [it for n, it in enumerate(issue["source_items"]) if n not in dropped]
        if not kept:
            if issue is newest:
                fail(f"every item in {issue['date']} repeats a story from the last {REPEAT_WINDOW_DAYS} days.")
            print(f"note: every item in {issue['date']} matched an earlier story; keeping it as published")
            continue
        issue["items"] = kept


def check_repeats():
    """Report mode: run the repeat check on every issue, as if each were the newest. Builds nothing."""
    issues = load_issues()
    for issue in issues:
        issue["source_items"] = list(issue["items"])
    total = 0
    for issue in sorted(issues, key=lambda i: i["day"]):
        for n, old_issue, old_n, reason in find_repeats(issue, issues):
            total += 1
            print(f"{issue['date']} #{n + 1}  {issue['source_items'][n]['headline']}\n"
                  f"    matches {old_issue['date']} #{old_n + 1}  {old_issue['source_items'][old_n]['headline']}\n"
                  f"    ({reason})")
    print(f"{total} item(s) would be dropped as repeats")


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
            f'{footer(cfg)}</div></body></html>')


def footer(cfg):
    out = f'<footer><p>{e(cfg["footer"])}</p>'
    email = cfg.get("contact_email", "").strip()
    if email:
        out += f'<p>Questions or corrections: <a href="mailto:{e(email)}">{e(email)}</a></p>'
    if cfg.get("disclaimer", "").strip():
        out += f'<p class="disclaimer">{e(cfg["disclaimer"].strip())}</p>'
    return out + '</footer>'


def build():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    issues = load_issues()
    drop_repeats(issues)
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
        channel_desc = " ".join(s for s in (cfg["tagline"], cfg.get("disclaimer", "").strip()) if s)
        items = "".join(
            f'<item><title>{e(long_date(i["day"]))}: {e(i["items"][0]["headline"])}</title>'
            f'<link>{e(site)}/issues/{i["date"]}.html</link>'
            f'<guid>{e(site)}/issues/{i["date"]}.html</guid>'
            f'<pubDate>{format_datetime(dt.datetime.combine(i["day"], dt.time(12), dt.timezone.utc))}</pubDate>'
            f'<description>{e(i["intro"])}</description></item>' for i in issues[:30])
        (OUT / "feed.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f'<title>{e(cfg["name"])}</title><link>{e(site)}/</link>'
            f'<description>{e(channel_desc)}</description>{items}</channel></rss>', encoding="utf-8")
    print(f"built {len(issues)} issue(s); latest {latest['date']}")


if __name__ == "__main__":
    if "--check-repeats" in sys.argv[1:]:
        check_repeats()
    else:
        build()
