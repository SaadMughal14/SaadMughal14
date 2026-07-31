#!/usr/bin/env python3
"""
Fetches real GitHub stats for STATS_USERNAME (via the GitHub GraphQL API) and
regenerates stats.svg, langs.svg, and trophies.svg with live numbers, in the
same visual style/animation as the rest of the profile.

Run by .github/workflows/update-stats.yml on a daily schedule, on push to
main, and on manual dispatch. Requires GH_TOKEN (a token with public read
access - the default GITHUB_TOKEN works for a user's own public data).
"""
import os
import sys
import datetime
import requests

GRAPHQL_URL = "https://api.github.com/graphql"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
LOGIN = os.environ.get("STATS_USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER")

if not TOKEN or not LOGIN:
    print("Missing GH_TOKEN or STATS_USERNAME/GITHUB_REPOSITORY_OWNER", file=sys.stderr)
    sys.exit(1)

SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"bearer {TOKEN}"})

# our established palette (matches banner.svg / trophies.svg / langs.svg)
BLUE, CYAN, AMBER, TEAL, INDIGO, CORAL, GOLD, SKY = (
    "#3b82f6", "#00d9ff", "#f5a623", "#17e6c8", "#818cf8", "#ff8a65", "#ffd166", "#38bdf8"
)
BG = "#060a14"


def gql(query, variables):
    r = SESSION.post(GRAPHQL_URL, json={"query": query, "variables": variables}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_user_basics():
    q = """
    query($login: String!) {
      user(login: $login) {
        createdAt
        followers { totalCount }
      }
    }"""
    d = gql(q, {"login": LOGIN})["user"]
    return d


def fetch_contributions_all_years(created_at):
    start_year = int(created_at[:4])
    this_year = datetime.datetime.utcnow().year
    total_commits = total_prs = total_issues = 0
    contributed_repos = set()
    q = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          repositoryContributions: totalRepositoryContributions
        }
      }
    }"""
    for year in range(start_year, this_year + 1):
        frm = f"{year}-01-01T00:00:00Z"
        to = f"{year}-12-31T23:59:59Z"
        d = gql(q, {"login": LOGIN, "from": frm, "to": to})["user"]["contributionsCollection"]
        total_commits += d["totalCommitContributions"]
        total_prs += d["totalPullRequestContributions"]
        total_issues += d["totalIssueContributions"]
    return total_commits, total_prs, total_issues


def fetch_repos_and_languages():
    q = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes {
            stargazerCount
            languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
      }
    }"""
    total_stars = 0
    total_repos = 0
    lang_sizes = {}
    lang_colors = {}
    after = None
    while True:
        d = gql(q, {"login": LOGIN, "after": after})["user"]["repositories"]
        total_repos = d["totalCount"]
        for repo in d["nodes"]:
            total_stars += repo["stargazerCount"]
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                lang_sizes[name] = lang_sizes.get(name, 0) + edge["size"]
                lang_colors[name] = edge["node"]["color"] or BLUE
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return total_stars, total_repos, lang_sizes, lang_colors


def compute_rank(stars, commits, prs, issues, followers):
    score = stars * 3 + commits * 0.3 + prs * 2 + issues * 1 + followers * 2
    if score > 1500: return "S+"
    if score > 800: return "S"
    if score > 400: return "A+"
    if score > 200: return "A"
    if score > 100: return "A-"
    if score > 40: return "B+"
    if score > 15: return "B"
    return "C+"


