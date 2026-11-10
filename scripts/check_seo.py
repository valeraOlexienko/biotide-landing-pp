#!/usr/bin/env python3
"""Check the site against its SEO rules (the October 2026 audit of the
reference sites, kept as code so it never has to be re-learned).

Run before every commit (the pre-commit hook in .githooks/ does this):

    python3 scripts/check_seo.py

Errors block the commit; warnings are printed and let it through.
Standard library only, so it runs without installing anything.

Rules, per indexable page (every top-level *.html without a noindex robots meta):
  - one <title> (warn over 60 chars), one meta description (max 160), one <h1>
  - absolute self-referencing canonical, and a text/markdown alternate link
  - every <img> has alt, width and height
  - no links to index.html (use /)
  - the required footer line is present (REQUIRED_FOOTER_TEXT, optional)
  - exactly one JSON-LD block that parses, with an @graph that defines
    #organization and #website; every @id it references resolves inside the
    page (only the homepage's #app may be referenced from elsewhere)
  - Article: @id = <url>#article, author/publisher -> #organization,
    isPartOf -> #website, datePublished <= dateModified (ISO dates)
  - BreadcrumbList @id = <url>#breadcrumb, FAQPage @id = <url>#faq
  - FAQPage questions match the visible <summary> text word for word
  - a visible "Last updated <date>" matches the schema dateModified
Site-wide:
  - sitemap.xml lists exactly the indexable pages; lastmod is an ISO date and,
    for articles, equals dateModified
  - llms.txt has an H1, a > summary, and a [title](url) link to every page

The site root is the repo root, or ``public/`` when that folder exists
(Cloudflare Pages layout). The base URL comes from the CNAME file.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "public" if (REPO / "public").is_dir() else REPO
BASE = "https://" + (REPO / "CNAME").read_text().strip()
ORG = BASE + "/#organization"
SITE = BASE + "/#website"
APP = BASE + "/#app"
# A sentence every page's footer must carry (e.g. a disambiguation line when
# other products share the name). Empty string disables the check.
REQUIRED_FOOTER_TEXT = ""
MAX_DESCRIPTION = 160
MAX_TITLE = 60


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titles: list[str] = []
        self.descriptions: list[str] = []
        self.robots = ""
        self.canonicals: list[str] = []
        self.md_alternates: list[str] = []
        self.h1 = 0
        self.imgs: list[dict] = []
        self.hrefs: list[str] = []
        self.summaries: list[str] = []
        self.ld: list[str] = []
        self._capture: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self._start("title")
        elif tag == "meta" and a.get("name") == "description":
            self.descriptions.append(a.get("content", ""))
        elif tag == "meta" and a.get("name") == "robots":
            self.robots = a.get("content", "").lower()
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonicals.append(a.get("href", ""))
        elif tag == "link" and a.get("rel") == "alternate" and a.get("type") == "text/markdown":
            self.md_alternates.append(a.get("href", ""))
        elif tag == "h1":
            self.h1 += 1
        elif tag == "img":
            self.imgs.append(a)
        elif tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
        elif tag == "summary":
            self._start("summary")
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._start("ld")

    def _start(self, what):
        self._capture, self._buf = what, []

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if self._capture and tag in ("title", "summary", "script"):
            text = "".join(self._buf)
            if self._capture == "title":
                self.titles.append(text.strip())
            elif self._capture == "summary":
                self.summaries.append(" ".join(text.split()))
            else:
                self.ld.append(text)
            self._capture = None


errors: list[str] = []
warnings: list[str] = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def warn(where, msg):
    warnings.append(f"{where}: {msg}")


def iso(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def page_url(name: str) -> str:
    return BASE + "/" + ("" if name == "index.html" else name)


def collect_ids(node, out: set[str], refs: set[str]):
    if isinstance(node, dict):
        if "@id" in node:
            (refs if set(node) == {"@id"} else out).add(node["@id"])
        for v in node.values():
            collect_ids(v, out, refs)
    elif isinstance(node, list):
        for v in node:
            collect_ids(v, out, refs)


def check_schema(name: str, p: Page, text: str) -> str | None:
    """Validate JSON-LD; return the page's dateModified if there is one."""
    url = page_url(name)
    if len(p.ld) != 1:
        err(name, f"expected 1 JSON-LD block, found {len(p.ld)}")
        return None
    try:
        doc = json.loads(p.ld[0])
    except json.JSONDecodeError as e:
        err(name, f"JSON-LD does not parse: {e}")
        return None
    graph = doc.get("@graph")
    if not isinstance(graph, list):
        err(name, "JSON-LD must use an @graph")
        return None
    defined: set[str] = set()
    refs: set[str] = set()
    collect_ids(graph, defined, refs)
    for need in (ORG, SITE):
        if need not in defined:
            err(name, f"@graph does not define {need}")
    allowed_external = {APP} if name != "index.html" else set()
    for ref in sorted(refs - defined - allowed_external):
        err(name, f"@id reference does not resolve in this page: {ref}")

    modified = None
    for n in graph:
        t = n.get("@type")
        if t == "Article":
            if n.get("@id") != url + "#article":
                err(name, f"Article @id should be {url}#article")
            for key, target in (("author", ORG), ("publisher", ORG), ("isPartOf", SITE)):
                if n.get(key) != {"@id": target}:
                    err(name, f'Article {key} should be {{"@id": "{target}"}}')
            pub, mod = iso(n.get("datePublished")), iso(n.get("dateModified"))
            if not pub or not mod:
                err(name, "Article needs ISO datePublished and dateModified")
            elif pub > mod:
                err(name, "Article datePublished is after dateModified")
            if not n.get("headline"):
                err(name, "Article has no headline")
            modified = n.get("dateModified")
        elif t == "WebPage" and name != "index.html":
            if n.get("isPartOf") != {"@id": SITE}:
                err(name, f'WebPage isPartOf should be {{"@id": "{SITE}"}}')
            modified = modified or n.get("dateModified")
        elif t == "BreadcrumbList" and name != "index.html":
            if n.get("@id") != url + "#breadcrumb":
                err(name, f"BreadcrumbList @id should be {url}#breadcrumb")
        elif t == "FAQPage":
            if name != "index.html" and n.get("@id") != url + "#faq":
                err(name, f"FAQPage @id should be {url}#faq")
            visible = set(p.summaries)
            for q in n.get("mainEntity", []):
                if q.get("name") not in visible:
                    err(name, f'FAQ question not shown word for word on the page: "{q.get("name")}"')
    if modified:
        m = re.search(r"Last updated:?\s+([A-Z][a-z]+ \d{1,2}, \d{4})", text)
        if m:
            shown = datetime.strptime(m.group(1), "%B %d, %Y").date()
            if shown != iso(modified):
                err(name, f'visible "Last updated {m.group(1)}" differs from schema dateModified {modified}')
    return modified


