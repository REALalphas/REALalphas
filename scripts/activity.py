"""Generate linked profile widgets. Only public repository details are rendered."""

import base64
import json
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from svg_geometry import contour
from languages import saturate, shift_hue

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
STATE_PATH = ROOT / ".cache" / "profile" / "activity-state.json"
LOGIN = "REALalphas"


def api(path, payload=None):
    headers = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
               "Accept": "application/vnd.github+json", "User-Agent": "REALalphas-profile"}
    data = None if payload is None else json.dumps(payload).encode()
    if data:
        headers["Content-Type"] = "application/json"
    with urlopen(Request("https://api.github.com" + path, data=data, headers=headers), timeout=30) as response:
        result = json.load(response)
    if isinstance(result, dict) and result.get("errors"):
        raise RuntimeError("GitHub GraphQL request failed")
    return result


def ago(iso, now=None):
    now = now or datetime.now(timezone.utc)
    seconds = max(0, (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds())
    if seconds < 60:
        return "just now"
    for duration, unit in [(31536000, "year"), (2592000, "month"), (604800, "week"),
                           (86400, "day"), (3600, "hour"), (60, "minute")]:
        if seconds >= duration:
            value = int(seconds // duration)
            return f"{value} {unit}{'s' if value != 1 else ''} ago"


def compact(value):
    if value < 1000:
        return str(value)
    return f"{value / 1000:.1f}".rstrip("0").rstrip(".") + "k"


def short(value, limit):
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


def avatar_data(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "avatars.githubusercontent.com":
        raise ValueError("Unexpected avatar URL")
    with urlopen(url + "&s=120" if "?" in url else url + "?s=120", timeout=30) as response:
        mime = response.headers.get_content_type()
        data = response.read(2_000_000)
    if mime not in ("image/png", "image/jpeg", "image/webp"):
        raise ValueError("Unexpected avatar format")
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def collect():
    query = '''query($cursor:String) { user(login:"REALalphas") {
      starredRepositories(first:20, orderBy:{field:STARRED_AT,direction:DESC}) {
        totalCount nodes { nameWithOwner name description url isPrivate stargazerCount owner { login } }
      }
      repositories(first:100, after:$cursor, ownerAffiliations:OWNER, privacy:PUBLIC) {
        nodes { stargazerCount } pageInfo { hasNextPage endCursor }
      }
    }}'''
    received, cursor, discovery, given = 0, None, None, 0
    while True:
        user = api("/graphql", {"query": query, "variables": {"cursor": cursor}})["data"]["user"]
        stars = user["starredRepositories"]
        given = stars["totalCount"]
        discovery = next((repo for repo in stars["nodes"] if not repo["isPrivate"]), None)
        repos = user["repositories"]
        received += sum(repo["stargazerCount"] for repo in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    commits = api("/search/commits?" + urlencode({"q": f"author:{LOGIN}", "sort": "author-date", "order": "desc", "per_page": 1}))
    commit_date = commits["items"][0]["commit"]["author"]["date"] if commits["items"] else None
    followers, page = [], 1
    while True:
        batch = api(f"/users/{LOGIN}/followers?per_page=100&page={page}")
        followers.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    state_path = STATE_PATH
    previous = json.loads(state_path.read_text()) if state_path.exists() else None
    known = set(previous["followers"]) if previous else set()
    newcomers = [person for person in followers if person["id"] not in known] if previous else []
    neighbor_id = newcomers[-1]["id"] if newcomers else previous.get("neighbor_id") if previous else None
    neighbor = next((person for person in followers if person["id"] == neighbor_id), None)
    detected = neighbor is not None
    if neighbor is None and followers:
        neighbor = followers[-1]
    avatar = avatar_data(neighbor["avatar_url"]) if neighbor else None
    state = {"followers": [person["id"] for person in followers], "neighbor_id": neighbor_id if detected else None}
    return {"commit_date": commit_date, "received": received, "given": given,
            "discovery": discovery, "neighbor": neighbor, "detected": detected,
            "avatar": avatar, "state": state}


# SVG equivalents of Alpha's UI tokens. Geometry uses a 2x scale so body text
# stays readable when the 800-unit card occupies half of the profile README.
THEME = {
    "canvas": "#222222", "surface": "#292929", "navigation": "#333333",
    "text": "#ffffff", "secondary": "#dddddd", "muted": "#999999",
    "border": "#999999", "border_opacity": 4 / 15,
}



def render(data):
    def font(name):
        return base64.b64encode((ASSETS / "fonts" / name).read_bytes()).decode()

    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="533.333333" height="665" viewBox="0 0 533.333333 665" role="img" aria-labelledby="title desc">
<title id="title">Meanwhile · AlphaS</title>
<desc id="desc">Time since last commit, stars received versus given, latest starred repository and the latest follower. Updated hourly.</desc>
<style>
@font-face{{font-family:Manrope;src:url(data:font/woff2;base64,{font('Manrope-latin.woff2')});font-weight:200 800}}
@font-face{{font-family:Noto;src:url(data:font/woff2;base64,{font('NotoSans-latin.woff2')});font-weight:100 900}}
@font-face{{font-family:Pliant;src:url(data:font/woff;base64,{font('Pliant-digits.woff')});font-weight:600}}
text{{font-family:Manrope,sans-serif}}.body{{font-family:Noto,sans-serif;font-weight:400}}.digits{{font-family:Pliant,sans-serif;font-weight:600;font-stretch:125%;font-variation-settings:'wdth' 125,'wght' 600}}
</style>
<path d="{contour(0, 0, 533.333333, 665, 40)}" fill="#222222"/>
<path d="{contour(.75, .75, 531.833333, 663.5, 39.25)}" fill="none" stroke="#999999" stroke-opacity=".266667" stroke-width="1.5"/>
''']

    def label(x, y, value, size=36, color="secondary", anchor="start", family=None):
        attr = f' class="{family}"' if family else ''
        svg.append(f'<text x="{x}" y="{y}"{attr} font-size="{size}" font-weight="500" text-anchor="{anchor}" fill="{THEME[color]}">{escape(str(value))}</text>')

    def number(x, y, value, size=96, anchor="start"):
        svg.append(f'<text class="digits" x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="#ffffff" fill-opacity=".6">{escape(str(value))}</text>')

    def panel(x, y, width, height, radius=32, fill="surface"):
        # Stroke sits fully inside the surface, matching the UI's inset shadow.
        svg.append(f'<path d="{contour(x, y, width, height, radius)}" fill="{THEME[fill]}"/>')
        svg.append(f'<path d="{contour(x + .75, y + .75, width - 1.5, height - 1.5, radius - .75)}" fill="none" stroke="#999999" stroke-opacity=".266667" stroke-width="1.5"/>')

    def icon(name, x, y, size=48, color="muted"):
        import xml.etree.ElementTree as ET
        root = ET.parse(ASSETS / "icons" / f"{name}.svg").getroot()
        shapes = "".join(ET.tostring(child, encoding="unicode") for child in root)
        svg.append(f'<g transform="translate({x} {y}) scale({size / 24})" fill="none" stroke="{THEME[color]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{shapes}</g>')

    label(40, 58, "Meanwhile", 36, "text")
    # The paired flip panels keep the time counter tactile, using UI surfaces.
    stamp = ago(data["commit_date"]) if data["commit_date"] else "No commits yet"
    panel(40, 88, 453.333333, 116)
    parts = stamp.split(" ", 1)
    if parts[0].isdigit():
        value = parts[0]
        digit_width = 64 + max(0, len(value) - 1) * 40
        panel(64, 112, digit_width, 68, 24, "navigation")
        number(64 + digit_width / 2, 170, value, 64, "middle")
        label_x = 64 + digit_width + 24
        label(label_x, 138, "Last commit", color="muted")
        label(label_x, 178, parts[1])
    else:
        icon("git-commit-horizontal", 64, 122)
        label(136, 160, stamp)

    # One two-tone surface: segment widths encode the actual received/given ratio.
    received, given = data["received"], data["given"]
    ratio = received / (received + given) if received + given else .5
    split = 64 + 405.333333 * ratio
    panel(40, 220, 453.333333, 164)
    icon("star", 64, 238, 40, "secondary")
    label(120, 270, "Stars", color="text")
    svg.append(f'<title>Stars: {received} received, {given} given</title>')
    svg.append(f'<defs><clipPath id="stars-shape"><path d="{contour(64, 288, 405.333333, 72, 24)}"/></clipPath></defs>')
    svg.append('<defs><filter id="stars-noise" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" seed="7" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComposite in2="SourceGraphic" operator="in"/></filter></defs>')
    svg.append('<g clip-path="url(#stars-shape)">')
    for key, x, width, color in [
        ("received", 64, 405.333333 * ratio, "#f1e05a"),
        ("given", split, 405.333333 * (1 - ratio), "#663399"),
    ]:
        # Same two radial light sources and acrylic grain as the language tiles.
        bright = "#" + "".join(f"{round(int(color[i:i + 2], 16) * .8 + 255 * .2):02x}" for i in (1, 3, 5))
        color, bright = saturate(color), saturate(bright)
        counter = shift_hue(color, -20, saturation_scale=1.2, lightness_scale=.9)
        svg.append(f'<defs><radialGradient id="stars-{key}" gradientUnits="userSpaceOnUse" cx="{x + width * 1.5}" cy="236" r="760"><stop offset="0" stop-color="{bright}" stop-opacity=".75"/><stop offset="1" stop-color="{color}" stop-opacity=".07"/></radialGradient><radialGradient id="stars-{key}-counter" gradientUnits="userSpaceOnUse" cx="{x - 50}" cy="398" r="300"><stop offset="0" stop-color="{counter}" stop-opacity=".5"/><stop offset="1" stop-color="{counter}" stop-opacity="0"/></radialGradient></defs>')
        for fill in [f"url(#stars-{key})", f"url(#stars-{key}-counter)"]:
            svg.append(f'<rect x="{x:.3f}" y="288" width="{width:.3f}" height="72" fill="{fill}"/>')
        svg.append(f'<rect x="{x:.3f}" y="288" width="{width:.3f}" height="72" fill="#ffffff" filter="url(#stars-noise)" opacity=".12"/>')
    svg.append('</g>')

    metrics = json.loads((ASSETS / "fonts/Pliant-digits-metrics.json").read_text())

    def centered_total(x, value, anchor="start"):
        value = compact(value)
        glyphs = metrics["variants"]["600"]["125"]
        if all(character in glyphs for character in value):
            bottom = min(glyphs[c]["bounds"][1] for c in value)
            top = max(glyphs[c]["bounds"][3] for c in value)
            baseline = 324 + (top + bottom) * 44 / (2 * metrics["unitsPerEm"])
            number(x, round(baseline, 3), value, 44, anchor)
        else:
            svg.append(f'<text class="digits" x="{x}" y="324" dominant-baseline="central" font-size="44" text-anchor="{anchor}" fill="#ffffff" fill-opacity=".6">{escape(value)}</text>')

    def star_label(x, value, anchor="start"):
        svg.append(f'<text x="{x:.3f}" y="324" dy=".35em" font-size="36" font-weight="500" text-anchor="{anchor}" fill="#ffffff" fill-opacity=".38">{value}</text>')

    if min(ratio, 1 - ratio) >= .25:
        centered_total(76, received)
        star_label(split - 12, "Got", "end")
        star_label(split + 12, "Given")
        centered_total(457.333333, given, "end")
    else:
        # Keep both totals legible when one proportional segment is very narrow.
        label(469.333333, 270, f"Got {compact(received)} / Given {compact(given)}", anchor="end")
        if ratio >= .25:
            centered_total(76, received)
            star_label(split - 12, "Got", "end")
        if 1 - ratio >= .25:
            star_label(split + 12, "Given")
            centered_total(457.333333, given, "end")

    # A compact bookmark, with enough type size to read the actual repository.
    repo = data["discovery"]
    panel(40, 400, 453.333333, 128)
    label(64, 448, "Latest find", color="muted")
    icon("bookmark", 421.333333, 412, 48)
    if repo:
        svg.append(f'<a xlink:href="{escape(repo["url"], quote=True)}">')
        name = repo["name"]
        # Keep a single readable line with the same 24-unit inset on each side.
        widths = json.loads((ASSETS / "fonts/title-metrics.json").read_text())
        def advance(value):
            return sum(widths.get(character, .7) for character in value) * 36
        if advance(name) > 405.333333:
            while name and advance(name + "…") > 405.333333:
                name = name[:-1]
            name = name.rstrip() + "…"
        label(64, 500, name)
        svg.append('</a>')
    else:
        label(64, 500, "Nothing saved yet", family="body")

    # A plain cropped avatar, without the profile component's frame or inset.
    person = data["neighbor"]
    label(144, 575, "Latest follower", color="muted")
    if person:
        svg.append(f'<a xlink:href="{escape(person["html_url"], quote=True)}">')
        outline = contour(40, 544, 80, 80, 32)
        svg.append(f'<defs><clipPath id="avatar"><path d="{outline}"/></clipPath></defs>')
        svg.append(f'<image x="40" y="544" width="80" height="80" clip-path="url(#avatar)" xlink:href="{data["avatar"]}"/>')
        label(144, 618, "@" + short(person["login"], 25), color="text")
        svg.append('</a>')
    else:
        label(144, 618, "Room for one more", family="body")
    svg.append('</svg>')
    (ASSETS / "activity.svg").write_text("\n".join(svg) + "\n", encoding="utf-8")
    (ROOT / "README.md").write_text('''<img src="assets/profile.svg" width="800" alt="AlphaS · @REALalphas" />

<p>
<img src="assets/activity.svg" width="316" alt="Meanwhile: last commit, stars received versus given, latest find and latest follower" />&nbsp;&nbsp;<img src="assets/languages.svg" width="474" alt="Languages %" />
</p>
''', encoding="utf-8")


def main():
    data = collect()
    render(data)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(data["state"], indent=2) + "\n")
    temporary.replace(STATE_PATH)


if __name__ == "__main__":
    main()