def gen_stats_svg(stars, commits, prs, issues, contributed, rank, path):
    dash = 327
    offset = max(20, dash - dash * min(1.0, (stars + commits/20 + prs*2) / 300))
    svg = f'''<svg width="480" height="195" viewBox="0 0 480 195" xmlns="http://www.w3.org/2000/svg">
<defs>
  <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="{BLUE}"/>
    <stop offset="100%" stop-color="{AMBER}"/>
  </linearGradient>
  <style>
    .mono{{font-family:'Courier New',Consolas,monospace;}}
    .sans{{font-family:'Segoe UI',Helvetica,Arial,sans-serif;}}
    .label{{fill:#cfe3ff;font-size:13px;}}
    .val{{fill:#ffffff;font-size:13px;font-weight:700;text-anchor:end;}}
  </style>
</defs>
<rect x="0.5" y="0.5" width="479" height="194" rx="16" fill="{BG}" stroke="rgba(59,130,246,0.25)"/>
<text x="24" y="34" class="sans" font-size="17" font-weight="700" fill="#ffffff">Saad's GitHub Stats (live)</text>
<g transform="translate(80,118)">
  <circle r="52" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="10"/>
  <circle r="52" fill="none" stroke="url(#ringGrad)" stroke-width="10" stroke-linecap="round"
    stroke-dasharray="{dash}" stroke-dashoffset="{dash}" transform="rotate(-90)">
    <animate attributeName="stroke-dashoffset" from="{dash}" to="{offset:.0f}" dur="1.6s" begin="0.3s" fill="freeze" calcMode="spline" keySplines="0.2 0 0.2 1"/>
  </circle>
  <text text-anchor="middle" y="8" class="sans" font-size="24" font-weight="700" fill="#ffffff">{rank}</text>
</g>
<g class="mono">
  <g transform="translate(180,58)" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="0.6s" dur="0.4s" fill="freeze"/>
    <text class="label" x="0" y="0">Total Stars Earned</text><text class="val" x="288" y="0">{stars}</text></g>
  <g transform="translate(180,86)" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="0.75s" dur="0.4s" fill="freeze"/>
    <text class="label" x="0" y="0">Total Commits</text><text class="val" x="288" y="0">{commits:,}</text></g>
  <g transform="translate(180,114)" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="0.9s" dur="0.4s" fill="freeze"/>
    <text class="label" x="0" y="0">Total PRs</text><text class="val" x="288" y="0">{prs}</text></g>
  <g transform="translate(180,142)" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="1.05s" dur="0.4s" fill="freeze"/>
    <text class="label" x="0" y="0">Total Issues</text><text class="val" x="288" y="0">{issues}</text></g>
  <g transform="translate(180,170)" opacity="0"><animate attributeName="opacity" from="0" to="1" begin="1.2s" dur="0.4s" fill="freeze"/>
    <text class="label" x="0" y="0">Public Repositories</text><text class="val" x="288" y="0">{contributed}</text></g>
</g>
</svg>'''
    with open(path, "w") as f:
        f.write(svg)


def gen_langs_svg(lang_sizes, path, top_n=5):
    total = sum(lang_sizes.values()) or 1
    top = sorted(lang_sizes.items(), key=lambda x: -x[1])[:top_n]
    top = [(name if len(name) <= 18 else name[:17] + "…", size) for name, size in top]
    palette = [BLUE, AMBER, TEAL, CORAL, INDIGO]
    rows = []
    y = 50
    for i, (name, size) in enumerate(top):
        pct = size / total * 100
        color = palette[i % len(palette)]
        bar_w = round(pct / 100 * 280, 1)
        rows.append(f'''<text class="label" x="0" y="{y-40}">{name}</text><text class="pct" x="280" y="{y-40}">{pct:.0f}%</text>
  <rect x="0" y="{y-34}" width="280" height="8" rx="4" fill="rgba(255,255,255,0.06)"/>
  <rect x="0" y="{y-34}" width="0" height="8" rx="4" fill="{color}">
    <animate attributeName="width" from="0" to="{bar_w}" begin="{0.3+i*0.2:.1f}s" dur="1s" fill="freeze" calcMode="spline" keySplines="0.2 0 0.2 1"/>
  </rect>''')
        y += 34
    card_h = 34 * (len(top) - 1) + 94 if top else 94
    svg = f'''<svg width="320" height="{card_h}" viewBox="0 0 320 {card_h}" xmlns="http://www.w3.org/2000/svg">
<defs><style>.sans{{font-family:'Segoe UI',Helvetica,Arial,sans-serif;}}.label{{fill:#e3edff;font-size:13px;}}.pct{{fill:#7a8fa8;font-size:12px;text-anchor:end;}}</style></defs>
<rect x="0.5" y="0.5" width="319" height="{card_h-1}" rx="16" fill="{BG}" stroke="rgba(59,130,246,0.25)"/>
<text x="20" y="30" class="sans" font-size="16" font-weight="700" fill="#ffffff">Most Used Languages (live)</text>
<g transform="translate(20,50)">
{"".join(rows)}
</g>
</svg>'''
    with open(path, "w") as f:
        f.write(svg)


