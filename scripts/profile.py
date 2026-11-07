"""Build the profile header from its logo, font and layout settings."""

import base64
from pathlib import Path
import xml.etree.ElementTree as ET

from svg_geometry import contour

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def render():
    font = base64.b64encode((ASSETS / "fonts/Manrope-Medium.ttf").read_bytes()).decode()
    logo = ET.parse(ASSETS / "logo.svg").getroot()
    shapes = "".join(ET.tostring(node, encoding="unicode") for node in logo)
    scale = 474 / 800  # Match the displayed corner, outline and caption size of the lower cards.
    stroke = 1.5 * scale
    inset = stroke / 2
    outline = contour(inset, inset, 800 - stroke, 96 - stroke, 40 * scale - inset)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="96" viewBox="0 0 800 96" fill="none" role="img" aria-labelledby="title desc">
<style>@font-face{{font-family:Manrope;src:url(data:font/ttf;base64,{font});font-weight:500;font-style:normal}}</style>
<title id="title">AlphaS · @REALalphas</title>
<desc id="desc">AlphaS on a graphite background.</desc>
<path d="{outline}" fill="#222222" stroke="#999999" stroke-opacity="0.266667" stroke-width="{stroke:g}"/>
<g transform="translate(12 12) scale(1.7)">{shapes}</g>
<text x="88" y="46" fill="#ffffff" font-family="Manrope, sans-serif" font-size="32" font-weight="500">AlphaS</text>
<text x="88" y="75" fill="#999999" font-family="Manrope, sans-serif" font-size="{28 * scale:g}" font-weight="400">@REALalphas</text>
</svg>
'''


def main():
    path = ASSETS / "profile.svg"
    svg = render()
    changed = not path.exists() or path.read_text(encoding="utf-8") != svg
    path.write_text(svg, encoding="utf-8")
    print(f"profile.svg: {'updated' if changed else 'unchanged'}")


if __name__ == "__main__":
    main()
