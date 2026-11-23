#!/usr/bin/env python3
"""The site in other languages, built from the English pages.

    python3 tools/i18n.py extract   # i18n/source.json: every piece of English text, with a stable id
    python3 tools/i18n.py status    # per language: ids missing or no longer used
    python3 tools/i18n.py build     # <lang>/index.html and <lang>/privacy.html, plus the English pages' head links
                                    # and language menu (then scripts/sync_chrome.py, before the languages)

After a build: python3 scripts/html_to_md.py && python3 scripts/check_seo.py.

English is the source: index.html and privacy.html. A unit is a leaf block's inner HTML (a heading, paragraph, list
item, term, summary, caption, SVG label, button, nav link), an attribute meant for people (alt, aria-label,
descriptions in the head), or a string of the JSON-LD. Its id is a hash of the English, so an English edit shows up
in `status` as one missing id per language; i18n/<lang>.txt maps ids to translations (inline tags kept, as in
English). The FAQ in the JSON-LD is rebuilt from the visible questions, so they match word for word.

A language page gets: <html lang>, its canonical, og:url and og:locale, the hreflang links shared by every page,
links that stay inside the language (/ja/#pricing, /ja/privacy.html), the app screens of that language
(images/<lang>/screen-*.webp; Tidy stays English, since it answers in English), the language menu with its own
language ticked, the cookie banner's wording, and on the privacy page a line saying the English text prevails.
Generated pages carry no HTML comments; edit the English and rebuild, never the output.
"""
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://" + (ROOT / "CNAME").read_text().strip()
PAGES = ["index.html", "privacy.html"]
LANGS = ["uk", "ja", "de", "fr", "es", "ko"]
MENU = [("en", "English"), ("uk", "Українська"), ("ja", "日本語"), ("de", "Deutsch"), ("fr", "Français"),
        ("es", "Español"), ("ko", "한국어")]
SCREENS = ["today", "checkin", "insights", "plan", "compatibility", "people"]
SCREEN_VERSION = 2
BLOCK_TAGS = ["title", "h1", "h2", "h3", "p", "li", "dt", "dd", "summary", "figcaption", "text", "button", "legend"]
BLOCK_INSIDE = re.compile(r"<(?:h[1-6]|p|li|dt|dd|summary|ul|ol|dl|div|figcaption|section|table|details)\b", re.I)
ATTRS = ("alt", "aria-label", "title", "placeholder")
META_TEXT = {"description", "og:title", "og:description", "og:image:alt", "twitter:title", "twitter:description",
             "twitter:image:alt"}
LD_KEYS = {"name", "description", "caption", "featureList", "operatingSystem", "text", "alternateName", "headline"}
LD_KEEP = {"Biotide", "Biotide Plus", "iPhone"}
# Units that stay as they are in every language: the brand, addresses, and Tidy's example questions (Tidy answers in
# English only, so the page shows what to type).
SAME = {"Biotide", "Biotide Plus", '<a href="mailto:support@biotide.app">support@biotide.app</a>',
        '<a href="https://biotide.app" target="_blank" rel="noopener">Biotide</a>',
        '<a href="mailto:privacy@biotide.app">privacy@biotide.app</a>',
        "When&rsquo;s a good day for a hard talk with Anna?", "What&rsquo;s my day like tomorrow?",
        "Do my moods follow the emotional curve?"}


def uid(kind: str, text: str) -> str:
    return hashlib.sha1(f"{kind}|{text}".encode()).hexdigest()[:8]


def has_words(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}", html.unescape(re.sub(r"<[^>]+>", "", text))))


def strip_comments(text: str) -> str:
    return re.sub(r"[ \t]*<!--.*?-->[ \t]*\n?", "", text, flags=re.S)


def ld_block(text: str):
    m = re.search(r'(<script type="application/ld\+json">)(.*?)(</script>)', text, re.S)
    return m


