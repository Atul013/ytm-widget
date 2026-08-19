"""SVG card renderer for the YouTube Music last-played widget."""

from __future__ import annotations

import base64
from html import escape
from typing import Iterable

CARD_W = 420
CARD_H = 140
ART = 100
PAD = 20


def _esc(text: str) -> str:
    """Escape text for safe embedding in SVG/XML.

    Track titles routinely contain & and < (e.g. "Tom & Jerry", "<3").
    Unescaped, a single one of these corrupts the entire card.
    """
    return escape(str(text or ""), quote=True)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "\u2026"


def _relative_time(minutes: int | None) -> str:
    if minutes is None:
        return "recently"
    if minutes < 1:
        return "just now"
    if minutes == 1:
        return "1 min ago"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes // 60
    if hours == 1:
        return "1 hour ago"
    if hours < 24:
        return f"{hours} hours ago"
    days = hours // 24
    return "1 day ago" if days == 1 else f"{days} days ago"


def _artist_line(artists: Iterable[dict] | None) -> str:
    if not artists:
        return "Unknown artist"
    names = [a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")]
    return ", ".join(names) if names else "Unknown artist"


def _thumb_data_uri(image_bytes: bytes | None, mime: str = "image/jpeg") -> str | None:
    """GitHub's SVG sanitizer blocks remote <image href>, so art must be inlined."""
    if not image_bytes:
        return None
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def render(
    title: str,
    artists: Iterable[dict] | None,
    album: str | None,
    thumb_bytes: bytes | None,
    minutes_ago: int | None,
) -> str:
    title_t = _esc(_truncate(title or "Unknown track", 30))
    artist_t = _esc(_truncate(_artist_line(artists), 34))
    album_t = _esc(_truncate(album or "", 34))
    when_t = _esc(_relative_time(minutes_ago))

    thumb_uri = _thumb_data_uri(thumb_bytes)
    text_x = PAD + ART + 18

    if thumb_uri:
        art = (
            f'<image x="{PAD}" y="{PAD}" width="{ART}" height="{ART}" '
            f'href="{thumb_uri}" clip-path="url(#round)" '
            f'preserveAspectRatio="xMidYMid slice"/>'
        )
    else:
        art = (
            f'<rect x="{PAD}" y="{PAD}" width="{ART}" height="{ART}" rx="10" '
            f'fill="var(--muted-bg)"/>'
            f'<text x="{PAD + ART // 2}" y="{PAD + ART // 2 + 8}" '
            f'text-anchor="middle" class="ph">\u266a</text>'
        )

    album_el = (
        f'<text x="{text_x}" y="{PAD + 78}" class="album">{album_t}</text>'
        if album_t
        else ""
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{CARD_H}" viewBox="0 0 {CARD_W} {CARD_H}" role="img" aria-label="Last played on YouTube Music: {title_t} by {artist_t}">
  <defs>
    <clipPath id="round">
      <rect x="{PAD}" y="{PAD}" width="{ART}" height="{ART}" rx="10"/>
    </clipPath>
  </defs>
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
    .label {{ font-size: 10px; font-weight: 600; fill: var(--accent); letter-spacing: .08em; }}
    .title {{ font-size: 15px; font-weight: 700; fill: var(--fg); }}
    .artist {{ font-size: 12.5px; fill: var(--sub); }}
    .album {{ font-size: 11px; fill: var(--sub); opacity: .8; }}
    .when {{ font-size: 10.5px; fill: var(--sub); }}
    .ph {{ font-size: 34px; fill: var(--sub); }}
  </style>
  <rect class="card" x="0.5" y="0.5" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="12"/>
  {art}
  <text x="{text_x}" y="{PAD + 14}" class="label">LAST PLAYED</text>
  <text x="{text_x}" y="{PAD + 38}" class="title">{title_t}</text>
  <text x="{text_x}" y="{PAD + 58}" class="artist">{artist_t}</text>
  {album_el}
  <text x="{text_x}" y="{CARD_H - PAD - 2}" class="when">{when_t}</text>
</svg>
"""
