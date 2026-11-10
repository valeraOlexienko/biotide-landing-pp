# images/

Everything the pages display is WebP. Exceptions on purpose: `og-image.png` (not every
social network accepts WebP), `favicon.png` and `apple-touch-icon.png` (platform formats),
`logo.png` (schema logo), and Apple's App Store badge SVG.

| File | Size | Source |
|------|------|--------|
| `favicon.png` | 64x64 | the app icon |
| `apple-touch-icon.png` | 180x180 | the app icon, no rounded corners (iOS adds them) |
| `logo.png` | 512x512 | the app icon; referenced by the Organization schema |
| `og-image.png` | 1200x630 | `tools/render_og.sh` from `tools/og-image.html` |
| `download-on-the-app-store.svg` | 156x52 as used | Apple's badge, served locally (no third-party request) |
| `screenshot-1..N.webp` | ~560 px wide | the App Store frames; also the schema screenshots |
| `screen-*.webp` | 1206x2622 (or 804x1748) | raw simulator screens for the bezel slot (iPhone 17) |
| `placeholder-screen.png` | 603x1311 | stand-in from `tools/placeholder_icons.py`; delete once real screens are in |

Rules: every `<img>` has `alt`, `width` and `height` (the SEO check enforces it). Bump the
`?v=` on an image URL when its content changes; Pages caches images for a week.
