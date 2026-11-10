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
| `screenshot-1..N.webp` | ~560 px wide | the App Store frames, once they exist (not yet) |
| `screen-*.webp` | 804x1748 | real app screens, also the schema screenshots (see below) |
| `iphone17-black.webp` | 675x1380 | Apple's iPhone 17 bezel (Black), from developer.apple.com/design/resources; used as is |

The icons are the app's own 1024 px icon (`Biotide/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon.png`
in the app repo), scaled down, square and opaque. `tools/placeholder_icons.py` would overwrite
them: don't run it again.

The screens come from the app's screenshot mode (sample data, never a real person's) on the
iPhone 17 Pro spare simulator, light appearance, US region (12-hour clock) and the status bar set
to 9:41, full battery: `-SCREENSHOT_MODE -SCREENSHOT_SCREEN <today|checkIn|insights|plan>`, then
`xcrun simctl io <udid> screenshot`, scaled from 1206x2622 to 804x1748 and saved with
`cwebp -q 84 -m 6`. Re-capture them when those screens change, then re-render the social image.

Rules: every `<img>` has `alt`, `width` and `height` (the SEO check enforces it). Bump the
`?v=` on an image URL when its content changes; Pages caches images for a week.