def gen_trophies_svg(stars, commits, prs, issues, followers, repos, years, path):
    cells = [
        ("⭐", "Stars", stars, "rgba(59,130,246,0.45)", BLUE),
        ("🔥", "Commits", f"{commits:,}", "rgba(0,217,255,0.45)", CYAN),
        ("🔀", "Pull Requests", prs, "rgba(245,166,35,0.45)", AMBER),
        ("🐛", "Issues", issues, "rgba(23,230,200,0.45)", TEAL),
        ("👥", "Followers", followers, "rgba(99,102,241,0.45)", INDIGO),
        ("📦", "Repositories", repos, "rgba(255,107,74,0.45)", CORAL),
        ("🏆", "Years Active", years, "rgba(255,209,102,0.45)", GOLD),
        ("🏢", "Companies", 2, "rgba(56,189,248,0.45)", SKY),
    ]
    cell_w, cell_h, gap = 130, 150, 10
    cols_per_row = 4
    parts = []
    for i, (icon, label, val, border, rankcolor) in enumerate(cells):
        col, row = i % cols_per_row, i // cols_per_row
        tx = 10 + col * (cell_w + gap)
        ty = 10 + row * (cell_h + gap)
        begin = 0.1 + i * 0.15
        parts.append(f'''<g transform="translate({tx},{ty})">
  <clipPath id="c{i}"><rect width="{cell_w}" height="{cell_h}" rx="14"/></clipPath>
  <g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="0.35s" fill="freeze"/>
    <rect width="{cell_w}" height="{cell_h}" rx="14" fill="#12081f" stroke="{border}"/>
    <g clip-path="url(#c{i})">
      <text x="65" y="44" text-anchor="middle" font-size="30">{icon}</text>
      <text x="65" y="68" text-anchor="middle" class="sans t-title">{label}</text>
      <text x="65" y="98" text-anchor="middle" class="sans t-rank" fill="{rankcolor}">&#9679;</text>
      <text x="65" y="132" text-anchor="middle" class="sans" font-size="16" fill="#ffffff">{val}</text>
    </g>
  </g>
</g>''')
    total_rows = -(-len(cells)//cols_per_row)
    svg_h = 10 + total_rows*(cell_h+gap)
    svg = f'''<svg width="560" height="{svg_h}" viewBox="0 0 560 {svg_h}" xmlns="http://www.w3.org/2000/svg">
<defs><style>.sans{{font-family:'Segoe UI',Helvetica,Arial,sans-serif;}}.t-title{{fill:#c9c3ff;font-size:13px;}}.t-rank{{font-size:22px;font-weight:700;}}</style></defs>
<rect width="560" height="{svg_h}" rx="16" fill="{BG}"/>
{"".join(parts)}
</svg>'''
    with open(path, "w") as f:
        f.write(svg)


def main():
    out_dir = os.environ.get("STATS_OUT_DIR", ".")
    basics = fetch_user_basics()
    followers = basics["followers"]["totalCount"]
    created_at = basics["createdAt"]
    years_active = datetime.datetime.utcnow().year - int(created_at[:4]) + 1

    commits, prs, issues = fetch_contributions_all_years(created_at)
    stars, repos, lang_sizes, _ = fetch_repos_and_languages()

    rank = compute_rank(stars, commits, prs, issues, followers)

    gen_stats_svg(stars, commits, prs, issues, repos, rank, os.path.join(out_dir, "stats.svg"))
    gen_langs_svg(lang_sizes, os.path.join(out_dir, "langs.svg"))
    gen_trophies_svg(stars, commits, prs, issues, followers, repos, years_active, os.path.join(out_dir, "trophies.svg"))

    print(f"Updated stats for {LOGIN}: stars={stars} commits={commits} prs={prs} issues={issues} "
          f"followers={followers} repos={repos} rank={rank}")


if __name__ == "__main__":
    main()
