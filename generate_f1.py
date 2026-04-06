#!/usr/bin/env python3
"""
generate_f1.py
Fetches GitHub contribution data for a user and generates an animated
F1 race track SVG where the car's speed/glow reflects contribution intensity.
Output: dist/f1-contribution.svg  and  dist/f1-contribution-dark.svg
"""

import os
import sys
import json
import math
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_USER  = os.environ.get("GITHUB_USER", "mauryashah137")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUTPUT_DIR   = "dist"
# ──────────────────────────────────────────────────────────────────────────────


def fetch_contributions():
    """Use GitHub GraphQL API to get the last 52 weeks of contribution data."""
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
                color
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"login": GITHUB_USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "f1-readme-generator",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    total = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    # Flatten to list of (date, count, color)
    days = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append({
                "date":  day["date"],
                "count": day["contributionCount"],
                "color": day["color"],
            })
    return days, total


def contribution_level(count, max_count):
    """Return 0-4 level for a contribution count."""
    if count == 0:
        return 0
    if max_count == 0:
        return 1
    ratio = count / max_count
    if ratio < 0.25:
        return 1
    if ratio < 0.50:
        return 2
    if ratio < 0.75:
        return 3
    return 4


def make_svg(days, total, dark=False):
    """
    Generate the full F1 animated SVG.

    Layout:
    - Top:    Title bar  ("🏎  LAP TIMES  —  Contributions in Motion")
    - Middle: F1 oval race track with animated car
    - Bottom: 52-week contribution heatmap grid (like GitHub's)
    - The car speed pulses faster on weeks with more contributions
    """

    # ── Dimensions ────────────────────────────────────────────────────────────
    W, H          = 860, 480
    TRACK_CX      = 430
    TRACK_CY      = 175
    TRACK_RX      = 330   # horizontal radius of oval center-line
    TRACK_RY      = 100   # vertical radius
    TRACK_WIDTH   = 38    # road width

    GRID_TOP      = 310   # y-start of contribution grid
    CELL          = 11    # cell size
    GAP           = 2     # gap between cells
    GRID_LEFT     = 20    # x-start

    # ── Color themes ──────────────────────────────────────────────────────────
    if dark:
        BG          = "#0d1117"
        TRACK_FILL  = "#161b22"
        TRACK_ROAD  = "#21262d"
        TRACK_EDGE  = "#30363d"
        KERB_A      = "#e10600"
        KERB_B      = "#ffffff"
        TEXT_COLOR  = "#8b949e"
        TEXT_BRIGHT = "#e6edf3"
        CELL_EMPTY  = "#161b22"
        CELL_COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
        SECTOR_BG   = "#161b22"
    else:
        BG          = "#ffffff"
        TRACK_FILL  = "#f0f0f0"
        TRACK_ROAD  = "#d0d0d0"
        TRACK_EDGE  = "#bbbbbb"
        KERB_A      = "#e10600"
        KERB_B      = "#ffffff"
        TEXT_COLOR  = "#57606a"
        TEXT_BRIGHT = "#24292f"
        CELL_EMPTY  = "#ebedf0"
        CELL_COLORS = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
        SECTOR_BG   = "#f6f8fa"

    # ── Pre-compute contribution stats ────────────────────────────────────────
    max_count   = max((d["count"] for d in days), default=1) or 1
    # Group into 52 weeks
    weeks = []
    for i in range(0, len(days), 7):
        weeks.append(days[i:i+7])
    # Trim to last 52
    weeks = weeks[-52:]

    # Weekly totals for speed modulation (used in JS)
    weekly_totals = [sum(d["count"] for d in w) for w in weeks]
    max_weekly    = max(weekly_totals) or 1

    # ── Build SVG strings ─────────────────────────────────────────────────────
    lines = []
    a = lines.append  # shorthand

    a(f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
      f'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">')

    # ── DEFS ──────────────────────────────────────────────────────────────────
    a('<defs>')

    # Car glow
    a(f'''  <filter id="carGlow" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="blur"/>
    <feColorMatrix in="blur" type="matrix"
      values="3 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.8 0" result="red"/>
    <feMerge><feMergeNode in="red"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>''')

    # Flame glow
    a(f'''  <filter id="flameGlow" x="-100%" y="-100%" width="300%" height="300%">
    <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur"/>
    <feColorMatrix in="blur" type="matrix"
      values="4 0 0 0 0.3  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="c"/>
    <feMerge><feMergeNode in="c"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>''')

    # Track center path (used for animateMotion)
    a(f'  <path id="racepath" d="M {TRACK_CX} {TRACK_CY - TRACK_RY} '
      f'A {TRACK_RX} {TRACK_RY} 0 0 1 {TRACK_CX} {TRACK_CY + TRACK_RY} '
      f'A {TRACK_RX} {TRACK_RY} 0 0 1 {TRACK_CX} {TRACK_CY - TRACK_RY} Z" fill="none"/>')

    a('</defs>')

    # ── BACKGROUND ────────────────────────────────────────────────────────────
    a(f'<rect width="{W}" height="{H}" fill="{BG}"/>')

    # Subtle horizontal rule
    a(f'<line x1="0" y1="295" x2="{W}" y2="295" stroke="{TRACK_EDGE}" stroke-width="0.5" opacity="0.4"/>')

    # ── TITLE BAR ─────────────────────────────────────────────────────────────
    a(f'<text x="20" y="26" fill="{TEXT_BRIGHT}" font-size="13" '
      f'font-family="\'Courier New\',monospace" font-weight="bold" letter-spacing="2">'
      f'🏎  LAP TIMES</text>')
    a(f'<text x="20" y="44" fill="{TEXT_COLOR}" font-size="10" '
      f'font-family="\'Courier New\',monospace" letter-spacing="1">'
      f'Contributions in Motion  ·  {total} commits this year</text>')

    # ── TRACK SURFACE ─────────────────────────────────────────────────────────
    OUTER_RX = TRACK_RX + TRACK_WIDTH // 2 + 6
    OUTER_RY = TRACK_RY + TRACK_WIDTH // 2 + 6
    INNER_RX = TRACK_RX - TRACK_WIDTH // 2 - 2
    INNER_RY = TRACK_RY - TRACK_WIDTH // 2 - 2

    # Outer kerb (red/white alternating dashes)
    a(f'<ellipse cx="{TRACK_CX}" cy="{TRACK_CY}" rx="{OUTER_RX}" ry="{OUTER_RY}" '
      f'fill="none" stroke="{KERB_A}" stroke-width="7" '
      f'stroke-dasharray="20 20" opacity="0.75"/>')
    a(f'<ellipse cx="{TRACK_CX}" cy="{TRACK_CY}" rx="{OUTER_RX}" ry="{OUTER_RY}" '
      f'fill="none" stroke="{KERB_B}" stroke-width="7" '
      f'stroke-dasharray="20 20" stroke-dashoffset="20" opacity="0.45"/>')

    # Road surface
    a(f'<ellipse cx="{TRACK_CX}" cy="{TRACK_CY}" rx="{TRACK_RX + TRACK_WIDTH//2}" ry="{TRACK_RY + TRACK_WIDTH//2}" '
      f'fill="none" stroke="{TRACK_ROAD}" stroke-width="{TRACK_WIDTH}"/>')

    # Inner kerb
    a(f'<ellipse cx="{TRACK_CX}" cy="{TRACK_CY}" rx="{INNER_RX}" ry="{INNER_RY}" '
      f'fill="none" stroke="{KERB_A}" stroke-width="4" '
      f'stroke-dasharray="12 12" opacity="0.55"/>')
    a(f'<ellipse cx="{TRACK_CX}" cy="{TRACK_CY}" rx="{INNER_RX}" ry="{INNER_RY}" '
      f'fill="none" stroke="{KERB_B}" stroke-width="4" '
      f'stroke-dasharray="12 12" stroke-dashoffset="12" opacity="0.3"/>')

    # Center lane dashes
    a(f'<ellipse cx="{TRACK_CX}" cy="{TRACK_CY}" rx="{TRACK_RX}" ry="{TRACK_RY}" '
      f'fill="none" stroke="{KERB_B}" stroke-width="1" '
      f'stroke-dasharray="16 14" opacity="0.12"/>')

    # Tire marks at corners
    for (x1, y1, cx2, cy2, x3, y3) in [
        (TRACK_CX - TRACK_RX + 28, TRACK_CY - 35,
         TRACK_CX - TRACK_RX + 10, TRACK_CY,
         TRACK_CX - TRACK_RX + 28, TRACK_CY + 35),
        (TRACK_CX + TRACK_RX - 28, TRACK_CY - 35,
         TRACK_CX + TRACK_RX - 10, TRACK_CY,
         TRACK_CX + TRACK_RX - 28, TRACK_CY + 35),
    ]:
        a(f'<path d="M {x1} {y1} Q {cx2} {cy2} {x3} {y3}" '
          f'fill="none" stroke="#000000" stroke-width="7" opacity="0.18"/>')
        a(f'<path d="M {x1+8} {y1} Q {cx2+6} {cy2} {x3+8} {y3}" '
          f'fill="none" stroke="#000000" stroke-width="5" opacity="0.12"/>')

    # Start/Finish line (top center)
    sf_x = TRACK_CX
    sf_y_top    = TRACK_CY - TRACK_RY - TRACK_WIDTH // 2 - 6
    sf_y_bottom = TRACK_CY - TRACK_RY + TRACK_WIDTH // 2 + 6
    a(f'<rect x="{sf_x - 4}" y="{sf_y_top}" width="8" height="{sf_y_bottom - sf_y_top}" fill="white" opacity="0.9"/>')
    # Checker pattern over it
    ch_h = (sf_y_bottom - sf_y_top) // 4
    for row in range(4):
        for col in range(2):
            if (row + col) % 2 == 0:
                a(f'<rect x="{sf_x - 4 + col*4}" y="{sf_y_top + row*ch_h}" '
                  f'width="4" height="{ch_h}" fill="#111" opacity="0.85"/>')

    # S/F label
    a(f'<text x="{sf_x + 10}" y="{sf_y_top + 14}" fill="{KERB_A}" '
      f'font-size="9" font-family="\'Courier New\',monospace" font-weight="bold" letter-spacing="1">S/F</text>')

    # DRS zone label (top straight)
    drs_x = TRACK_CX - 55
    drs_y = TRACK_CY - TRACK_RY - TRACK_WIDTH // 2 - 10
    a(f'<rect x="{drs_x}" y="{drs_y - 10}" width="110" height="12" rx="2" fill="#00d2be" opacity="0.12"/>')
    a(f'<text x="{drs_x + 55}" y="{drs_y}" fill="#00d2be" font-size="8" '
      f'font-family="\'Courier New\',monospace" text-anchor="middle" letter-spacing="1.5" opacity="0.7">'
      f'DRS ZONE</text>')

    # Sector markers
    sectors = [
        (TRACK_CX + TRACK_RX + 12, TRACK_CY - 8, "S1", "#ffcc00"),
        (TRACK_CX - 14,             TRACK_CY + TRACK_RY + 14, "S2", "#00d2be"),
        (TRACK_CX - TRACK_RX - 36,  TRACK_CY - 8, "S3", TEXT_COLOR),
    ]
    for sx, sy, label, sc in sectors:
        a(f'<rect x="{sx}" y="{sy}" width="24" height="16" rx="2" '
          f'fill="{SECTOR_BG}" stroke="{sc}" stroke-width="0.8"/>')
        a(f'<text x="{sx + 12}" y="{sy + 11}" fill="{sc}" font-size="8" '
          f'font-family="monospace" text-anchor="middle">{label}</text>')

    # Lap counter (top-left of track area)
    a(f'<rect x="20" y="62" width="64" height="28" rx="3" '
      f'fill="{SECTOR_BG}" stroke="{KERB_A}" stroke-width="0.8"/>')
    a(f'<text x="52" y="74" fill="{KERB_A}" font-size="8" '
      f'font-family="monospace" text-anchor="middle" letter-spacing="1">LAP</text>')
    a(f'<text x="52" y="85" fill="{TEXT_BRIGHT}" font-size="9" '
      f'font-family="monospace" text-anchor="middle" font-weight="bold">∞ / ∞</text>')

    # Speed display (top-right of track area)
    a(f'<rect x="{W - 84}" y="62" width="64" height="28" rx="3" '
      f'fill="{SECTOR_BG}" stroke="#00d2be" stroke-width="0.8"/>')
    a(f'<text x="{W - 52}" y="74" fill="#00d2be" font-size="7" '
      f'font-family="monospace" text-anchor="middle" letter-spacing="1">KM/H</text>')
    # Animated speed numbers
    speed_vals = "312;318;305;328;295;320;312"
    a(f'<text x="{W - 52}" y="86" fill="{TEXT_BRIGHT}" font-size="10" '
      f'font-family="monospace" text-anchor="middle" font-weight="bold">'
      f'<animate attributeName="textContent" values="{speed_vals}" dur="4s" repeatCount="indefinite"/>'
      f'312</text>')

    # ── F1 CAR ────────────────────────────────────────────────────────────────
    a('<g id="f1car" filter="url(#carGlow)">')

    # Speed lines (visible on straights)
    a('''  <g id="speedlines">
    <line x1="-8" y1="-3.5" x2="-30" y2="-3.5" stroke="#ff4400" stroke-width="1.2" opacity="0.7"/>
    <line x1="-6" y1="0"    x2="-36" y2="0"    stroke="#ff6600" stroke-width="1.8" opacity="0.9"/>
    <line x1="-8" y1="3.5"  x2="-30" y2="3.5"  stroke="#ff4400" stroke-width="1.2" opacity="0.7"/>
    <line x1="-4" y1="-6"   x2="-22" y2="-6"   stroke="#ff2200" stroke-width="0.8" opacity="0.5"/>
    <line x1="-4" y1="6"    x2="-22" y2="6"    stroke="#ff2200" stroke-width="0.8" opacity="0.5"/>
    <animate attributeName="opacity" values="0;0;1;1;0;0;1;1;0" dur="4s" repeatCount="indefinite"/>
  </g>''')

    # Exhaust flame
    a('''  <g filter="url(#flameGlow)">
    <ellipse cx="-16" cy="0" rx="7" ry="2.5" fill="#ff6600">
      <animate attributeName="rx" values="7;11;5;9;6;10;7" dur="0.18s" repeatCount="indefinite"/>
      <animate attributeName="ry" values="2.5;3.5;1.5;3;2;3.5;2.5" dur="0.18s" repeatCount="indefinite"/>
      <animate attributeName="fill" values="#ff6600;#ffaa00;#ff3300;#ff8800;#ff6600" dur="0.2s" repeatCount="indefinite"/>
    </ellipse>
    <ellipse cx="-21" cy="0" rx="4" ry="1.5" fill="#ffdd00" opacity="0.7">
      <animate attributeName="rx" values="4;7;3;5;4" dur="0.22s" repeatCount="indefinite"/>
    </ellipse>
  </g>''')

    # Rear wing
    a('''  <rect x="-14" y="-9" width="2.5" height="18" rx="0.5" fill="#990000"/>
  <rect x="-13" y="-10" width="11" height="3.5" rx="0.5" fill="#cc0000"/>
  <rect x="-13" y="-7"  width="9"  height="2.5" rx="0.5" fill="#aa0000"/>''')

    # Car body
    a('''  <path d="M -11 -5 L 12 -4 L 16 -2 L 16 2 L 12 4 L -11 5 L -13 3 L -13 -3 Z" fill="#e10600"/>
  <path d="M -11 -5 L 9 -4 L 13 -2.5 L -9 -3 Z" fill="#ff3333" opacity="0.4"/>''')

    # Sidepod vents
    for vx in [-4, -2, 0, 2]:
        a(f'  <rect x="{vx}" y="-5" width="1" height="3" rx="0.5" fill="#aa0000" opacity="0.7"/>')

    # Halo + cockpit
    a('''  <path d="M 0 -3.5 Q 5 -6.5 11 -3.5 Q 5 -5 0 -3.5" fill="none" stroke="#1a1a1a" stroke-width="2.2"/>
  <ellipse cx="4" cy="0" rx="4.5" ry="2.8" fill="#0a0a1a"/>
  <ellipse cx="4.5" cy="-0.5" rx="2.8" ry="1.6" fill="#1a2a6c" opacity="0.9"/>
  <line x1="2.5" y1="-1.2" x2="6.5" y2="-0.5" stroke="#88bbff" stroke-width="0.6" opacity="0.6"/>''')

    # Nose + front wing
    a('''  <path d="M 12 -2 L 20 -1 L 20 1 L 12 2 Z" fill="#cc0000"/>
  <path d="M 18 -1 L 22 0 L 18 1 Z" fill="#aa0000"/>
  <rect x="13" y="-7.5" width="8" height="3" rx="0.5" fill="#cc0000"/>
  <rect x="13" y="4.5"  width="8" height="3" rx="0.5" fill="#cc0000"/>
  <rect x="20" y="-7.5" width="2" height="15" rx="0.5" fill="#990000"/>''')

    # Wheels with spinning rims
    for wx, wy, rx_, ry_ in [(-7, -6.5, 2.5, 3.8), (-7, 6.5, 2.5, 3.8),
                               (8, -6, 1.8, 2.8),  (8, 6,  1.8, 2.8)]:
        a(f'  <ellipse cx="{wx}" cy="{wy}" rx="{rx_}" ry="{ry_}" fill="#1a1a1a" stroke="#333" stroke-width="0.8"/>')
        a(f'  <ellipse cx="{wx}" cy="{wy}" rx="{rx_*0.48:.1f}" ry="{ry_*0.48:.1f}" fill="none" '
          f'stroke="#e10600" stroke-width="0.6" opacity="0.6">'
          f'<animateTransform attributeName="transform" type="rotate" '
          f'from="0 {wx} {wy}" to="360 {wx} {wy}" dur="0.28s" repeatCount="indefinite"/>'
          f'</ellipse>')

    # Car number
    a('  <text x="-1" y="2" fill="white" font-size="5.5" font-family="\'Arial Black\',monospace" '
      'font-weight="900" text-anchor="middle" opacity="0.9">13</text>')

    a('</g>')  # end f1car

    # Ghost/shadow car
    a('<g id="ghostcar" opacity="0.15">'
      '<ellipse cx="0" cy="0" rx="24" ry="9" fill="#e10600"/>'
      '</g>')

    # ── ANIMATE MOTION ────────────────────────────────────────────────────────
    # Base duration — faster when contributions are high
    # We use a fixed 4s but modulate via JS below
    a('<animateMotion href="#f1car" dur="4s" repeatCount="indefinite" rotate="auto">'
      '<mpath href="#racepath"/>'
      '</animateMotion>')
    a('<animateMotion href="#ghostcar" dur="4s" begin="-0.35s" repeatCount="indefinite" rotate="auto">'
      '<mpath href="#racepath"/>'
      '</animateMotion>')

    # ── CONTRIBUTION GRID ─────────────────────────────────────────────────────
    # Month labels
    month_labels = []
    prev_month = None
    for wi, week in enumerate(weeks):
        if week:
            m = datetime.fromisoformat(week[0]["date"]).strftime("%b")
            if m != prev_month:
                month_labels.append((wi, m))
                prev_month = m

    for wi, label in month_labels:
        lx = GRID_LEFT + wi * (CELL + GAP)
        a(f'<text x="{lx}" y="{GRID_TOP - 4}" fill="{TEXT_COLOR}" '
          f'font-size="9" font-family="monospace">{label}</text>')

    # Day-of-week labels (Mon, Wed, Fri)
    for dow, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        ly = GRID_TOP + dow * (CELL + GAP) + CELL - 1
        a(f'<text x="{GRID_LEFT - 18}" y="{ly}" fill="{TEXT_COLOR}" '
          f'font-size="8" font-family="monospace">{label}</text>')

    # Cells
    for wi, week in enumerate(weeks):
        cx = GRID_LEFT + wi * (CELL + GAP)
        for di, day in enumerate(week):
            cy = GRID_TOP + di * (CELL + GAP)
            level = contribution_level(day["count"], max_count)
            color = CELL_COLORS[level]
            tooltip = f'{day["date"]}: {day["count"]} contributions'
            a(f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="2" '
              f'fill="{color}" opacity="0.95">'
              f'<title>{tooltip}</title>'
              f'</rect>')

    # Legend
    legend_x = W - 140
    legend_y = GRID_TOP + 7 * (CELL + GAP) + 10
    a(f'<text x="{legend_x}" y="{legend_y}" fill="{TEXT_COLOR}" font-size="9" font-family="monospace">Less</text>')
    for i, c in enumerate(CELL_COLORS):
        a(f'<rect x="{legend_x + 32 + i * (CELL + 2)}" y="{legend_y - 9}" '
          f'width="{CELL}" height="{CELL}" rx="2" fill="{c}"/>')
    a(f'<text x="{legend_x + 32 + 5 * (CELL + 2) + 4}" y="{legend_y}" '
      f'fill="{TEXT_COLOR}" font-size="9" font-family="monospace">More</text>')

    # ── FOOTER ────────────────────────────────────────────────────────────────
    a(f'<text x="{W // 2}" y="{H - 10}" text-anchor="middle" fill="{TEXT_COLOR}" '
      f'font-size="9" font-family="\'Courier New\',monospace" letter-spacing="3" opacity="0.6">'
      f'LIGHTS OUT AND AWAY WE GO  🏁</text>')

    a('</svg>')
    return "\n".join(lines)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Fetching contributions for {GITHUB_USER}...")
    days, total = fetch_contributions()
    print(f"  {total} total contributions, {len(days)} days fetched.")

    print("Generating light SVG...")
    svg_light = make_svg(days, total, dark=False)
    with open(f"{OUTPUT_DIR}/f1-contribution.svg", "w", encoding="utf-8") as f:
        f.write(svg_light)

    print("Generating dark SVG...")
    svg_dark = make_svg(days, total, dark=True)
    with open(f"{OUTPUT_DIR}/f1-contribution-dark.svg", "w", encoding="utf-8") as f:
        f.write(svg_dark)

    print("Done! Files written to dist/")


if __name__ == "__main__":
    main()