def units(text: str):
    """(start, end, kind, english) for every translatable span of a comment-free page, outside the language menu."""
    found, taken = [], []
    menu = re.search(r'<details class="lang-menu">.*?</details>', text, re.S)
    ld = ld_block(text)
    skip = [(menu.start(), menu.end())] if menu else []
    if ld:
        skip.append((ld.start(), ld.end()))

    def free(a, b):
        return not any(s <= a and b <= e for s, e in skip + taken)

    for tag in BLOCK_TAGS:
        for m in re.finditer(rf"<{tag}\b[^>]*>(.*?)</{tag}>", text, re.S):
            inner = m.group(1)
            if BLOCK_INSIDE.search(inner) or not has_words(inner) or not free(m.start(1), m.end(1)):
                continue
            found.append((m.start(1), m.end(1), "html", inner))
    taken = [(a, b) for a, b, _, _ in found]
    for m in re.finditer(r"<(a|span)\b([^>]*)>([^<]+)</\1>", text):
        if m.group(1) == "span" and "visually-hidden" not in m.group(2) and "soon-badge" not in m.group(2):
            continue
        if has_words(m.group(3)) and free(m.start(3), m.end(3)) and "mailto:" not in m.group(2):
            found.append((m.start(3), m.end(3), "html", m.group(3)))
    taken = [(a, b) for a, b, _, _ in found]
    for m in re.finditer(r'\s(' + "|".join(ATTRS) + r')="([^"]*)"', text):
        if has_words(m.group(2)) and free(m.start(2), m.end(2)):
            found.append((m.start(2), m.end(2), "attr", m.group(2)))
    for m in re.finditer(r'<meta (?:name|property)="([^"]+)" content="([^"]*)"', text):
        if m.group(1) in META_TEXT and has_words(m.group(2)):
            found.append((m.start(2), m.end(2), "attr", m.group(2)))
    return sorted(found)


