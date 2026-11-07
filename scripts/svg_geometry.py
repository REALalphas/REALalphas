"""Shared Alpha UI corner geometry for generated SVG cards."""

import math


def contour(x, y, width, height, radius):
    """Sample CSS corner-shape: superellipse(1.2) for a portable SVG path."""
    radius = min(radius, width / 2, height / 2)
    exponent = 2 / (2 ** 1.2)
    points = []
    for cx, cy, start in [(x + width - radius, y + radius, -90),
                           (x + width - radius, y + height - radius, 0),
                           (x + radius, y + height - radius, 90),
                           (x + radius, y + radius, 180)]:
        for step in range(17):
            angle = math.radians(start + step * 90 / 16)
            cosine, sine = math.cos(angle), math.sin(angle)
            points.append((cx + radius * math.copysign(abs(cosine) ** exponent, cosine),
                           cy + radius * math.copysign(abs(sine) ** exponent, sine)))
    return "M" + "L".join(f"{px:.3f},{py:.3f}" for px, py in points) + "Z"
