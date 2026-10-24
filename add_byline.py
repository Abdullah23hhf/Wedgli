#!/usr/bin/env python3
"""
add_byline.py - adds a visible author/date line and Article schema to Wedgli guides,
sets the author on the two deals articles, and adds a "Who writes Wedgli" section to About.

Usage:
  python3 add_byline.py --site . --inplace                 (edit the pages in place; used by GitHub Actions)
  python3 add_byline.py --site <folder> --out <new folder> (write copies, originals untouched)
  Options: --author Abdullah   --updated 2026-10-24   --dates dates.json (optional)

* Publish dates come from the git history (first commit of each page) unless --dates is given.
* An existing "Updated" date is kept on re-runs; --updated is only used the first time.
* Re-running is safe (previous insertions are replaced).
* A guide gets an "Updated" date only if it contains the inserted-content marker
  (i.e. it was really expanded). Other guides show only "Published".
"""
import argparse, datetime, html, json, pathlib, re, subprocess, sys

B_START, B_END = "<!-- wedgli-byline:start -->", "<!-- wedgli-byline:end -->"
S_START, S_END = "<!-- wedgli-schema:start -->", "<!-- wedgli-schema:end -->"
A_START, A_END = "<!-- wedgli-author:start -->", "<!-- wedgli-author:end -->"
D_START, D_END = "<!-- wedgli-by:start -->", "<!-- wedgli-by:end -->"
CSS_ID = "wedgli-byline-css"
CSS = (f'<style id="{CSS_ID}">\n'
       '  .byline-meta { font-size: 0.92rem; color: var(--ink-soft); margin: 14px 0 0; }\n'
       '  .byline-meta strong { color: var(--ink); font-weight: 600; }\n'
       '</style>\n')


def pretty(iso):
    d = datetime.date.fromisoformat(iso)
    return d.strftime("%B ") + str(d.day) + d.strftime(", %Y")


def git_first_date(folder, name):
    try:
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ad", "--date=short", "--", name],
                             cwd=folder, capture_output=True, text=True, check=True).stdout.split()
        return out[-1] if out else None
    except Exception:
        return None


def old_updated(raw):
    m = re.search(re.escape(B_START) + r'.*?Updated <time datetime="(\d{4}-\d{2}-\d{2})"', raw, flags=re.S)
    return m.group(1) if m else None


def strip_old(t):
    """exact inverse of what this script inserts"""
    t = re.sub(r"\n[ \t]*" + re.escape(B_START) + r".*?" + re.escape(B_END), "", t, flags=re.S)
    t = re.sub(re.escape(S_START) + r".*?" + re.escape(S_END) + r"\n", "", t, flags=re.S)
    t = re.sub(r"\n[ \t]*" + re.escape(A_START) + r".*?" + re.escape(A_END) + r"\n", "", t, flags=re.S)
    t = re.sub(re.escape(D_START) + r".*?" + re.escape(D_END), "", t, flags=re.S)
    t = re.sub(r'<style id="' + CSS_ID + r'">.*?</style>\n', "", t, flags=re.S)
    return t


def title_of(t):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", t, flags=re.S)
    h1 = re.sub(r"<[^>]+>", " ", re.sub(r"<br\s*/?>", " ", m.group(1))) if m else ""
    return " ".join(html.unescape(h1).split())


def meta_desc(t):
    m = re.search(r'<meta name="description" content="([^"]*)"', t)
    return html.unescape(m.group(1)) if m else ""