def ld_strings(node, key=None):
    if isinstance(node, dict):
        if node.get("@type") in ("FAQPage", "Question", "Answer"):
            return
        for k, v in node.items():
            yield from ld_strings(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from ld_strings(v, key)
    elif isinstance(node, str) and key in LD_KEYS and node not in LD_KEEP and has_words(node):
        yield node


def english(page: str) -> str:
    return strip_comments((ROOT / page).read_text(encoding="utf-8"))


def source() -> list[dict]:
    out, seen = [], set()
    for page in PAGES:
        text = english(page)
        for _, _, kind, en in units(text):
            i = uid(kind if kind != "attr" else "html", en)
            if i not in seen and en not in SAME:
                seen.add(i)
                out.append({"id": i, "page": page, "en": en})
        doc = json.loads(ld_block(text).group(2))
        for s in ld_strings(doc):
            i = uid("ld", s)
            if i not in seen:
                seen.add(i)
                out.append({"id": i, "page": page, "en": s, "ld": True})
    return out


def load(lang: str) -> dict:
    """i18n/<lang>.txt: "@key value" lines for the page settings, "<id> <translation>" lines for the units."""
    path = ROOT / "i18n" / f"{lang}.txt"
    data = {"meta": {}, "units": {}}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, _, value = line.partition(" ")
        if key.startswith("@banner."):
            data["meta"].setdefault("banner", {})[key[len("@banner."):]] = value
        elif key.startswith("@"):
            data["meta"][key[1:]] = value
        else:
            data["units"][key] = value
    return data


def menu_html(lang: str, meta: dict) -> str:
    rows = []
    for code, name in MENU:
        href = "/" if code == "en" else f"/{code}/"
        current = ' aria-current="true"' if code == lang else ""
        rows.append(f'                    <li><a href="{href}" hreflang="{code}" lang="{code}"{current}>{name}</a></li>')
    own = dict(MENU)[lang]
    label = meta.get("menuLabel", "Language")
    return (
        '<details class="lang-menu">\n'
        f'            <summary aria-label="{html.escape(label)}: {own}">\n'
        '                <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.25"/><path d="M2.75 12h18.5M12 2.75c2.5 2.6 3.75 5.7 3.75 9.25S14.5 18.65 12 21.25M12 2.75C9.5 5.35 8.25 8.45 8.25 12s1.25 6.65 3.75 9.25"/></svg>\n'
        f'                <span class="lang-code" aria-hidden="true">{lang.upper()}</span>\n'
        '            </summary>\n'
        '            <div class="lang-panel">\n'
        f'                <p class="lang-title">{html.escape(label)}</p>\n'
        '                <ul>\n' + "\n".join(rows) + '\n                </ul>\n'
        '            </div>\n'
        '        </details>'
    )


def page_url(lang: str, page: str) -> str:
    folder = "" if lang == "en" else f"{lang}/"
    return f"{BASE}/{folder}" + ("" if page == "index.html" else page)


def hreflang(page: str) -> str:
    lines = [f'    <link rel="alternate" hreflang="{code}" href="{page_url(code, page)}">' for code, _ in MENU]
    lines.append(f'    <link rel="alternate" hreflang="x-default" href="{page_url("en", page)}">')
    return "    <!-- hreflang (tools/i18n.py build) -->\n" + "\n".join(lines) + "\n    <!-- /hreflang -->"


OG_LOCALES = {"en": "en_US", "uk": "uk_UA", "ja": "ja_JP", "de": "de_DE", "fr": "fr_FR", "es": "es_ES", "ko": "ko_KR"}


def with_locale_alternates(text: str, own: str) -> str:
    """og:locale:alternate for every other language, right after the page's og:locale (replacing any already there)."""
    text = re.sub(r'\n\s*<meta property="og:locale:alternate" content="[^"]*">', "", text)
    lines = "".join(f'\n    <meta property="og:locale:alternate" content="{OG_LOCALES[c]}">' for c, _ in MENU if c != own)
    return re.sub(r'(<meta property="og:locale" content="[^"]*">)', lambda m: m.group(1) + lines, text, count=1)

def update_english() -> list[str]:
    """Head links and the language menu on the English pages (the menu also reaches 404.html through sync_chrome)."""
    changed = []
    for page in PAGES:
        path = ROOT / page
        text = path.read_text(encoding="utf-8")
        new = re.sub(r"    <!-- hreflang \(tools/i18n.py build\) -->.*?<!-- /hreflang -->", lambda _: hreflang(page), text,
                     flags=re.S)
        if "<!-- hreflang" not in new:
            new = re.sub(r'(<link rel="alternate" type="text/markdown"[^>]*>)', lambda m: m.group(1) + "\n" + hreflang(page),
                         new, count=1)
        new = with_locale_alternates(new, "en")
        if page == "index.html":
            parked = re.search(r"        <!-- Language menu \(built.*?\n        -->\n", new, re.S)
            live = re.search(r'<details class="lang-menu">.*?</details>', new, re.S)
            menu = menu_html("en", {})
            if parked:
                new = new[:parked.start()] + "        " + menu + "\n" + new[parked.end():]
            elif live:
                new = new[:live.start()] + menu + new[live.end():]
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(page)
    return changed


def rewrite_links(text: str, lang: str) -> str:
    def fix(m):
        attr, value = m.group(1), m.group(2)
        if re.match(r"^(?:[a-z]+:|#|//)", value):
            return m.group(0)
        if value.startswith("/"):
            if value == "/" or value.startswith("/#"):
                value = f"/{lang}" + value
            elif re.match(r"^/[\w-]+\.html(?:\.md)?(?:[?#].*)?$", value):
                value = f"/{lang}" + value
        elif re.match(r"^[\w-]+\.html(?:\.md)?(?:[?#].*)?$", value):
            value = f"/{lang}/" + value
        else:
            value = "/" + value
        return f'{attr}="{value}"'

    text = re.sub(r'\b(href|src|srcset)="([^"]*)"', fix, text)
    shots = "|".join(SCREENS)
    text = re.sub(rf"/images/(screen-(?:{shots})(?:-dark)?\.webp)(?:\?v=\d+)?", rf"/images/{lang}/\1?v={SCREEN_VERSION}",
                  text)
    return text


def build_ld(raw: str, lang: str, page: str, table: dict, faq: list[tuple[str, str]]) -> str:
    local = page_url("en", page)
    raw = raw.replace(f'"{local}#', f'"{page_url(lang, page)}#') if page != "index.html" else raw
    for frag in ("#faq", "#breadcrumb", "#webpage"):
        raw = raw.replace(f'"{BASE}/{frag}"', f'"{page_url(lang, page)}{frag}"')
    doc = json.loads(raw)

    def walk(node, key=None):
        if isinstance(node, dict):
            if node.get("@type") == "FAQPage":
                node["mainEntity"] = [{"@type": "Question", "name": q,
                                       "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]
                return node
            if node.get("@type") == "WebPage":
                node["url"] = page_url(lang, page)
                node["inLanguage"] = lang
            if node.get("@type") == "ListItem" and isinstance(node.get("item"), str):
                for p in PAGES:
                    if node["item"] in (page_url("en", p), page_url("en", p).rstrip("/")):
                        node["item"] = page_url(lang, p)
                        break
            return {k: walk(v, k) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v, key) for v in node]
        if isinstance(node, str):
            if key in LD_KEYS and node not in LD_KEEP and has_words(node):
                return table.get(uid("ld", node), node)
            shots = "|".join(SCREENS)
            return re.sub(rf"{re.escape(BASE)}/images/(screen-(?:{shots})\.webp)", rf"{BASE}/images/{lang}/\1", node)
        return node

    doc = walk(doc)
    body = json.dumps(doc, ensure_ascii=False, indent=4)
    return "\n" + "\n".join("    " + line for line in body.splitlines()) + "\n    "


def plain(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def build_page(lang: str, page: str, data: dict) -> tuple[str, list[str]]:
    meta, table = data.get("meta", {}), data.get("units", {})
    text = english(page)
    missing = []
    out, last = [], 0
    for a, b, kind, en in units(text):
        i = uid("html", en)
        tr = en if en in SAME else table.get(i)
        if tr is None:
            missing.append(i)
            tr = en
        elif kind == "attr":
            tr = html.escape(html.unescape(tr), quote=True)
        out.append(text[last:a] + tr)
        last = b
    out.append(text[last:])
    text = "".join(out)

    text = re.sub(r'<html lang="en"', f'<html lang="{lang}"', text, count=1)
    text = rewrite_links(text, lang)
    text = re.sub(r'(<link rel="canonical" href=")[^"]*"', lambda m: m.group(1) + page_url(lang, page) + '"', text)
    text = re.sub(r'(<meta property="og:url" content=")[^"]*"', lambda m: m.group(1) + page_url(lang, page) + '"', text)
    text = re.sub(r'(<link rel="alternate" type="text/markdown" href=")[^"]*"',
                  lambda m: m.group(1) + page_url(lang, page) + ("index.html.md" if page == "index.html" else ".md") + '"',
                  text)
    text = text.replace('<meta property="og:locale" content="en_US">',
                        f'<meta property="og:locale" content="{meta.get("ogLocale", lang)}">')
    text = re.sub(r'<details class="lang-menu">.*?</details>', lambda _: menu_html(lang, meta), text, flags=re.S)
    text = with_locale_alternates(text, lang)
    if (ROOT / "images" / f"og-image-{lang}.png").exists():  # tools/render_og_langs.py
        text = text.replace(f"{BASE}/images/og-image.png", f"{BASE}/images/og-image-{lang}.png")
    banner = meta.get("banner", {})
    if banner:
        attrs = "".join(f' data-{re.sub(r"([A-Z])", lambda c: "-" + c.group(1).lower(), k)}="{html.escape(v, quote=True)}"'
                        for k, v in banner.items())
        text = text.replace('<div id="cookie-banner" class="cookie-banner"', f'<div id="cookie-banner" class="cookie-banner"{attrs}', 1)
    if page == "privacy.html" and meta.get("privacyNote"):
        text = re.sub(r'(<p class="last-updated">.*?</p>)', lambda m: m.group(1) + f'\n    <p class="note-box">{meta["privacyNote"]}</p>',
                      text, count=1)
    faq = []
    for m in re.finditer(r"<details class=\"faq-item\">\s*<summary>(.*?)</summary>\s*<p>(.*?)</p>", text, re.S):
        faq.append((plain(m.group(1)), plain(m.group(2))))
    ld = ld_block(text)
    ld_table = {k: v for k, v in table.items()}
    for s in ld_strings(json.loads(ld.group(2))):
        if uid("ld", s) not in table:
            missing.append(uid("ld", s))
    text = text[:ld.start(2)] + build_ld(ld.group(2), lang, page, ld_table, faq) + text[ld.end(2):]
    head = f"<!DOCTYPE html>\n<!-- Generated by tools/i18n.py from {page} and i18n/{lang}.txt. Do not edit; edit those and rebuild. -->\n"
    text = head + text.split("\n", 1)[1]
    return text, missing


def write_sitemap() -> bool:
    """sitemap.xml with every English page and its language versions, each <url> carrying the same xhtml:link
    alternates as the pages' heads. lastmod: the English entry's, kept from the current file (scripts/check_seo.py
    checks it against dateModified); a language page shares its English page's lastmod."""
    path = ROOT / "sitemap.xml"
    old = path.read_text(encoding="utf-8")
    lastmod = dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", old))
    english = [loc for loc in lastmod if not any(loc.startswith(f"{BASE}/{code}/") for code in LANGS)]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for loc in english:
        page = next((p for p in PAGES if page_url("en", p) == loc), None)
        variants = [(code, page_url(code, page)) for code, _ in MENU] if page else [("en", loc)]
        for code, url in variants:
            lines += ["    <url>", f"        <loc>{url}</loc>", f"        <lastmod>{lastmod[loc]}</lastmod>"]
            if page:
                lines += [f'        <xhtml:link rel="alternate" hreflang="{c}" href="{u}"/>' for c, u in variants]
                lines.append(f'        <xhtml:link rel="alternate" hreflang="x-default" href="{loc}"/>')
            lines.append("    </url>")
    lines.append("</urlset>")
    new = "\n".join(lines) + "\n"
    if new != old:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def leftovers(lang: str, page: str) -> list[str]:
    """Visible English sentences still on a built page (outside scripts, styles and the SVG paths)."""
    def texts(t):
        t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S)
        t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
        return {" ".join(html.unescape(x).split()) for x in re.findall(r">([^<]+)<", t)}
    keep = {" ".join(html.unescape(re.sub(r"<[^>]+>", "", x)).split()) for x in SAME} | {"Biotide", "Apple Health", "Tidy",
            "Biotide Plus", "iCloud", "OK", "FAQ", "HRV", "Plus", "Psychological Reports", "Cloudflare Web Analytics",
            "Google (Firebase)", "Google Analytics"}
    en = {x for x in texts(english(page)) if re.search(r"[A-Za-z]{3,}.*\s.*[A-Za-z]{3,}", x)}
    built = texts((ROOT / lang / page).read_text(encoding="utf-8"))
    return sorted(x for x in en & built if x not in keep)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    src = source()
    if cmd == "extract":
        (ROOT / "i18n").mkdir(exist_ok=True)
        (ROOT / "i18n" / "source.json").write_text(json.dumps(src, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{len(src)} units -> i18n/source.json")
        return 0
    ids = {u["id"] for u in src}
    if cmd == "status":
        for lang in LANGS:
            have = set(load(lang).get("units", {}))
            print(f"{lang}: {len(ids & have)}/{len(ids)} translated, {len(ids - have)} missing, {len(have - ids)} unused")
        return 0
    if cmd == "build":
        for page in update_english():
            print(f"  updated {page} (hreflang, language menu)")
        # The header (with the menu) reaches privacy.html and 404.html before the languages are built from them.
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_chrome.py")], check=True)
        if write_sitemap():
            print("  updated sitemap.xml (every language, with hreflang)")
        problems = 0
        for lang in LANGS:
            data = load(lang)
            (ROOT / lang).mkdir(exist_ok=True)
            for page in PAGES:
                text, missing = build_page(lang, page, data)
                (ROOT / lang / page).write_text(text, encoding="utf-8")
                left = [] if missing else leftovers(lang, page)
                if left:
                    problems += len(left)
                    print(f"  {lang}/{page}: English left: {left[:4]}")
                if missing:
                    problems += len(missing)
                    print(f"  {lang}/{page}: {len(set(missing))} untranslated: {' '.join(sorted(set(missing))[:8])}…")
                elif not left:
                    print(f"  {lang}/{page}")
        return 1 if problems else 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
