import os
import math
import requests
from datetime import datetime

USERNAME = "amine9812"
OUT_DIR = "assets"
LANG_FILE = os.path.join(OUT_DIR, "languages-donut.svg")
CONTRIB_FILE = os.path.join(OUT_DIR, "contributions-grid.svg")

TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
HEADERS = {"Authorization": f"bearer {TOKEN}"} if TOKEN else {}

os.makedirs(OUT_DIR, exist_ok=True)

# ---------- Helpers ----------
def clamp(x, a, b):
    return max(a, min(b, x))

def fmt_pct(x):
    return f"{x:.1f}%"

def svg_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )

def polar_to_cart(cx, cy, r, angle_deg):
    a = math.radians(angle_deg)
    return (cx + r * math.cos(a), cy + r * math.sin(a))

def donut_arc_path(cx, cy, r_outer, r_inner, start_deg, end_deg):
    # SVG arcs go clockwise when sweep-flag=1; use degrees on unit circle
    large = 1 if (end_deg - start_deg) % 360 > 180 else 0
    x1, y1 = polar_to_cart(cx, cy, r_outer, start_deg)
    x2, y2 = polar_to_cart(cx, cy, r_outer, end_deg)
    x3, y3 = polar_to_cart(cx, cy, r_inner, end_deg)
    x4, y4 = polar_to_cart(cx, cy, r_inner, start_deg)

    return (
        f"M {x1:.2f} {y1:.2f} "
        f"A {r_outer:.2f} {r_outer:.2f} 0 {large} 1 {x2:.2f} {y2:.2f} "
        f"L {x3:.2f} {y3:.2f} "
        f"A {r_inner:.2f} {r_inner:.2f} 0 {large} 0 {x4:.2f} {y4:.2f} "
        f"Z"
    )

