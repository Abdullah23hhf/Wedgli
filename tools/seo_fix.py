#!/usr/bin/env python3
"""
One-time Wedgli site fixer.
- Only touches the <head> (canonical / Open Graph / Twitter / fonts) and the
  header/footer home links.
- Plus a short list of exact sentence fixes (listed in SENTENCE_FIXES below).
- Never deletes or rewrites article sections. Safe to run twice (idempotent).
"""
import glob, os, re, sys

SITE = "https://wedgli.com"
SKIP = {"google4c5417055e90dde1.html"}

DESC_FALLBACK = {
    "tiny-house-storage-guide.html":
        "Storage ideas for a tiny house of 400 square feet or less: multi-functional "
        "furniture, stair drawers, vertical wall storage, and hidden compartments.",
}

FONT_FAMILY_ATTR = "fonts.googleapis.com/css2"

# (file, regex, replacement)  -> exact wording fixes for wrong or risky claims
SENTENCE_FIXES = [
    ("studio-furniture-guide.html",
     r"Unlike older models needing permanent wall anchoring, many contemporary versions use heavy-duty counter-weighted frames that require zero drilling\.",
     "Even freestanding models are heavy, so follow the manufacturer's anchoring instructions and check your lease first. If drilling is not allowed, a cabinet-style bed or a sofa bed is the safer choice."),
    ("studio-furniture-guide.html",
     r"using heavy-duty renter-safe anchors\.",
     "using hardware rated for the load, and only where your lease allows it. If you can't drill, a freestanding folding table is the safer pick."),
    ("command-hooks-guide.html",
     r"Use heavy-duty variants \(up to 5 lbs\) near the front door for winter coats, backpacks, and dog leashes\.",
     "Use heavy-duty variants near the front door for winter coats, backpacks, and dog leashes, and always check the weight rating printed on the package."),
    ("command-hooks-guide.html",
     r"can cut adhesive strength by up to half",
     "can weaken the adhesive bond"),
    ("corner-closet-organizer-guide.html",
     r"often 20(?:–|&ndash;|-)30% of the closet",
     "which can be roughly 20–30% of the closet"),
    ("coat-closet-organization-guide.html",
     r"This alone can free up 30(?:–|&ndash;|-)40% of your closet space at any given time\.",
     "This alone can free up a good share of your closet space at any given time."),
    ("storage-bins-guide.html",
     r"increasing pantry spatial efficiency by up to 20% compared to round packaging",
     "so shelves are used more efficiently than with round packaging"),
    ("kids-room-organization-guide.html",
     r"mounted with renter-safe anchors, fitted with",
     "mounted only where your lease allows it (or a freestanding version), fitted with"),
    ("home-office-organization-guide.html",
     r"mounted above the desk with renter-safe anchors or industrial mounting tape",
     "mounted above the desk with industrial mounting tape rated for the load (or anchors, if your lease allows)"),
    ("entryway-organization-guide.html",
     r"mounted next to the front door with renter-safe anchors,",
     "mounted next to the front door (only where your lease allows drilling),"),
]


# Plain-text fixes. Spaces match any whitespace; an apostrophe matches ' or its HTML forms.
PLAIN_FIXES = [
    # --- AI student page: ChatGPT naming + Google clarity (US students) ---
    ("ai-student-discounts-2026.html",
     "Google's student offer depends on your country.",
     "Google gives US college students aged 18+ a free year of Google AI Pro (redeem by Dec 31, 2026, then $19.99/month unless you cancel)."),
    ("ai-student-discounts-2026.html",
     "ChatGPT Work is free for 4 months.",
     "Four months of ChatGPT Plus are free (OpenAI calls the offer ChatGPT Work)."),
    ("ai-student-discounts-2026.html",
     "4 free months of ChatGPT Work",
     "4 free months of ChatGPT Plus (OpenAI calls it ChatGPT Work)"),
    ("ai-student-discounts-2026.html",
     "Four free months of ChatGPT Work.",
     "Four free months of ChatGPT Plus, which OpenAI's offer page calls ChatGPT Work."),
    ("ai-student-discounts-2026.html",
     "For four months of ChatGPT Work,",
     "For four months of ChatGPT Plus (called ChatGPT Work by OpenAI),"),
    ("ai-student-discounts-2026.html",
     "ChatGPT Work</strong> (4 free months)",
     "ChatGPT Plus</strong> (4 free months)"),
    ("ai-student-discounts-2026.html",
     "ChatGPT Work before Oct 31",
     "ChatGPT Plus before Oct 31"),
    ("ai-student-discounts-2026.html",
     "A free 12-month Google AI plan. The plan depends on your country. Check the official page for the offer in your region.",
     "A free 12-month Google AI Pro plan for eligible US college students aged 18+. Students in many other countries get Google AI Plus instead."),
    ("ai-student-discounts-2026.html",
     "Check the redeem deadline on the official page for your country.",
     "Redeem by December 31, 2026."),
    ("ai-student-discounts-2026.html",
     "Free 12-month Google AI plan (varies by country)",
     "Free 12-month Google AI Pro plan (US students; AI Plus elsewhere)"),
    ("ai-student-discounts-2026.html",
     "check the deadline for your country",
     "redeem by Dec 31, 2026"),
    ("ai-student-discounts-2026.html",
     "Often yes. Many countries get a free 12-month Google AI plan. The plan and deadline depend on your country, so check one.google.com/ai-student.",
     "Yes, for eligible US college students aged 18+: Google AI Pro is free for 12 months if you redeem by December 31, 2026. Students in many other countries get Google AI Plus instead."),
    # --- Black Friday page: same naming note ---
    ("black-friday-student-deals-2026.html",
     "4 months free. SheerID check with a school-issued email.",
     "4 months free (OpenAI's page calls it ChatGPT Work). SheerID check with a school-issued email."),
    # --- Cabinet-free kitchen: no-drill promise ---
    ("cabinet-free-kitchen-guide.html",
     "heavy-duty adhesive strips or renter-safe anchors",
     "heavy-duty adhesive strips rated for the load (or anchors, only if your lease allows drilling)"),
]

