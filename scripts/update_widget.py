"""Fetch the most recently played YouTube Music track and render an SVG card.

Exit codes:
  0  success, or a transient failure we deliberately swallow (retry next run)
  2  auth failure - credentials are invalid, needs human re-auth
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history_log  # noqa: E402
import render  # noqa: E402
import render_top  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state.json"
SVG_PATH = ROOT / "music.svg"
LOG_PATH = ROOT / "history.json"
TOP_SVG_PATH = ROOT / "top.svg"

EXIT_OK = 0
EXIT_AUTH = 2

# How long the card may go without a successful fetch before we stop calling it
# transient and start alerting. Comfortably longer than a normal quiet stretch
# (overnight, a day off music) so it only fires on a real stall.
STALE_AFTER_HOURS = 36

# Substrings that indicate the credential itself is bad, rather than YouTube
# having a transient wobble. Matched case-insensitively against the exception.
AUTH_MARKERS = (
    "unauthorized",
    "401",
    "403",
    "authentication",
    "not authenticated",
    "invalid credentials",
    "please provide authentication",
    "cookie",
    "invalid auth",
    "auth json",
    "file path provided",
    "no such file",
)


def log(msg: str) -> None:
    print(msg, flush=True)


def fail_auth(msg: str) -> None:
    """Signal to the workflow that a human must re-authenticate."""
    log(f"AUTH FAILURE: {msg}")
    if gh_out := os.environ.get("GITHUB_OUTPUT"):
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write("auth_failed=true\n")
    sys.exit(EXIT_AUTH)


def bail_transient(msg: str) -> None:
    """Leave the existing card untouched and try again on the next run.

    A genuine wobble resolves within a run or two. If the card has been stuck
    for STALE_AFTER_HOURS, "transient" is no longer a credible explanation, so
    escalate rather than keep exiting green.
    """
    stale_for = card_age_hours()
    if stale_for is not None and stale_for >= STALE_AFTER_HOURS:
        fail_auth(
            f"card has not updated in {stale_for:.0f}h "
            f"(threshold {STALE_AFTER_HOURS}h); latest failure: {msg}"
        )
    log(f"Transient failure (card left untouched, will retry): {msg}")
    sys.exit(EXIT_OK)


def looks_like_auth_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    if any(marker in text for marker in AUTH_MARKERS):
        return True

    # An expired cookie doesn't come back as a 401. YouTube serves a logged-out
    # page, ytmusicapi finds no history shelf to parse, and raises
    # YTMusicServerError(None) - an exception whose message is literally "None".
    # Without this, that misfiles as transient and the card silently rots behind
    # a green check (it went unnoticed for six days once).
    message = str(exc).strip().lower()
    return "ytmusicservererror" in text and message in ("", "none")


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        log("state.json unreadable, treating as first run")
        return {}


def card_age_hours() -> float | None:
    """Hours since the card last successfully updated, or None if unknown.

    Returns None on a first run or unreadable/timestamp-less state, where there
    is no baseline to judge staleness against and alerting would be noise.
    """
    first_seen = load_state().get("first_seen")
    if not first_seen:
        return None
    try:
        seen = datetime.fromisoformat(first_seen)
    except ValueError:
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - seen).total_seconds() / 3600)


def pick_thumbnail(thumbnails: list | None) -> str | None:
    """Choose the largest thumbnail that stays reasonable to inline as base64."""
    if not thumbnails:
        return None
    usable = [t for t in thumbnails if isinstance(t, dict) and t.get("url")]
    if not usable:
        return None
    usable.sort(key=lambda t: t.get("width", 0))
    for thumb in usable:
        if thumb.get("width", 0) >= 200:
            return thumb["url"]
    return usable[-1]["url"]


def fetch_thumbnail(url: str | None) -> bytes | None:
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ytm-widget/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read(3_000_000)
        return data or None
    except Exception as exc:  # noqa: BLE001 - art is optional, never fatal
        log(f"Thumbnail fetch failed, falling back to placeholder: {exc}")
        return None


def minutes_since(first_seen: str | None, now: datetime) -> int:
    """Elapsed whole minutes since first_seen, clamped at 0.

    A missing or unparseable timestamp means we have no idea how old the play
    is, so fall back to 0 ("just now") rather than inventing an age.
    """
    if not first_seen:
        return 0
    try:
        seen = datetime.fromisoformat(first_seen)
    except ValueError:
        return 0
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return max(0, int((now - seen).total_seconds() // 60))


def main() -> int:
    headers_raw = os.environ.get("YTM_HEADERS", "").strip()
    if not headers_raw:
        fail_auth("YTM_HEADERS secret is empty or missing")

    try:
        from ytmusicapi import YTMusic, setup as ytm_setup
    except ImportError as exc:
        bail_transient(f"ytmusicapi import failed: {exc}")

    # The secret may hold either raw browser headers ("Key: value" lines, which
    # is what DevTools "Copy All" produces) or an already-converted JSON blob.
    # ytmusicapi only accepts the latter, so convert when needed.
    auth = headers_raw
    if not headers_raw.lstrip().startswith("{"):
        try:
            auth = ytm_setup(headers_raw=headers_raw)
        except Exception as exc:  # noqa: BLE001
            fail_auth(f"could not parse YTM_HEADERS as browser headers: {exc}")
        if isinstance(auth, dict):
            auth = json.dumps(auth)

    try:
        yt = YTMusic(auth)
    except Exception as exc:  # noqa: BLE001
        if looks_like_auth_error(exc):
            fail_auth(f"could not initialise client: {exc}")
        bail_transient(f"client init failed: {exc}")

    try:
        history = yt.get_history()
    except Exception as exc:  # noqa: BLE001
        if looks_like_auth_error(exc):
            fail_auth(f"get_history rejected: {exc}")
        bail_transient(f"get_history failed: {exc}")

    if not history:
        bail_transient("history is empty (is YouTube history enabled on the account?)")

    track = history[0]
    video_id = track.get("videoId") or track.get("title", "unknown")
    title = track.get("title", "Unknown track")
    artists = track.get("artists") or []
    album = (track.get("album") or {}).get("name") if isinstance(track.get("album"), dict) else None

    state = load_state()
    now = datetime.now(timezone.utc)

    plays = history_log.prune(history_log.load(LOG_PATH), now)
    plays, fresh_count = history_log.record_history(plays, history, now)
    history_log.save(LOG_PATH, plays, now)

    top = history_log.recent_tracks(plays, limit=5)
    top_art = [fetch_thumbnail(e.get("thumbnail")) for e in top]
    TOP_SVG_PATH.write_text(
        render_top.render(top, top_art, days=history_log.WINDOW_DAYS),
        encoding="utf-8",
    )
    if fresh_count:
        log(f"Logged {fresh_count} new play(s); {len(plays)} in window")

    # While the same track is still on top, keep the original first_seen so the
    # card ages ("5 min ago") instead of resetting to "just now" every run.
    same_track = state.get("videoId") == video_id and SVG_PATH.exists()
    first_seen = state.get("first_seen") if same_track else None
    if not first_seen:
        first_seen = now.isoformat()

    thumb_bytes = fetch_thumbnail(pick_thumbnail(track.get("thumbnails")))

    svg = render.render(
        title=title,
        artists=artists,
        album=album,
        thumb_bytes=thumb_bytes,
        minutes_ago=minutes_since(first_seen, now),
    )

    # Only claim "changed" when generated output actually moved, so the workflow
    # stops producing empty commits on runs where nothing differs. fresh_count
    # covers history.json/top.svg, which change independently of the card.
    previous_svg = SVG_PATH.read_text(encoding="utf-8") if SVG_PATH.exists() else None
    changed = svg != previous_svg or bool(fresh_count)
    SVG_PATH.write_text(svg, encoding="utf-8")
    STATE_PATH.write_text(
        json.dumps(
            {"videoId": video_id, "title": title, "first_seen": first_seen},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    artist_names = ", ".join(a.get("name", "") for a in artists) or "Unknown"
    log(f"{'Updated' if changed else 'Unchanged'}: {title} - {artist_names}")
    if gh_out := os.environ.get("GITHUB_OUTPUT"):
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")
            fh.write(f"video_id={video_id}\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
