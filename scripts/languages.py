"""Generate aggregate language shares from accessible public and private repositories."""

import json
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

    for excluded in ("Bash", "Shell", "Batch", "Batchfile", "Docker", "Dockerfile"):
        languages.pop(excluded, None)

    total = sum(languages.values())
    if not total:
        raise RuntimeError("No language data; keeping the existing card")
    rows = languages.most_common(8)
    remaining = total - sum(value for _, value in rows)
    if remaining:
        rows.append(("Other", remaining))
    height = 96 + len(rows) * 48
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{height}" viewBox="0 0 800 {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Languages</title>',
        '<desc id="desc">Language shares by code size, excluding forks, Bash, Shell, Batch and Docker files.</desc>',
        f'<rect width="800" height="{height}" rx="24" fill="#222222"/>',
        f'<rect x="0.75" y="0.75" width="798.5" height="{height - 1.5:g}" rx="23.25" fill="none" stroke="#999999" stroke-opacity="0.266667" stroke-width="1.5"/>',
        '<g font-family="Manrope, sans-serif" fill="#ffffff">',
        '<text x="40" y="50" font-size="24" font-weight="500">Languages</text>',
    ]
    for index, (name, count) in enumerate(rows):
        y = 88 + index * 48
        share = count / total
        svg.extend([
            f'<text x="40" y="{y}" font-size="18">{escape(name)}</text>',
            f'<text x="760" y="{y}" text-anchor="end" font-family="Fira Code, monospace" font-size="16" fill="#dddddd">{share:.1%}</text>',
            f'<rect x="40" y="{y + 10}" width="720" height="6" rx="3" fill="#333333"/>',
            f'<rect x="40" y="{y + 10}" width="{720 * share:.2f}" height="6" rx="3" fill="#796699"/>',
        ])
    svg.extend(['</g>', '</svg>'])
    destination = Path(__file__).resolve().parent.parent / "assets/languages.svg"
    destination.write_text("\n".join(svg) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
