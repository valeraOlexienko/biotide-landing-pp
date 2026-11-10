#!/usr/bin/env bash
# Render tools/og-image.html to images/og-image.png (1200x630) with the system Chrome.
#
#   tools/render_og.sh
#
# Edit the headline, line and screen in tools/og-image.html first. Social networks
# cache the image: after a change, re-share through their debuggers
# (developers.facebook.com/tools/debug, cards-dev.twitter.com/validator) to refresh.
set -euo pipefail
cd "$(dirname "$0")/.."

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
[ -x "$CHROME" ] || { echo "Chrome not found at $CHROME (set CHROME=...)"; exit 1; }

SITE=.
[ -d public ] && SITE=public

"$CHROME" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1200,630 --force-device-scale-factor=1 \
  --screenshot="$PWD/$SITE/images/og-image.png" \
  "file://$PWD/tools/og-image.html" >/dev/null 2>&1

echo "  wrote $SITE/images/og-image.png"
