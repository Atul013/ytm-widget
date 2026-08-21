"""SVG renderer for the recently-played card.

This lists recent tracks in order rather than ranking them by play count.
get_history() gives every appearance its own videoId, so the feed cannot say
"played N times"; counting across polls only increments on a replay we happen
to catch, which for varied listening almost never outranks the steady stream of
new tracks. A "most played" ranking would therefore be recency wearing a
misleading label, so the card says what it actually shows.
"""

from __future__ import annotations

import base64
from html import escape
from typing import Any

CARD_W = 420
HEADER_H = 46
ROW_H = 56
FOOTER_H = 26
PAD = 18
ART = 42


def _esc(text: str) -> str:
    return escape(str(text or ""), quote=True)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def _row(index: int, entry: dict[str, Any], art_b64: bytes | None, y: int) -> str:
    rank = index + 1
    title = _esc(_truncate(entry.get("title", "Unknown"), 26))
    artist = _esc(_truncate(entry.get("artist", "Unknown artist"), 30))
    album = _esc(_truncate(entry.get("album") or "", 16))
    art_x = PAD + 22
    text_x = art_x + ART + 12

    if art_b64:
        uri = f"data:image/jpeg;base64,{base64.b64encode(art_b64).decode('ascii')}"
        art = (
            f'<image x="{art_x}" y="{y + 6}" width="{ART}" height="{ART}" '
            f'href="{uri}" clip-path="url(#r{rank})" preserveAspectRatio="xMidYMid slice"/>'
        )
    else:
        art = (
            f'<rect x="{art_x}" y="{y + 6}" width="{ART}" height="{ART}" rx="6" '
            f'fill="var(--muted-bg)"/>'
        )

    return f"""  <clipPath id="r{rank}"><rect x="{art_x}" y="{y + 6}" width="{ART}" height="{ART}" rx="6"/></clipPath>
  <text x="{PAD}" y="{y + 32}" class="rank">{rank}</text>
  {art}
  <text x="{text_x}" y="{y + 24}" class="title">{title}</text>
  <text x="{text_x}" y="{y + 40}" class="artist">{artist}</text>
  <text x="{CARD_W - PAD}" y="{y + 32}" class="plays" text-anchor="end">{album}</text>"""


def render(entries: list[dict[str, Any]], art: list[bytes | None], days: int = 7) -> str:
    if not entries:
        return _empty_card()

    rows_h = ROW_H * len(entries)
    card_h = HEADER_H + rows_h + FOOTER_H
    rows = "\n".join(
        _row(i, e, art[i] if i < len(art) else None, HEADER_H + i * ROW_H)
        for i, e in enumerate(entries)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{card_h}" viewBox="0 0 {CARD_W} {card_h}" role="img" aria-label="Recently played tracks">
  <style>
    :root {{
      --bg: #ffffff; --border: #d0d7de; --fg: #1f2328;
      --sub: #59636e; --accent: #cc0000; --muted-bg: #eaeef2;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0d1117; --border: #30363d; --fg: #e6edf3;
        --sub: #8b949e; --accent: #ff4444; --muted-bg: #21262d;
      }}
    }}
    .card {{ fill: var(--bg); stroke: var(--border); }}
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .head {{ font-size: 11px; font-weight: 700; fill: var(--accent); letter-spacing: .09em; }}
    .rank {{ font-size: 13px; font-weight: 700; fill: var(--sub); }}
    .title {{ font-size: 12.5px; font-weight: 600; fill: var(--fg); }}
    .artist {{ font-size: 11px; fill: var(--sub); }}
    .plays {{ font-size: 10px; fill: var(--sub); }}
    .foot {{ font-size: 9px; fill: var(--sub); opacity: .75; }}
  </style>
  <rect class="card" x="0.5" y="0.5" width="{CARD_W - 1}" height="{card_h - 1}" rx="12"/>
  <text x="{PAD}" y="28" class="head">RECENTLY PLAYED</text>
{rows}
  <text x="{PAD}" y="{card_h - 9}" class="foot">Most recent first</text>
</svg>
"""


def _empty_card() -> str:
    h = HEADER_H + 54
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{h}" viewBox="0 0 {CARD_W} {h}" role="img" aria-label="No listening data yet">
  <style>
    :root {{ --bg:#ffffff; --border:#d0d7de; --sub:#59636e; --accent:#cc0000; }}
    @media (prefers-color-scheme: dark) {{
      :root {{ --bg:#0d1117; --border:#30363d; --sub:#8b949e; --accent:#ff4444; }}
    }}
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .head {{ font-size: 11px; font-weight: 700; fill: var(--accent); letter-spacing: .09em; }}
    .msg {{ font-size: 12px; fill: var(--sub); }}
  </style>
  <rect fill="var(--bg)" stroke="var(--border)" x="0.5" y="0.5" width="{CARD_W - 1}" height="{h - 1}" rx="12"/>
  <text x="{PAD}" y="28" class="head">RECENTLY PLAYED</text>
  <text x="{PAD}" y="{HEADER_H + 22}" class="msg">No tracks recorded yet.</text>
</svg>
"""
