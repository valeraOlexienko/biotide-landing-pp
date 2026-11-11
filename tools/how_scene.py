#!/usr/bin/env python3
"""Build the homepage's "How it works" scroll scene and write it into index.html.

    python3 tools/how_scene.py

The scene is one pinned scroll-craft act (landing.js drives it, landing.css lays it out):
the three cycles draw across a month as you scroll, fourteen check-ins land on them, the
fit per curve appears and the curve that fits least fades, then the days ahead draw and the
best days for an exam light up. Apple's iPhone bezel beside it never moves; its screen
follows the steps (Today, the check-in, Insights, Prime days).

Everything is the app's screenshot-mode data, so the chart and the screens agree:
birth date 12 March 1988 (ScreenshotMode.birthDayKey), today Tuesday 10 November 2026,
check-ins made like SampleData.seedCheckIns (energy follows the physical curve, focus the
intellectual one, mood barely the emotional one, with noise; the noise here is our own
deterministic sequence, so single dots differ from the app's), the fit percentages from
the Insights screen and the exam days from the Prime days screen. Re-run after re-capturing
the screens. Writes between <!-- scene:how --> and <!-- /scene:how --> in index.html.
"""
import datetime as dt
import html
import math
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"

BIRTH = dt.date(1988, 3, 12)
TODAY = dt.date(2026, 11, 10)
START = TODAY - dt.timedelta(days=14)        # 27 Oct: fourteen check-ins before today
DAYS = 30                                    # through 26 Nov
PERIODS = {"physical": 23, "emotional": 28, "intellectual": 33}
FIT = [("physical", "Physical", "97%", "fits"), ("emotional", "Emotional", "57%", "counts less"),
       ("intellectual", "Intellectual", "93%", "fits")]
EXAM_DAYS = [dt.date(2026, 11, 15), dt.date(2026, 11, 17), dt.date(2026, 11, 19)]   # the Prime days screen

# act progress -> share of the chart drawn: the past to today, a hold for the fit, then the days ahead
TODAY_F = 14 / DAYS
WARP = [(0.03, 0.0), (0.36, TODAY_F), (0.62, TODAY_F), (0.84, 1.0)]
STEP_FROM = {"today": 0.0, "checkin": 0.17, "insights": 0.40, "plan": 0.62}
FIT_AT, FIT_UNTIL, WEIGHT_AT = 0.43, 0.61, 0.47

W, TOP, BOTTOM = 1000.0, 40.0, 420.0
TICK_DAYS = (1, 5, 10, 15, 20, 25)
ZERO = (TOP + BOTTOM) / 2


def value(cycle, day_offset):
    t = (START - BIRTH).days + day_offset
    return math.sin(2 * math.pi * t / PERIODS[cycle])


def x_of(day_offset):
    return day_offset / DAYS * W


def y_of(v):                                  # v in -1...1
    return ZERO - v * (BOTTOM - TOP) / 2


def progress_at(f):                           # the act progress at which the drawing edge reaches f
    for (p0, f0), (p1, f1) in zip(WARP, WARP[1:]):
        if f1 > f0 and f0 <= f <= f1:
            return p0 + (f - f0) / (f1 - f0) * (p1 - p0)
    return WARP[-1][0]


def path(cycle):
    pts = []
    steps = DAYS * 5
    for k in range(steps + 1):
        d = k / 5
        pts.append(f"{x_of(d):.1f},{y_of(value(cycle, d)):.1f}")
    return "M" + " L".join(pts)


def checkins():
    rnd = random.Random(20261101)
    out = []
    for i in range(14):
        def level(signal):
            noise = rnd.uniform(-1.1, 1.1)
            return min(5, max(1, round(3 + 1.7 * signal + noise)))
        out.append({
            "physical": level(value("physical", i)),          # energy
            "emotional": level(value("emotional", i) * 0.2),  # mood
            "intellectual": level(value("intellectual", i)),  # focus
        })
    return out