# ---------- Fetch Languages (aggregate bytes across repos) ----------
def fetch_all_repos():
    repos = []
    session = requests.Session()
    session.headers.update({"Accept": "application/vnd.github+json"})
    if TOKEN:
        session.headers.update({"Authorization": f"Bearer {TOKEN}"})

    page = 1
    while True:
        url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner&sort=pushed"
        r = session.get(url, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
        if page > 20:  # safety
            break
    return repos

def fetch_repo_languages(owner, repo):
    session = requests.Session()
    session.headers.update({"Accept": "application/vnd.github+json"})
    if TOKEN:
        session.headers.update({"Authorization": f"Bearer {TOKEN}"})
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def compute_language_bytes():
    repos = fetch_all_repos()
    totals = {}

    for repo in repos:
        if repo.get("fork"):
            continue
        if repo.get("archived"):
            continue
        owner = repo["owner"]["login"]
        name = repo["name"]
        try:
            langs = fetch_repo_languages(owner, name)
        except Exception:
            continue
        for lang, b in langs.items():
            totals[lang] = totals.get(lang, 0) + int(b)

    # If empty, avoid crash
    if not totals:
        totals = {"Unknown": 1}

    total_bytes = sum(totals.values())
    items = sorted(totals.items(), key=lambda x: x[1], reverse=True)

    # Keep top 8, group rest as Other
    top = items[:8]
    rest = items[8:]
    if rest:
        other_sum = sum(b for _, b in rest)
        top.append(("Other", other_sum))

    data = [(lang, b, (b / total_bytes) * 100.0) for lang, b in top]
    return data

# ---------- Render Languages Donut SVG ----------
def render_languages_donut(data):
    # Color palette (distinct, professional). No external dependencies.
    palette = [
        "#4ade80", "#22c55e", "#16a34a", "#86efac",
        "#10b981", "#34d399", "#059669", "#6ee7b7", "#bbf7d0"
    ]

    width, height = 900, 420
    cx, cy = 220, 210
    r_outer, r_inner = 150, 95
    start = -90.0  # start at top

    # Build arcs
    arcs = []
    legend = []

    legend_x = 460
    legend_y = 110
    legend_step = 28

    for i, (lang, _, pct) in enumerate(data):
        sweep = (pct / 100.0) * 360.0
        end = start + sweep
        color = palette[i % len(palette)]
        path = donut_arc_path(cx, cy, r_outer, r_inner, start, end)
        arcs.append(f'<path d="{path}" fill="{color}" />')
        legend.append(
            f'<rect x="{legend_x}" y="{legend_y + i*legend_step - 12}" width="14" height="14" rx="3" fill="{color}"/>'
            f'<text x="{legend_x + 22}" y="{legend_y + i*legend_step}" fill="#e5e7eb" font-size="14" font-family="Inter,Segoe UI,Arial">'
            f'{svg_escape(lang)} • {fmt_pct(pct)}</text>'
        )
        start = end

    updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#0b1220"/>
  <text x="40" y="52" fill="#ffffff" font-size="22" font-weight="700" font-family="Inter,Segoe UI,Arial">
    Languages — usage distribution
  </text>
  <text x="40" y="80" fill="#9ca3af" font-size="12" font-family="Inter,Segoe UI,Arial">
    Aggregated across non-fork, non-archived repositories • Updated {updated}
  </text>

  <g>
    {''.join(arcs)}
    <circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="#0b1220"/>
    <text x="{cx}" y="{cy-6}" text-anchor="middle" fill="#ffffff" font-size="22" font-weight="700" font-family="Inter,Segoe UI,Arial">Top Languages</text>
    <text x="{cx}" y="{cy+18}" text-anchor="middle" fill="#9ca3af" font-size="12" font-family="Inter,Segoe UI,Arial">{USERNAME}</text>
  </g>

  <text x="{legend_x}" y="78" fill="#ffffff" font-size="16" font-weight="700" font-family="Inter,Segoe UI,Arial">
    Breakdown
  </text>
  <g>
    {''.join(legend)}
  </g>
</svg>
"""
    with open(LANG_FILE, "w", encoding="utf-8") as f:
        f.write(svg)

# ---------- Fetch Contributions (green squares grid) ----------
def fetch_contribution_calendar():
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN missing. Actions provides it automatically; locally you must set it.")

    query = """
    query($login:String!) {
      user(login:$login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
                contributionLevel
              }
            }
          }
        }
      }
    }
    """
    variables = {"login": USERNAME}
    r = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {TOKEN}"},
        json={"query": query, "variables": variables},
        timeout=30,
    )
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        raise RuntimeError(str(j["errors"]))
    weeks = j["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return weeks

def render_contrib_grid(weeks):
    # GitHub-like green palette (dark background)
    level_color = {
        "NONE": "#161b22",
        "FIRST_QUARTILE": "#0e4429",
        "SECOND_QUARTILE": "#006d32",
        "THIRD_QUARTILE": "#26a641",
        "FOURTH_QUARTILE": "#39d353",
    }

    cell = 12
    gap = 3
    pad_x, pad_y = 24, 70

    cols = len(weeks)  # typically 52-53
    rows = 7

    width = pad_x * 2 + cols * (cell + gap) - gap
    height = pad_y + rows * (cell + gap) + 40

    updated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    squares = []
    for x, w in enumerate(weeks):
        days = w["contributionDays"]
        for y, d in enumerate(days):
            lvl = d["contributionLevel"]
            color = level_color.get(lvl, "#161b22")
            rx = 3
            px = pad_x + x * (cell + gap)
            py = pad_y + y * (cell + gap)
            squares.append(f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" rx="{rx}" fill="{color}"/>')

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#0b1220"/>
  <text x="24" y="40" fill="#ffffff" font-size="22" font-weight="700" font-family="Inter,Segoe UI,Arial">
    Contributions — last year
  </text>
  <text x="24" y="62" fill="#9ca3af" font-size="12" font-family="Inter,Segoe UI,Arial">
    Green squares only • Updated {updated}
  </text>

  <g>
    {''.join(squares)}
  </g>

  <!-- Minimal legend -->
  <g>
    <text x="{width-210}" y="{height-18}" fill="#9ca3af" font-size="12" font-family="Inter,Segoe UI,Arial">Less</text>
    <rect x="{width-170}" y="{height-30}" width="12" height="12" rx="3" fill="#161b22"/>
    <rect x="{width-152}" y="{height-30}" width="12" height="12" rx="3" fill="#0e4429"/>
    <rect x="{width-134}" y="{height-30}" width="12" height="12" rx="3" fill="#006d32"/>
    <rect x="{width-116}" y="{height-30}" width="12" height="12" rx="3" fill="#26a641"/>
    <rect x="{width-98}"  y="{height-30}" width="12" height="12" rx="3" fill="#39d353"/>
    <text x="{width-80}" y="{height-18}" fill="#9ca3af" font-size="12" font-family="Inter,Segoe UI,Arial">More</text>
  </g>
</svg>
"""
    with open(CONTRIB_FILE, "w", encoding="utf-8") as f:
        f.write(svg)

def main():
    # Languages donut
    lang_data = compute_language_bytes()
    render_languages_donut(lang_data)

    # Contribution grid
    weeks = fetch_contribution_calendar()
    render_contrib_grid(weeks)

if __name__ == "__main__":
    main()