def guide(t, name, published, updated, author):
    lede = re.search(r'(<p class="lede">.*?</p>)', t, flags=re.S)
    if not lede:
        return None
    by = (f'By <strong>{author}</strong> &middot; Published <time datetime="{published}">{pretty(published)}</time>')
    if updated:
        by += f' &middot; Updated <time datetime="{updated}">{pretty(updated)}</time>'
    line = f'\n    {B_START}<p class="byline-meta">{by}</p>{B_END}'
    t = t[:lede.end()] + line + t[lede.end():]

    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title_of(t),
        "description": meta_desc(t),
        "author": {"@type": "Person", "name": author},
        "publisher": {"@type": "Organization", "name": "Wedgli"},
        "datePublished": published,
        "dateModified": updated or published,
        "mainEntityOfPage": f"https://wedgli.com/{name}",
    }
    has_article = re.search(r'"@type"\s*:\s*"Article"', t)
    if has_article:
        # patch the existing Article block instead of adding a second one
        t = re.sub(r'"author"\s*:\s*\{[^{}]*\}', f'"author": {{ "@type": "Person", "name": "{author}" }}', t, count=1)
        if "datePublished" not in t:
            t = re.sub(r'("publisher"\s*:\s*\{[^{}]*\})',
                       lambda m: m.group(1) + f',\n  "datePublished": "{published}",\n  "dateModified": "{updated or published}"', t, count=1)
    else:
        block = f'{S_START}\n<script type="application/ld+json">\n{json.dumps(schema, indent=2, ensure_ascii=False)}\n</script>\n{S_END}\n'
        t = t.replace("</head>", block + "</head>", 1)
    t = t.replace("</head>", CSS + "</head>", 1)
    return t


def deals(t, author):
    t = re.sub(r'("author"\s*:\s*\{)\s*"@type"\s*:\s*"Organization"\s*,\s*"name"\s*:\s*"[^"]*"\s*(\})',
               rf'\1 "@type": "Person", "name": "{author}" \2', t, count=1)
    t = t.replace("<strong>Published:</strong>", f"{D_START}<strong>By:</strong> {author} &middot; {D_END}<strong>Published:</strong>", 1)
    return t


ABOUT_H = "Who writes Wedgli"
ABOUT_BLOCK = (
    f'{A_START}\n'
    f'    <h2>{ABOUT_H}</h2>\n'
    '    <p>Wedgli is written and edited by Abdullah, an independent publisher. Every guide shows the author\'s name and the date it was published or last updated, so you can judge how current it is.</p>\n'
    '    <p>The guides are general information, not professional advice. Where a guide mentions a price, offer, or manufacturer limit, the official page is the final word. If you spot a mistake or an outdated detail, send it through the <a href="contact.html">contact page</a> and the guide will be checked against the original source.</p>\n'
    f'    {A_END}\n'
)


def about(t):
    if ABOUT_H in t:
        return t
    m = re.search(r"\n[ \t]*<h2>Our approach</h2>", t)
    if not m:
        return None
    return t[:m.start()] + "\n    " + ABOUT_BLOCK + t[m.start():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--dates")
    ap.add_argument("--out")
    ap.add_argument("--inplace", action="store_true")
    ap.add_argument("--author", default="Abdullah")
    ap.add_argument("--updated", default=datetime.date.today().isoformat())
    a = ap.parse_args()
    if not a.inplace and not a.out:
        sys.exit("give --out <folder> or --inplace")
    site = pathlib.Path(a.site)
    out = site if a.inplace else pathlib.Path(a.out)
    dates = json.load(open(a.dates)) if a.dates else {}
    out.mkdir(parents=True, exist_ok=True)
    changed, problems = [], []
    for p in sorted(site.glob("*.html")):
        n = p.name
        raw = p.read_text(encoding="utf-8")
        t = strip_old(raw)
        if n.endswith("-guide.html"):
            expanded = "wedgli-added:start" in t
            published = dates.get(n) or git_first_date(site, n) or a.updated
            updated = (old_updated(raw) or a.updated) if expanded else None
            new = guide(t, n, published, updated, a.author)
        elif n in ("ai-student-discounts-2026.html", "black-friday-student-deals-2026.html"):
            new = deals(t, a.author)
        elif n == "about.html":
            new = about(t)
        else:
            continue
        if new is None:
            problems.append(f"{n}: could not place the new markup")
            continue
        if new != raw or not a.inplace:
            (out / n).write_text(new, encoding="utf-8")
            changed.append(n)
    print(f"{len(changed)} page(s) {'changed' if a.inplace else 'written'}")
    for n in changed:
        print("  ", n)
    if problems:
        print("PROBLEMS:", *problems, sep="\n - ")
        sys.exit(1)


if __name__ == "__main__":
    main()