def svg():
    e = []
    e.append('<svg class="cyc" viewBox="0 0 1000 480" preserveAspectRatio="xMidYMid meet" aria-hidden="true" focusable="false">')
    e.append('<defs><clipPath id="cyc-reveal"><rect class="cyc__reveal" x="-10" y="0" width="1020" height="480"/></clipPath></defs>')
    # the exam days, behind everything
    for d in EXAM_DAYS:
        i = (d - START).days
        at = progress_at(i / DAYS)
        num = "" if d.day in TICK_DAYS else f'<text x="{x_of(i):.1f}" y="{BOTTOM + 34:.0f}">{d.day}</text>'
        e.append(f'<g class="cyc__best" data-at="{at:.3f}"><rect x="{x_of(i) - 15:.1f}" y="{TOP - 8:.0f}" width="30" height="{BOTTOM - TOP + 16:.0f}" rx="15"/>{num}</g>')
    e.append(f'<text class="cyc__label cyc__best-label" data-at="{progress_at((EXAM_DAYS[0] - START).days / DAYS):.3f}" x="{x_of((EXAM_DAYS[1] - START).days):.1f}" y="22">Best days for an exam</text>')
    # axes
    e.append(f'<line class="cyc__zero" x1="0" x2="1000" y1="{ZERO:.1f}" y2="{ZERO:.1f}"/>')
    ti = (TODAY - START).days
    e.append(f'<line class="cyc__today" x1="{x_of(ti):.1f}" x2="{x_of(ti):.1f}" y1="{TOP - 8:.0f}" y2="{BOTTOM + 8:.0f}"/>')
    e.append(f'<text class="cyc__label cyc__today-label" x="{x_of(ti):.1f}" y="22">Today</text>')
    for d in range(DAYS + 1):
        day = START + dt.timedelta(days=d)
        near_best = any(abs((day - b).days) == 1 for b in EXAM_DAYS)   # a lit day number sits there
        if day.day in TICK_DAYS and not near_best:
            txt = day.strftime("%b") if day.day == 1 else str(day.day)
            e.append(f'<text class="cyc__tick" x="{x_of(d):.1f}" y="{BOTTOM + 34:.0f}">{txt}</text>')
    # the curves and the check-ins, revealed by the clip
    e.append('<g clip-path="url(#cyc-reveal)">')
    for c in PERIODS:
        e.append(f'<path class="cyc__line cyc__line--{c}" d="{path(c)}"/>')
    e.append('</g>')
    offsets = {"physical": -8, "emotional": 0, "intellectual": 8}
    for i, ci in enumerate(checkins()):
        at = progress_at((i + 0.5) / DAYS)
        dots = "".join(f'<circle class="cyc__dot cyc__dot--{c}" cx="{x_of(i) + offsets[c]:.1f}" cy="{y_of((ci[c] - 3) / 2):.1f}" r="6"/>' for c in PERIODS)
        e.append(f'<g class="cyc__day" data-at="{at:.3f}">{dots}</g>')
    # the fit, in the empty days ahead while they are still undrawn
    fx = x_of(ti) + 70
    e.append(f'<g class="cyc__fit" data-at="{FIT_AT}" data-until="{FIT_UNTIL}">')
    e.append(f'<text class="cyc__fit-head" x="{fx:.0f}" y="{TOP + 40:.0f}">How often each curve matched</text>')
    for r, (c, name, pct, verdict) in enumerate(FIT):
        y = TOP + 104 + r * 74
        e.append(f'<g class="cyc__fit-row cyc__fit-row--{c}"><line x1="{fx:.0f}" x2="{fx + 34:.0f}" y1="{y - 9:.0f}" y2="{y - 9:.0f}"/>'
                 f'<text x="{fx + 50:.0f}" y="{y:.0f}">{name}</text><text class="cyc__fit-pct" x="{fx + 330:.0f}" y="{y:.0f}">{pct}</text>'
                 f'<text class="cyc__fit-verdict" x="{fx + 346:.0f}" y="{y:.0f}">{verdict}</text></g>')
    e.append('</g>')
    e.append(f'<line class="cyc__cursor" x1="0" x2="0" y1="{TOP - 8:.0f}" y2="{BOTTOM + 8:.0f}"/>')
    e.append('</svg>')
    return "\n                    ".join(e)


# Each screen comes in light and dark (images/screen-NAME.webp and screen-NAME-dark.webp); the dark one is a
# <source data-dark> that site.js points at the page's theme.
SCREEN_VERSION = 2

