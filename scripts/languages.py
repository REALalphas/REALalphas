"""Generate aggregate language shares from accessible public and private repositories."""

import json
import base64
import colorsys
import os
from collections import Counter
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen


def github(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "REALalphas-profile"}
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(f"https://api.github.com{path}", headers=headers), timeout=30) as response:
        return json.load(response)


def main():
    if not os.environ.get("GH_TOKEN"):
        raise RuntimeError("Set METRICS_TOKEN in Actions secrets to include private repositories")
    if github("/user")["login"].casefold() != "realalphas":
        raise RuntimeError("METRICS_TOKEN must belong to REALalphas")
    languages = Counter()
    page = 1
    while True:
        repos = github(f"/user/repos?affiliation=owner&visibility=all&per_page=100&page={page}")
        for repo in repos:
            if not repo["fork"] and repo["owner"]["login"].casefold() == "realalphas":
                languages.update(github(f"/repos/{repo['full_name']}/languages"))
        if len(repos) < 100:
            break
        page += 1

    total = sum(languages.values())
    if not total:
        raise RuntimeError("No language data; keeping the existing card")
    other = sum(languages.pop(name, 0) for name in (
        "Makefile", "CMake", "Docker", "Dockerfile", "Bash", "Shell",
        "Batch", "Batchfile", "PowerShell", "Just", "DTrace",
    ))
    rows = languages.most_common(8)
    remaining = other + sum(languages.values()) - sum(value for _, value in rows)
    if remaining:
        rows.append(("Other", remaining))
    destination = Path(__file__).resolve().parent.parent / "assets/languages.svg"
    destination.write_text(render_card(rows, total), encoding="utf-8")


COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Rust": "#dea584",
    "Makefile": "#427819", "Java": "#b07219", "CSS": "#663399",
    "HTML": "#e34c26", "Nix": "#7e7eff", "Python": "#3572a5",
    "Go": "#00add8", "C": "#555555", "C++": "#f34b7d",
    "C#": "#178600", "Ruby": "#701516", "PHP": "#4f5d95",
    "Swift": "#f05138", "Kotlin": "#a97bff", "Dart": "#00b4ab",
    "Vue": "#41b883", "Svelte": "#ff3e00", "Lua": "#000080",
    "SCSS": "#c6538c", "Other": "#999999",
}


def saturate(color):
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)
    rgb = colorsys.hls_to_rgb(hue, lightness, min(1, saturation * 1.35))
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb)


def render_card(rows, total):
    font_path = Path(__file__).resolve().parent.parent / "assets/fonts/Unbounded-digits.woff"
    font_data = base64.b64encode(font_path.read_bytes()).decode("ascii")
    # Keep reading order on four columns: wide, square, square, square, repeat.
    cell = 171
    gap = 12
    tile_height = cell
    row_step = tile_height + gap
    placements = []
    row = column = 0
    for index, (name, count) in enumerate(rows):
        span = 2 if index % 4 == 0 else 1
        if column + span > 4:
            row += 1
            column = 0
        placements.append((name, count, row, column, span))
        column += span
    height = 128 + (row + 1) * row_step - gap
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}" viewBox="0 0 800 {height}" role="img" aria-labelledby="title desc">',
        f'<style>@font-face{{font-family:Unbounded;src:url(data:font/woff;base64,{font_data}) format("woff");font-weight:600;}}</style>',
        '<title id="title">Languages %</title>',
        '<desc id="desc">Language shares by code size, excluding forks. Build files, containers and shell scripts are grouped into Other.</desc>',
        f'<rect width="800" height="{height}" rx="24" fill="#222222"/>',
        f'<rect x="0.75" y="0.75" width="798.5" height="{height - 1.5:g}" rx="23.25" fill="none" stroke="#999999" stroke-opacity="0.266667" stroke-width="1.5"/>',
        '<g font-family="Manrope, sans-serif" fill="#ffffff">',
        '<text x="40" y="58" font-size="24" font-weight="500">Languages %</text>',
    ]
    for index, (name, count, row, column, span) in enumerate(placements):
        x = 40 + column * (cell + gap)
        y = 88 + row * row_step
        width = cell * span + gap * (span - 1)
        color = COLORS.get(name, "#999999")
        bright = "#" + "".join(f"{round(int(color[i:i + 2], 16) * 0.8 + 255 * 0.2):02x}" for i in (1, 3, 5))
        color, bright = saturate(color), saturate(bright)
        percentage = 100 * count / total
        label = f"{percentage:.0f}" if percentage > 9 else f"{percentage:.1f}"
        svg.extend([
            f'<defs><radialGradient id="language-{index}" gradientUnits="userSpaceOnUse" cx="{x + width * 1.5}" cy="{y - tile_height * 0.5}" r="760"><stop offset="0" stop-color="{bright}" stop-opacity="0.75"/><stop offset="1" stop-color="{color}" stop-opacity="0.07"/></radialGradient></defs>',
            f'<rect x="{x}" y="{y}" width="{width}" height="{tile_height}" rx="16" fill="url(#language-{index})"/>',
            f'<rect x="{x + 0.75}" y="{y + 0.75}" width="{width - 1.5}" height="{tile_height - 1.5}" rx="15.25" fill="none" stroke="#999999" stroke-opacity="0.266667" stroke-width="1.5"/>',
            f'<text x="{x + 20}" y="{y + 44}" font-size="24" font-weight="500" fill="#ffffff" fill-opacity="0.72">{escape(name)}</text>',
            f'<text x="{x + width - 20}" y="{y + tile_height - 24}" text-anchor="end" font-family="Unbounded, sans-serif" font-size="64" font-weight="600" fill="#ffffff" fill-opacity="0.6">{label}</text>',
        ])
    svg.extend(['</g>', '</svg>'])
    return "\n".join(svg) + "\n"


if __name__ == "__main__":
    main()