def check_page(name: str) -> tuple[bool, str | None]:
    text = (ROOT / name).read_text(encoding="utf-8")
    p = Page()
    p.feed(text)
    if "noindex" in p.robots:
        return False, None
    url = page_url(name)

    if len(p.titles) != 1 or not p.titles[0]:
        err(name, "needs exactly one non-empty <title>")
    elif len(p.titles[0]) > MAX_TITLE:
        warn(name, f"title is {len(p.titles[0])} chars (over {MAX_TITLE} may be truncated)")
    if len(p.descriptions) != 1 or not p.descriptions[0]:
        err(name, "needs exactly one meta description")
    elif len(p.descriptions[0]) > MAX_DESCRIPTION:
        err(name, f"meta description is {len(p.descriptions[0])} chars (max {MAX_DESCRIPTION})")
    if p.h1 != 1:
        err(name, f"needs exactly one <h1>, found {p.h1}")
    if p.canonicals != [url]:
        err(name, f"canonical should be {url}, found {p.canonicals or 'none'}")
    if not p.md_alternates:
        err(name, "missing <link rel=alternate type=text/markdown>")
    for img in p.imgs:
        src = img.get("src", "?")
        if "alt" not in img:
            err(name, f"<img> without alt: {src}")
        if not img.get("width") or not img.get("height"):
            err(name, f"<img> without width/height: {src}")
    for href in p.hrefs:
        if href.split("#")[0] == "index.html":
            err(name, f'link to "{href}"; use "/" instead')
            break
    if REQUIRED_FOOTER_TEXT and REQUIRED_FOOTER_TEXT not in text:
        err(name, "required footer line is missing")
    if "__" in text and re.search(r"__[A-Z_]+__", text):
        err(name, f"unfilled template token: {re.search(r'__[A-Z_]+__', text).group(0)}")
    return True, check_schema(name, p, text)


def check_sitemap(pages: dict[str, str | None]):
    path = ROOT / "sitemap.xml"
    xml = path.read_text(encoding="utf-8")
    entries = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", xml))
    locs = set(re.findall(r"<loc>([^<]+)</loc>", xml))
    expected = {page_url(n) for n in pages}
    for missing in sorted(expected - locs):
        err("sitemap.xml", f"missing {missing}")
    for extra in sorted(locs - expected):
        err("sitemap.xml", f"lists a page that is not indexable or does not exist: {extra}")
    for loc in sorted(locs - set(entries)):
        err("sitemap.xml", f"no lastmod for {loc}")
    for name, modified in pages.items():
        lm = entries.get(page_url(name))
        if lm and not iso(lm):
            err("sitemap.xml", f"lastmod is not an ISO date for {name}: {lm}")
        elif lm and modified and iso(lm) != iso(modified):
            err("sitemap.xml", f"lastmod {lm} for {name} differs from its dateModified {modified}")


def check_llms(pages: dict[str, str | None]):
    path = ROOT / "llms.txt"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        err("llms.txt", "first line must be an H1 (# Name)")
    if not any(line.startswith("> ") for line in lines[:6]):
        err("llms.txt", "needs a > summary line right after the H1")
    linked = set(re.findall(r"\]\((" + re.escape(BASE) + r"/[^)\s]*)\)", text))
    for name in pages:
        if not ({page_url(name), BASE + "/" + name + ".md"} & linked):
            err("llms.txt", f"no [title](url) link to {name}")


def main() -> int:
    pages: dict[str, str | None] = {}
    for f in sorted(ROOT.glob("*.html")):
        indexable, modified = check_page(f.name)
        if indexable:
            pages[f.name] = modified
    check_sitemap(pages)
    check_llms(pages)

    for w in warnings:
        print(f"warning  {w}")
    for e in errors:
        print(f"error    {e}")
    if errors:
        print(f"\nSEO check failed: {len(errors)} error(s). Fix them or commit with --no-verify to skip.")
        return 1
    print(f"SEO check passed: {len(pages)} pages" + (f", {len(warnings)} warning(s)" if warnings else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
