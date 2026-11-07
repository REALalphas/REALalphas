"""Generate profile widgets, masking private repository names before rendering."""

import base64
import json
import os
import random
import string
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


def repository_preview(repo):
    """Never pass a private URL or the hidden name suffix to the SVG renderer."""
    if repo["private"]:
        name = repo["name"]
        character = name[2:3] or name[-1:] or "•"
        return {"private": True, "label": repo["owner"]["login"] + "/" + name[:2],
                "tail": character + character.lower() * 3 + "".join(random.choice(string.ascii_lowercase) for _ in range(2))}
    return {"private": False, "label": repo["full_name"], "url": repo["html_url"]}


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
      starredRepositories { totalCount }
      repositories(first:100, after:$cursor, ownerAffiliations:OWNER, privacy:PUBLIC) {
        nodes { stargazerCount } pageInfo { hasNextPage endCursor }
      }
    }}'''
    received, cursor, given = 0, None, 0
    while True:
        user = api("/graphql", {"query": query, "variables": {"cursor": cursor}})["data"]["user"]
        stars = user["starredRepositories"]
        given = stars["totalCount"]
        repos = user["repositories"]
        received += sum(repo["stargazerCount"] for repo in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        cursor = repos["pageInfo"]["endCursor"]
    commits = api("/search/commits?" + urlencode({"q": f"author:{LOGIN}", "sort": "author-date", "order": "desc", "per_page": 1}))
    commit_date = commits["items"][0]["commit"]["author"]["date"] if commits["items"] else None
    repository = None
    if commits["items"]:
        full_name = commits["items"][0]["repository"]["full_name"]
        repository = repository_preview(api("/repos/" + full_name))
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
    return {"commit_date": commit_date, "repository": repository, "received": received, "given": given,
            "neighbor": neighbor, "detected": detected,
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
<desc id="desc">Time since last commit, stars received versus given and the latest follower. Updated hourly.</desc>
<style>
@font-face{{font-family:Manrope;src:url(data:font/ttf;base64,{font('Manrope-Medium.ttf')});font-weight:500}}
@font-face{{font-family:Pliant;src:url(data:font/woff;base64,{font('Pliant-digits.woff')});font-weight:600}}
text{{font-family:Manrope,sans-serif}}.digits{{font-family:Pliant,Manrope,sans-serif;font-weight:600;font-stretch:125%;font-variation-settings:'wdth' 125,'wght' 600}}
</style>
<path d="{contour(0, 0, 533.333333, 665, 40)}" fill="#222222"/>
<path d="{contour(.75, .75, 531.833333, 663.5, 39.25)}" fill="none" stroke="#999999" stroke-opacity=".266667" stroke-width="1.5"/>
''']

    def label(x, y, value, size=32, color="secondary", anchor="start", family=None):
        attr = f' class="{family}"' if family else ''
        svg.append(f'<text x="{x}" y="{y}"{attr} font-size="{size}" font-weight="500" text-anchor="{anchor}" fill="{THEME[color]}">{escape(str(value))}</text>')

    def number(x, y, value, size=96, anchor="start"):
        svg.append(f'<text class="digits" x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="#ffffff" fill-opacity=".6">{escape(str(value))}</text>')

    def panel(x, y, width, height, radius=32, fill="surface"):
        # Stroke sits fully inside the surface, matching the UI's inset shadow.
        svg.append(f'<path d="{contour(x, y, width, height, radius)}" fill="{THEME[fill]}"/>')
        svg.append(f'<path d="{contour(x + .75, y + .75, width - 1.5, height - 1.5, radius - .75)}" fill="none" stroke="#999999" stroke-opacity=".266667" stroke-width="1.5"/>')

    def icon(name, right, center_y, size=34, color="muted", top=None):
        import xml.etree.ElementTree as ET
        root = ET.parse(ASSETS / "icons" / f"{name}.svg").getroot()
        shapes = "".join(ET.tostring(child, encoding="unicode") for child in root)
        # Geometric bounds of the actual Lucide paths, excluding the stroke.
        bounds = {"clock-3": (2, 2, 20, 20),
                  "star": (1.9982, 2.0001, 20.0018, 19.0721),
                  "heart": (2, 3.9838, 20.0001, 17.0158)}
        bx, by, width, height = bounds[name]
        scale, stroke = size / 24, 1.875
        x = right - (bx + width + stroke / 2) * scale
        y = center_y - (by + height / 2) * scale
        if top is not None:
            y = top - (by - stroke / 2) * scale
        y -= 2 / .5925
        x += 1 / .5925
        svg.append(f'<g transform="translate({x:.3f} {y:.3f}) scale({scale})" fill="none" stroke="{THEME[color]}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{shapes}</g>')

    text_metrics = json.loads((ASSETS / "fonts/Manrope-text-metrics.json").read_text())
    digit_metrics = json.loads((ASSETS / "fonts/Pliant-digits-metrics.json").read_text())

    def measure(value, size=32):
        advance = 0
        left, right, bottom, top = float("inf"), float("-inf"), 0, 0
        for character in value:
            glyph = text_metrics.get(character, text_metrics["M"])
            left = min(left, advance + glyph["left"] * size)
            right = max(right, advance + glyph["right"] * size)
            bottom = min(bottom, glyph["bottom"] * size)
            top = max(top, glyph["top"] * size)
            advance += glyph["advance"] * size
        return {"left": min(left, advance), "right": max(right, 0), "top": top,
                "bottom": bottom, "height": top - bottom, "advance": advance}

    def fit_text(value, width=405.333333, size=32):
        if measure(value, size)["right"] - measure(value, size)["left"] <= width:
            return value
        while value and measure(value.rstrip() + "…", size)["right"] > width:
            value = value[:-1]
        return value.rstrip() + "…"

    def ink_label(x, top, value, size=32, color="secondary"):
        bounds = measure(value, size)
        label(round(x - bounds["left"], 3), round(top + bounds["top"], 3),
              value, size, color)

    def centered_label(x, center_y, value, size=32):
        bounds = measure(value, size)
        label(round(x - bounds["left"], 3),
              round(center_y + (bounds["top"] + bounds["bottom"]) / 2, 3), value, size)

    label(40, 58, "Meanwhile", 28, "text")

    def activity_card(y, height, title, icon_name):
        panel(40, y, 453.333333, height)
        ink_label(64, y + 24, title, 28, "muted")
        title_height = measure(title, 28)["height"]
        icon(icon_name, 469.333333, y + 24 + title_height / 2, top=y + 24)

    # A fixed content inset and a compact two-line body, without stretched gaps.
    commit_y, commit_height = 88, 160
    activity_card(commit_y, commit_height, "Last commit", "clock-3")
    stamp = ago(data["commit_date"]) if data["commit_date"] else "No commits yet"
    repository = data.get("repository")
    repo_text = ""
    if repository:
        repo_text = (repository["label"] + repository["tail"] if repository["private"]
                     else fit_text(repository["label"], size=28))
    commit_font_size = 28
    time_top = commit_y + 72
    ink_label(64, time_top, stamp, commit_font_size)
    if repository:
        repo_top = time_top + measure(stamp, commit_font_size)["height"] + 12
        repo_baseline = repo_top + measure(repo_text, commit_font_size)["top"]
        if repository["private"]:
            prefix, tail = repository["label"], repository["tail"]
            owner, visible = prefix.rsplit("/", 1)
            sharp_prefix = owner + "/" + visible[:1]
            blurred = visible[1:] + tail
            x = 64 - measure(repo_text, commit_font_size)["left"]
            label(round(x, 3), round(repo_baseline, 3), sharp_prefix, commit_font_size)
            x += measure(sharp_prefix, commit_font_size)["advance"]
            for index, character in enumerate(blurred):
                blur = [1.1, 2.3, 3.6, 4.5, 4.9, 5.1, 5.5][index]
                svg.append(f'<defs><filter id="repo-blur-{index}" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="{blur}"/></filter></defs>')
                svg.append(f'<text x="{x:.3f}" y="{repo_baseline:.3f}" font-size="{commit_font_size}" font-weight="500" fill="#dddddd" filter="url(#repo-blur-{index})">{escape(character)}</text>')
                x += measure(character, commit_font_size)["advance"]
        else:
            svg.append(f'<a xlink:href="{escape(repository["url"], quote=True)}">')
            ink_label(64, repo_top, repo_text, commit_font_size)
            svg.append('</a>')

    received, given = data["received"], data["given"]
    ratio = received / (received + given) if received + given else .5
    star_y, star_height = 264, 224
    bar_x, bar_y, bar_width, bar_height = 64, 336, 405.333333, 128
    split = bar_x + bar_width * ratio
    activity_card(star_y, star_height, "Stars", "star")
    svg.append(f'<title>Stars: {received} received, {given} given</title>')
    svg.append(f'<defs><clipPath id="stars-shape"><path d="{contour(bar_x, bar_y, bar_width, bar_height, 24)}"/></clipPath></defs>')
    svg.append('<defs><filter id="stars-noise" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="3" seed="7" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComposite in2="SourceGraphic" operator="in"/></filter></defs>')
    svg.append('<g clip-path="url(#stars-shape)">')
    for key, x, width, color in [
        ("received", bar_x, bar_width * ratio, "#f1e05a"),
        ("given", split, bar_width * (1 - ratio), "#663399"),
    ]:
        bright = "#" + "".join(f"{round(int(color[i:i + 2], 16) * .8 + 255 * .2):02x}" for i in (1, 3, 5))
        color, bright = saturate(color), saturate(bright)
        counter = shift_hue(color, -20, saturation_scale=1.2, lightness_scale=.9)
        svg.append(f'<defs><radialGradient id="stars-{key}" gradientUnits="userSpaceOnUse" cx="{x + width * 1.5}" cy="{bar_y - bar_height * .5}" r="760"><stop offset="0" stop-color="{bright}" stop-opacity=".75"/><stop offset="1" stop-color="{color}" stop-opacity=".07"/></radialGradient><radialGradient id="stars-{key}-counter" gradientUnits="userSpaceOnUse" cx="{x - 50}" cy="{bar_y + bar_height + 30}" r="300"><stop offset="0" stop-color="{counter}" stop-opacity=".5"/><stop offset="1" stop-color="{counter}" stop-opacity="0"/></radialGradient></defs>')
        for fill in [f"url(#stars-{key})", f"url(#stars-{key}-counter)"]:
            svg.append(f'<rect x="{x:.3f}" y="{bar_y}" width="{width:.3f}" height="{bar_height}" fill="{fill}"/>')
        svg.append(f'<rect x="{x:.3f}" y="{bar_y}" width="{width:.3f}" height="{bar_height}" fill="#ffffff" filter="url(#stars-noise)" opacity=".12"/>')
    svg.append('</g>')

    def counter_bounds(value, variant):
        glyphs = digit_metrics["variants"]["600"][str(variant)]
        units = digit_metrics["unitsPerEm"]
        advance, left, right, bottom, top = 0, float("inf"), float("-inf"), float("inf"), float("-inf")
        for character in value:
            if character in glyphs:
                glyph = glyphs[character]
                x1, y1, x2, y2 = glyph["bounds"]
                step = glyph["advance"]
            else:
                glyph = text_metrics.get(character, text_metrics["M"])
                x1, y1, x2, y2 = [glyph[key] * units for key in ["left", "bottom", "right", "top"]]
                step = glyph["advance"] * units
            left, right = min(left, advance + x1), max(right, advance + x2)
            bottom, top = min(bottom, y1), max(top, y2)
            advance += step
        return left, bottom, right, top

    def star_segment(x, width, value, caption, left_side):
        # Respect the caption and gap before fitting the largest possible digit ink.
        caption_bounds = measure(caption, 22)
        caption_width = caption_bounds["right"] - caption_bounds["left"]
        padding, content_gap = 20, 20
        stacked = width < bar_width * .4
        available = width - 2 * padding
        available_height = bar_height - 2 * padding
        if stacked:
            available_height -= caption_bounds["height"] + content_gap
        else:
            available -= content_gap + caption_width
        if available < 24 or (stacked and caption_width > available):
            return False
        fitted = None
        for variant in range(125, 99, -1):
            bounds = counter_bounds(compact(value), variant)
            left, bottom, right, top = bounds
            scale = available_height / (top - bottom)
            fitted = (variant, bounds, scale)
            if (right - left) * scale <= available:
                break
        variant, (left, bottom, right, top), scale = fitted
        scale = min(scale, available / (right - left))
        size = scale * digit_metrics["unitsPerEm"]
        number_height = (top - bottom) * scale
        if stacked:
            group_height = number_height + content_gap + caption_bounds["height"]
            group_top = bar_y + (bar_height - group_height) / 2
            baseline = group_top + top * scale
            number_x = x + padding - left * scale if left_side else x + width - padding - right * scale
            caption_x = (x + padding if left_side else x + width - padding - caption_width) - caption_bounds["left"]
            caption_y = group_top + number_height + content_gap + caption_bounds["top"]
        else:
            baseline = bar_y + bar_height / 2 + (top + bottom) * scale / 2
            number_x = x + padding - left * scale if left_side else x + width - padding - right * scale
            caption_x = x + width - padding - caption_width if left_side else x + padding
            caption_x -= caption_bounds["left"]
            caption_y = bar_y + bar_height / 2 + (caption_bounds["top"] + caption_bounds["bottom"]) / 2
        svg.append(f'<text class="digits" x="{number_x:.3f}" y="{baseline:.3f}" font-size="{size:.3f}" style="font-stretch:{variant}%;font-variation-settings: &apos;wdth&apos; {variant}, &apos;wght&apos; 600" fill="#ffffff" fill-opacity=".6">{escape(compact(value))}</text>')
        svg.append(f'<text x="{caption_x:.3f}" y="{caption_y:.3f}" font-size="22" font-weight="500" fill="#ffffff" fill-opacity=".38">{caption}</text>')
        return True

    shown_left = star_segment(bar_x, bar_width * ratio, received, "Got", True)
    shown_right = star_segment(split, bar_width * (1 - ratio), given, "Given", False)
    svg.append(f'<path d="{contour(bar_x + .75, bar_y + .75, bar_width - 1.5, bar_height - 1.5, 23.25)}" fill="none" stroke="#999999" stroke-opacity=".266667" stroke-width="1.5"/>')
    if not shown_left or not shown_right:
        # A near-zero segment cannot hold a number; retain both totals in the header.
        label(405.333333, 308, f"{compact(received)} / {compact(given)}", 28, anchor="end")

    # Compact row: the unchanged avatar anchors a vertically centered text stack.
    follower_y, follower_height, avatar_y = 504, 120, 528
    panel(40, follower_y, 453.333333, follower_height)
    person = data["neighbor"]
    caption = "Latest follower"
    name = fit_text("@" + person["login"], 309.333333, size=28) if person else "Room for one more"
    caption_height, name_height = measure(caption, 28)["height"], measure(name, 28)["height"]
    stack_top = avatar_y + (72 - caption_height - 12 - name_height) / 2
    follower_text_x = 160 - 2 / .5925
    # README displays 533.333 SVG units at 316px: one visible pixel is 1/0.5925 units.
    caption_top = stack_top - 2 / .5925
    ink_label(follower_text_x, caption_top, caption, 28, "muted")
    icon("heart", 469.333333, caption_top + caption_height / 2, top=follower_y + 24)
    if person:
        svg.append(f'<a xlink:href="{escape(person["html_url"], quote=True)}">')
        outline = contour(64, avatar_y, 72, 72, 24)
        svg.append(f'<defs><clipPath id="avatar"><path d="{outline}"/></clipPath></defs>')
        svg.append(f'<image x="64" y="{avatar_y}" width="72" height="72" clip-path="url(#avatar)" xlink:href="{data["avatar"]}"/>')
        svg.append(f'<path d="{contour(64.75, avatar_y + .75, 70.5, 70.5, 23.25)}" fill="none" stroke="#999999" stroke-opacity=".266667" stroke-width="1.5"/>')
        ink_label(follower_text_x, stack_top + caption_height + 12, name, 28)
        svg.append('</a>')
    else:
        ink_label(follower_text_x, stack_top + caption_height + 12, name, 28)
    svg.append('</svg>')
    (ASSETS / "activity.svg").write_text("\n".join(svg) + "\n", encoding="utf-8")
    (ROOT / "README.md").write_text('''<img src="assets/profile.svg" width="800" alt="AlphaS · @REALalphas" />

<p>
<img src="assets/activity.svg" width="316" alt="Meanwhile: last commit, stars received versus given and latest follower" />&nbsp;&nbsp;<img src="assets/languages.svg" width="474" alt="Languages %" />
</p>
''', encoding="utf-8")


def main():
    data = collect()
    destination = ASSETS / "activity.svg"
    before = destination.read_bytes() if destination.exists() else None
    render(data)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(data["state"], indent=2) + "\n")
    temporary.replace(STATE_PATH)
    changed = before != destination.read_bytes()
    print(f"activity.svg: {'updated' if changed else 'unchanged'}")


if __name__ == "__main__":
    main()
