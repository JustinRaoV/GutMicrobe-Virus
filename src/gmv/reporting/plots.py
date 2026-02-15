"""Simple SVG chart generators (no extra plotting dependency)."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


def write_bar_svg(output: str | Path, title: str, x_label: str, y_label: str, data: Sequence[Tuple[str, float]]) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    width, height = 900, 480
    margin_left, margin_bottom = 90, 90
    margin_top, margin_right = 70, 40
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    values: List[float] = [max(0.0, float(v)) for _, v in data]
    max_v = max(values) if values else 1.0
    if max_v == 0:
        max_v = 1.0

    bars = []
    n = len(data)
    bar_w = plot_w / max(1, n * 1.5)
    gap = bar_w / 2
    x = margin_left + gap

    for label, val in data:
        h = (float(val) / max_v) * plot_h
        y = margin_top + (plot_h - h)
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="#3A86FF" />'
        )
        bars.append(
            f'<text x="{x + bar_w/2:.2f}" y="{margin_top + plot_h + 20:.2f}" '
            f'font-size="11" text-anchor="middle">{label}</text>'
        )
        bars.append(
            f'<text x="{x + bar_w/2:.2f}" y="{max(margin_top + 12, y - 4):.2f}" '
            f'font-size="10" text-anchor="middle">{int(val)}</text>'
        )
        x += bar_w + gap

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect width="100%" height="100%" fill="#F8F9FB" />
  <text x="{width/2}" y="30" font-size="20" text-anchor="middle" fill="#111">{title}</text>
  <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}" stroke="#111" stroke-width="2" />
  <line x1="{margin_left}" y1="{margin_top + plot_h}" x2="{margin_left + plot_w}" y2="{margin_top + plot_h}" stroke="#111" stroke-width="2" />
  <text x="{margin_left + plot_w/2}" y="{height - 20}" font-size="14" text-anchor="middle">{x_label}</text>
  <text transform="translate(22,{margin_top + plot_h/2}) rotate(-90)" font-size="14" text-anchor="middle">{y_label}</text>
  {''.join(bars)}
</svg>
'''
    output_path.write_text(svg, encoding="utf-8")
