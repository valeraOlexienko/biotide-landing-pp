#!/usr/bin/env python3
"""Copy the header, consent banner and footer from index.html into every other page.

    python3 scripts/sync_chrome.py            # sync all pages
    python3 scripts/sync_chrome.py --check    # exit 1 if any page differs (used by CI/hooks)

There is no templating on these sites: the chrome is duplicated verbatim in every
page between <!-- chrome:NAME --> and <!-- /chrome:NAME --> markers. Edit it in
index.html, run this, commit all pages together.

404.html is served at any depth, so its chrome is written with root-absolute
asset and page links (href="/privacy.html"); the markers themselves are the same.
Standard library only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "public" if (REPO / "public").is_dir() else REPO
BLOCKS = ("header", "consent", "footer")


def block(html: str, name: str) -> str | None:
    m = re.search(rf"<!-- chrome:{name}.*?<!-- /chrome:{name} -->", html, re.S)
    return m.group(0) if m else None


def absolutize(chunk: str) -> str:
    """Relative page links -> root-absolute, for 404.html."""
    return re.sub(r'href="(?!(?:https?:|mailto:|tel:|/|#))', 'href="/', chunk)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    source = {name: block(index, name) for name in BLOCKS}
    missing = [n for n, v in source.items() if v is None]
    if missing:
        sys.exit(f"index.html is missing chrome markers for: {', '.join(missing)}")

    changed = []
    for page in sorted(ROOT.glob("*.html")):
        if page.name == "index.html":
            continue
        html = page.read_text(encoding="utf-8")
        new = html
        for name in BLOCKS:
            current = block(html, name)
            if current is None:
                continue  # a page without that block (e.g. a bare landing variant) is left alone
            wanted = absolutize(source[name]) if page.name == "404.html" else source[name]
            new = new.replace(current, wanted)
        if new != html:
            changed.append(page.name)
            if not check:
                page.write_text(new, encoding="utf-8")

    if check:
        if changed:
            print("chrome out of sync with index.html in: " + ", ".join(changed))
            print("run: python3 scripts/sync_chrome.py")
            return 1
        print("chrome in sync")
        return 0
    for name in changed:
        print(f"  updated {name}")
    if not changed:
        print("  nothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
