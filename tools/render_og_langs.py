#!/usr/bin/env python3
"""The social preview card in every language: images/og-image-<lang>.png (1200x630).

    python3 tools/render_og_langs.py

Fills tools/og-image.html with the language's headline and line (`@og.headline`, `@og.line` in i18n/<lang>.txt) and
its Today screen (images/<lang>/screen-today.webp), and renders it with the system Chrome in a throwaway profile, like
tools/render_og.sh does for the English card. tools/i18n.py points each language page's og:image and twitter:image at
its card. Re-render when the English card, a headline or a Today screen changes.
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from i18n import LANGS, load  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def card(lang: str) -> str:
    meta = load(lang)["meta"]
    text = (ROOT / "tools" / "og-image.html").read_text(encoding="utf-8")
    text = text.replace('<html lang="en">', f'<html lang="{lang}">', 1)
    text = re.sub(r"<h1>.*?</h1>", lambda _: f"<h1>{meta['og.headline']}</h1>", text, count=1, flags=re.S)
    text = re.sub(r"(<div class=\"text\">.*?)<p>.*?</p>", lambda m: m.group(1) + f"<p>{html.escape(meta['og.line'], quote=False)}</p>",
                  text, count=1, flags=re.S)
    text = text.replace("../images/screen-today.webp", f"../images/{lang}/screen-today.webp")
    # Japanese headlines break between the marked phrases; Korean between words.
    text = text.replace("</style>", "    .phrase { display: inline-block; }\n    :lang(ko) h1, :lang(ko) p { word-break: keep-all; }\n    :lang(ja) h1, :lang(ko) h1 { font-size: 58px; line-height: 1.12; }\n</style>", 1)
    return text


def main() -> int:
    if not Path(CHROME).exists():
        print(f"Chrome not found at {CHROME}")
        return 1
    for lang in LANGS:
        page = ROOT / "tools" / f".og-{lang}.html"
        page.write_text(card(lang), encoding="utf-8")
        out = ROOT / "images" / f"og-image-{lang}.png"
        with tempfile.TemporaryDirectory() as profile:
            subprocess.run([CHROME, "--headless=new", f"--user-data-dir={profile}", "--no-first-run", "--disable-gpu",
                            "--hide-scrollbars", "--window-size=1200,630", "--force-device-scale-factor=1",
                            f"--screenshot={out}", f"file://{page}"], capture_output=True, check=False)
        page.unlink()
        print(f"  wrote images/{out.name}" if out.exists() else f"  failed: {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
