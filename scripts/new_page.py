#!/usr/bin/env python3
"""Create a new content page (guide, comparison, alternative) from the article template.

    python3 scripts/new_page.py <slug> "<Headline>" ["<Meta description>"]

    slug         the file name without .html, lowercase, hyphens (e.g. widmark-formula)
    Headline     the H1 / Article headline (also the <title> unless it is over 60 characters,
                 in which case shorten the <title> by hand afterwards)
    description  the meta description (max 160 characters); defaults to the headline

What it does:
  - writes <slug>.html from scripts/templates/article.html, with today's date as
    datePublished / dateModified / "Last updated"
  - copies the header, consent banner and footer from index.html, so the chrome is
    identical (the same thing scripts/sync_chrome.py enforces afterwards)
  - adds the page to sitemap.xml and to the Guides section of llms.txt
  - leaves a .html.md mirror to scripts/html_to_md.py and reminds you of the other places
    a page has to appear

Standard library only.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "public" if (REPO / "public").is_dir() else REPO
TEMPLATE = REPO / "scripts" / "templates" / "article.html"
DOMAIN = (REPO / "CNAME").read_text().strip()


def chrome(html: str, name: str) -> str:
    m = re.search(rf"<!-- chrome:{name}.*?<!-- /chrome:{name} -->", html, re.S)
    if not m:
        sys.exit(f"index.html has no <!-- chrome:{name} --> ... <!-- /chrome:{name} --> block")
    return m.group(0)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    slug, headline = argv[0], argv[1]
    description = argv[2] if len(argv) > 2 else headline
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        sys.exit("slug must be lowercase letters, digits and hyphens, e.g. widmark-formula")
    out = ROOT / f"{slug}.html"
    if out.exists():
        sys.exit(f"{out.name} already exists")
    if len(description) > 160:
        sys.exit(f"description is {len(description)} characters; the limit is 160")

    today = date.today()
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    short_title = headline.rstrip("?.!")
    if len(short_title) > 40:
        short_title = short_title[:37].rsplit(" ", 1)[0] + "…"

    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in {
        "{{SLUG}}": slug,
        "{{TITLE}}": headline,
        "{{HEADLINE}}": headline,
        "{{SHORT_TITLE}}": short_title,
        "{{DESCRIPTION}}": description,
        "{{DATE}}": today.isoformat(),
        "{{DATE_LONG}}": f"{today:%B} {today.day}, {today.year}",
        "{{HEADER}}": chrome(index, "header"),
        "{{CONSENT}}": chrome(index, "consent"),
        "{{FOOTER}}": chrome(index, "footer"),
    }.items():
        page = page.replace(key, value)
    out.write_text(page, encoding="utf-8")
    print(f"  wrote {out.name}")

    sitemap = ROOT / "sitemap.xml"
    xml = sitemap.read_text(encoding="utf-8")
    url = f"https://{DOMAIN}/{slug}.html"
    if url not in xml:
        entry = f"    <url>\n        <loc>{url}</loc>\n        <lastmod>{today.isoformat()}</lastmod>\n    </url>\n"
        xml = xml.replace("</urlset>", entry + "</urlset>")
        sitemap.write_text(xml, encoding="utf-8")
        print("  added to sitemap.xml")

    llms = ROOT / "llms.txt"
    text = llms.read_text(encoding="utf-8")
    line = f"- [{headline}]({url}.md): one line on what it answers (HTML: {url})\n"
    if url not in text:
        if "\n## Guides\n" in text:
            head, tail = text.split("\n## Guides\n", 1)
            # append after the heading and any comment lines that follow it
            lines = tail.split("\n")
            i = 0
            while i < len(lines) and (lines[i].startswith("<!--") or lines[i].strip() == "" and i == 0):
                i += 1
            lines.insert(i, line.rstrip("\n"))
            text = head + "\n## Guides\n" + "\n".join(lines)
        else:
            text = text.rstrip("\n") + "\n\n## Guides\n\n" + line
        llms.write_text(text, encoding="utf-8")
        print("  added to llms.txt (edit the one-line summary)")

    print(
        "\nNext:\n"
        f"  1. Write the page: answer box first, sources at the end, FAQ = schema.\n"
        f"  2. Link it from index.html (#guides list with <time datetime=\"{today.isoformat()}\">, footer Guides nav),\n"
        f"     404.html, and the Related reading of sibling pages; then python3 scripts/sync_chrome.py.\n"
        f"  3. python3 scripts/html_to_md.py && python3 scripts/check_seo.py\n"
        f"  4. After deploy: Search Console URL inspection, Request indexing."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
