#!/usr/bin/env python3
"""Generate clean Markdown mirrors of the site's HTML pages.

For every top-level ``*.html`` file this writes a sibling ``<name>.html.md``
that mirrors the page's main content (the convention from the llms.txt spec:
append ``.md`` to the page URL). The HTML is the single source of truth; these
files are regenerated locally and checked in CI, so stale or missing mirrors
fail validation.

Usage:
    python3 scripts/html_to_md.py            # regenerate all pages
    python3 scripts/html_to_md.py index.html # regenerate one page

Deps: beautifulsoup4, markdownify  (pip install beautifulsoup4 markdownify)

The site root is the repo root, or ``public/`` when that folder exists
(Cloudflare Pages layout). The base URL comes from the CNAME file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from markdownify import markdownify as md

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "public" if (REPO / "public").is_dir() else REPO

# Priority list of selectors for the page's main content. First match wins.
CONTENT_SELECTORS = ["main", ".privacy-page", "article", ".content", "body"]

# Elements removed from the content root before conversion (chrome / decoration
# that may live *inside* the content root). Add page-specific selectors here for
# scroll scenes, live readouts and other markup that is not copy.
STRIP_SELECTORS = [
    "script",
    "style",
    "noscript",
    "svg",
    "[aria-hidden='true']",
    ".back-link",
    ".skip-link",
    "header",
    "footer",
    "nav",
]


def site_base() -> str:
    """Base URL derived from the CNAME file, e.g. https://example.app/."""
    cname = (REPO / "CNAME").read_text().strip()
    return f"https://{cname}/"


def page_url(base: str, html_name: str) -> str:
    """Canonical URL of a page. index.html maps to the bare domain."""
    if html_name == "index.html":
        return base
    return urljoin(base, html_name)


def absolutize(soup: BeautifulSoup, base: str) -> None:
    """Make links/images absolute. Internal .html links point at their .md mirror
    so an agent can traverse the Markdown graph without bouncing back to HTML."""
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:")):
            continue
        if re.match(r"^[a-z][a-z0-9+.-]*://", href, re.I):
            continue  # already absolute
        full = urljoin(base, href)
        # Rewrite same-site .html pages to their .md mirror.
        full = re.sub(r"\.html(?=$|[?#])", ".html.md", full)
        a["href"] = full

    for img in soup.find_all("img", src=True):
        src = img["src"].strip()
        if src and not re.match(r"^[a-z][a-z0-9+.-]*://", src, re.I) and not src.startswith("data:"):
            img["src"] = urljoin(base, src)


def select_content(soup: BeautifulSoup):
    for sel in CONTENT_SELECTORS:
        node = soup.select_one(sel)
        if node:
            return node
    return soup


def clean(node) -> None:
    for sel in STRIP_SELECTORS:
        for el in node.select(sel):
            el.decompose()
    # Fold decorative icons and step numbers into the heading that follows them,
    # so "1" + "### Plug in" becomes "### 1. Plug in" instead of leaving the
    # glyph stranded on its own line.
    for tag in node.select(".icon, .step-number, .step"):
        label = tag.get_text(strip=True)
        head = tag.find_next(["h2", "h3", "h4"])
        if head and label:
            is_step = bool({"step-number", "step"} & set(tag.get("class") or []))
            head.insert(0, f"{label}. " if is_step else f"{label} ")
        tag.decompose()
    # Turn FAQ <details><summary>Q</summary>...</details> into "### Q" + answer.
    for summary in node.select("details > summary"):
        summary.name = "h3"


def tidy(markdown: str) -> str:
    markdown = "\n".join(line.rstrip() for line in markdown.splitlines())
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip() + "\n"


def convert(html_path: Path, base: str) -> str:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    content = select_content(soup)
    clean(content)
    absolutize(content, base)

    body = md(
        str(content),
        heading_style="ATX",
        bullets="-",
        strip=["span"],
    )
    body = tidy(body)

    url = page_url(base, html_path.name)
    header = (
        f"<!-- AUTO-GENERATED from {html_path.name}. Do not edit by hand; "
        f"edit the HTML and run python3 scripts/html_to_md.py. -->\n\n"
        f"> **Markdown version** of [{url}]({url}) — a clean, agent-friendly "
        f"mirror of the HTML page.\n\n"
    )
    return header + body


def main(argv: list[str]) -> int:
    base = site_base()
    targets = [ROOT / a for a in argv] if argv else sorted(p for p in ROOT.glob("*.html") if p.name != "404.html")
    if not targets:
        print("No HTML files found.")
        return 1
    for html_path in targets:
        out = html_path.with_name(html_path.name + ".md")
        out.write_text(convert(html_path, base), encoding="utf-8")
        print(f"  {html_path.name} -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