SCREENS = [
    ("today", 0, "images/screen-today.webp", "Biotide's Today screen for Tuesday, November 10: physical 0, emotional +78, intellectual −37 and the three curves across the month"),
    ("checkin", 0, "images/screen-checkin.webp", "The daily check-in: energy, mood, focus and last night's sleep, each rated from 1 to 5, with an optional note"),
    ("insights", 1, "images/screen-insights.webp", "Insights: Apple Health signals against your usual, two weeks of check-in averages, and how often each curve matched how you felt"),
    ("plan", 2, "images/screen-plan.webp", "Prime days for an exam: the best days in the next 30, the first on Tuesday, November 17"),
]

STEPS = [
    ("Check in", "Your birth date draws the three curves. Each evening, rate your energy, mood, focus and sleep in about thirty seconds, and every check-in lands on the chart."),
    ("See what fits", "After 14 check-ins Biotide shows how often each curve matched how you felt. Here the emotional curve matched only 57% of the time, so it counts for less."),
    ("Plan ahead", "Pick an exam, an interview or an important conversation, and Biotide ranks the days ahead with the curves that fit you: here, the 15th, 17th and 19th."),
]


def scene():
    warp = "[" + ", ".join(f"[{p}, {f:.4f}]" for p, f in WARP) + "]"
    screens = "".join(
        f'<picture class="themed"><source srcset="{src.replace(".webp", "-dark.webp")}?v={SCREEN_VERSION}" media="(prefers-color-scheme: dark)" data-dark>'
        f'<img class="how-screen" data-step="{step}" data-from="{STEP_FROM[key]}" src="{src}?v={SCREEN_VERSION}" width="804" height="1748" alt="{html.escape(alt)}" loading="lazy"></picture>'
        for key, step, src, alt in SCREENS)
    steps = "\n".join(
        f'                    <li class="how-step"><h3>{html.escape(h)}</h3><p>{html.escape(p)}</p></li>' for h, p in STEPS)
    return f'''<!-- scene:how (generated by tools/how_scene.py; edit the script, not this block) -->
    <section class="how-intro" id="how">
        <div class="wrap">
            <div class="section-head">
                <h2>How it works</h2>
                <p>From your birth date to your best days, in three steps.</p>
            </div>
        </div>
    </section>

    <!-- The month as the app draws it: the three cycles draw as you scroll, the check-ins land on
         them, the fit appears and the weakest curve fades, then the days ahead draw and the best
         days light up. The phone beside it never moves (Apple product-image rules); only its
         screen follows the steps. Opacity and a clip only: nothing slides or parallaxes. -->
    <section class="how-act" data-sc-act="pin" data-sc-span="5">
        <div data-sc-stage class="how-stage">
            <div class="wrap how-stage__grid">
                <figure class="cyc-wrap" data-warp="{warp}" data-start="{START.isoformat()}" data-days="{DAYS}" data-weight="{WEIGHT_AT}">
                    <p class="cyc__date" aria-hidden="true">{TODAY.strftime("%a, %b %-d")}</p>
                    {svg()}
                    <figcaption class="cyc__note">Sample data, as on the screens: the cycles for a birth date of 12 March 1988, two weeks of check-ins and the best days for an exam. The curves&rsquo; guess.</figcaption>
                </figure>
                <ol class="how-steps">
{steps}
                </ol>
                <div class="phone how-phone"><div class="phone__screen">{screens}</div><img class="phone__frame" src="images/iphone17-black.webp" width="675" height="1380" alt="" aria-hidden="true" loading="lazy"></div>
            </div>
        </div>
    </section>
    <!-- /scene:how -->'''


def main():
    s = INDEX.read_text(encoding="utf-8")
    block = scene()
    m = re.search(r"<!-- scene:how.*?<!-- /scene:how -->", s, re.S)
    if m:
        s = s[:m.start()] + block + s[m.end():]
    else:   # first run: replace the plain "How it works" section
        m = re.search(r'    <!-- HOW IT WORKS:.*?\n    <section class="section" id="how">.*?\n    </section>', s, re.S)
        if not m:
            raise SystemExit("no scene markers and no plain #how section in index.html")
        s = s[:m.start()] + "    " + block + s[m.end():]
    INDEX.write_text(s, encoding="utf-8")
    print("  wrote the How it works scene into index.html")


if __name__ == "__main__":
    main()