def plain_to_regex(text):
    pat = re.escape(text)
    pat = pat.replace("\\ ", "\\s+").replace("\\'", "'")
    pat = pat.replace("'", "(?:'|&#39;|&rsquo;|&#x27;|’)")
    return pat

log = []
def say(msg):
    log.append(msg)
    print(msg)

def page_url(fname):
    return SITE + "/" if fname == "index.html" else f"{SITE}/{fname}"

def og_type(fname):
    return "article" if (fname.endswith("-guide.html") or "2026" in fname) else "website"

def fix_fonts(html, changes):
    if 'rel="preload" as="style"' in html:
        return html
    def repl(m):
        tag = m.group(0)
        if FONT_FAMILY_ATTR in tag and 'rel="stylesheet"' in tag:
            href = re.search(r'href="([^"]+)"', tag).group(1)
            changes.append("fonts non-blocking")
            return (f'<link rel="preload" as="style" href="{href}" '
                    f'onload="this.onload=null;this.rel=\'stylesheet\'">\n'
                    f'<noscript><link rel="stylesheet" href="{href}"></noscript>')
        return tag
    new = re.sub(r"<link\b[^>]*>", repl, html)
    if new != html and "fonts.gstatic.com" not in new:
        new = new.replace('<link rel="preload" as="style"',
                          '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
                          '<link rel="preload" as="style"', 1)
        changes.append("preconnect gstatic")
    return new

def fix_head(fname, html, changes):
    mt = re.search(r"<title>(.*?)</title>", html, re.S)
    title = mt.group(1).strip() if mt else ""
    md = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    desc = md.group(1) if md else DESC_FALLBACK.get(fname, "")
    url = page_url(fname)
    add = []
    if not md and desc:
        add.append(f'<meta name="description" content="{desc}">'); changes.append("meta description")
    if not md and not desc:
        say(f"  ! {fname}: no meta description and no fallback")
    if 'name="robots"' not in html:
        add.append('<meta name="robots" content="index, follow, max-image-preview:large">'); changes.append("robots")
    if 'rel="canonical"' not in html:
        add.append(f'<link rel="canonical" href="{url}">'); changes.append("canonical")
    og = [("og:title", title), ("og:description", desc), ("og:type", og_type(fname)),
          ("og:url", url), ("og:site_name", "Wedgli")]
    added_og = False
    for prop, val in og:
        if val and f'property="{prop}"' not in html:
            add.append(f'<meta property="{prop}" content="{val}">'); added_og = True
    if added_og: changes.append("open graph")
    tw = [("twitter:card", "summary"), ("twitter:title", title), ("twitter:description", desc)]
    added_tw = False
    for name, val in tw:
        if val and f'name="{name}"' not in html:
            add.append(f'<meta name="{name}" content="{val}">'); added_tw = True
    if added_tw: changes.append("twitter card")
    if add and "</head>" in html:
        html = html.replace("</head>", "\n".join(add) + "\n</head>", 1)
    return html

def fix_nav(html, changes):
    new = html
    for old, rep in [('href="index.html#guides"', 'href="/#guides"'),
                     ('href="index.html"', 'href="/"'),
                     ('href="https://wedgli.com/index.html#guides"', 'href="https://wedgli.com/#guides"'),
                     ('href="https://wedgli.com/index.html"', 'href="https://wedgli.com/"')]:
        new = new.replace(old, rep)
    if new != html: changes.append("home links /")
    return new

def main():
    files = sorted(f for f in glob.glob("*.html") if f not in SKIP)
    say(f"Found {len(files)} HTML files")
    changed_files = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            original = fh.read()
        html, changes = original, []
        html = fix_head(f, html, changes)
        html = fix_fonts(html, changes)
        html = fix_nav(html, changes)
        for ff, pat, rep in SENTENCE_FIXES:
            if ff == f:
                html, n = re.subn(pat, lambda m, r=rep: r, html, count=1, flags=re.S)
                if n: changes.append("sentence fix")
                elif rep not in html: say(f"  ! {f}: sentence not found -> {pat[:50]}...")
        for ff, text, rep in PLAIN_FIXES:
            if ff == f:
                html, n = re.subn(plain_to_regex(text), lambda m, r=rep: r, html, count=1, flags=re.S)
                if n: changes.append("text fix")
                elif rep not in html: say(f"  ! {f}: text not found -> {text[:50]}...")
        if html != original:
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(html)
            changed_files += 1
            say(f"CHANGED {f}: " + ", ".join(changes))
        else:
            say(f"ok      {f} (nothing to change)")
    say(f"Done. {changed_files} files changed.")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Wedgli fix report\n```\n" + "\n".join(log) + "\n```\n")

if __name__ == "__main__":
    main()
