"""Rolling play log for weekly counts.

There is no play-count API in YouTube Music. `get_history()` returns a flat
recency list, newest first, with no counts and no timestamps - but it returns
around 200 entries, not just the current track. That full list is what makes
real counts possible.

Each run diffs the returned list against what we have already recorded and
appends everything that is new. Because the list reaches far further back than
one polling interval, tracks played *between* polls are still captured. Polling
only has to be frequent enough that fewer than ~200 tracks pass between runs.

What this still cannot see: the API returns each track once per appearance in
the history feed, so a song played three times in a row may appear once. Counts
are therefore a floor, not an exact tally.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WINDOW_DAYS = 7
# Cap retained plays so the file cannot grow without bound.
MAX_ENTRIES = 4000


def _parse(ts: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    # "observations" is the pre-1.1 key; read it so existing logs survive.
    return data.get("plays", data.get("observations", []))


def prune(plays: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    cutoff = now - timedelta(days=WINDOW_DAYS)
    kept = [
        p for p in plays
        if (seen := _parse(p.get("seen", ""))) is not None and seen >= cutoff
    ]
    return kept[-MAX_ENTRIES:]


def _signature(track: dict[str, Any]) -> str:
    """Identify a history entry. videoId alone is not enough - the same song
    appears repeatedly across the feed, and we need to tell a genuinely new
    appearance from one we have already recorded."""
    return str(track.get("videoId") or track.get("title", ""))


def record_history(
    plays: list[dict[str, Any]],
    history: list[dict[str, Any]],
    now: datetime,
) -> tuple[list[dict[str, Any]], int]:
    """Append every history entry newer than the last one we recorded.

    `history` is newest-first. We walk it until we hit the most recent entry we
    already know about, then record everything above that point - those are the
    tracks played since the previous run.

    On the very first run there is no anchor, so the whole returned list is
    recorded. That backfills genuine listening history rather than starting
    empty, at the cost of not knowing exactly when those plays happened.
    """
    if not history:
        return plays, 0

    known = {p.get("videoId") for p in plays}
    anchor = plays[-1].get("videoId") if plays else None

    fresh: list[dict[str, Any]] = []
    for track in history:
        sig = _signature(track)
        if anchor and sig == anchor:
            break
        fresh.append(track)

    # No anchor match means the feed moved on further than we can reconcile.
    # Fall back to recording only entries we have never seen at all.
    if anchor and len(fresh) == len(history):
        fresh = [t for t in history if _signature(t) not in known]

    # `history` is newest-first; store oldest-first so the log reads forward
    # and `plays[-1]` stays the most recent entry.
    for track in reversed(fresh):
        artists = track.get("artists") or []
        album = track.get("album")
        plays.append(
            {
                "videoId": _signature(track),
                "title": track.get("title", "Unknown"),
                "artist": ", ".join(
                    a.get("name", "") for a in artists
                    if isinstance(a, dict) and a.get("name")
                ) or "Unknown artist",
                "album": album.get("name") if isinstance(album, dict) else None,
                "thumbnail": _best_thumb(track.get("thumbnails")),
                "seen": now.isoformat(),
            }
        )

    return plays, len(fresh)


def _best_thumb(thumbnails: list | None) -> str | None:
    if not thumbnails:
        return None
    usable = [t for t in thumbnails if isinstance(t, dict) and t.get("url")]
    if not usable:
        return None
    usable.sort(key=lambda t: t.get("width", 0))
    for thumb in usable:
        if thumb.get("width", 0) >= 120:
            return thumb["url"]
    return usable[-1]["url"]


def top_tracks(plays: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Rank tracks by play count, most played first.

    Ties break by recency, so with equal counts the more recently played track
    ranks higher. Note that when every count is 1 this degenerates into a
    recency list - a signal that the log has not accumulated enough to rank.
    """
    tallies: dict[str, dict[str, Any]] = {}
    for play in plays:
        video_id = play.get("videoId")
        if not video_id:
            continue
        entry = tallies.setdefault(
            video_id,
            {
                "videoId": video_id,
                "title": play.get("title", "Unknown"),
                "artist": play.get("artist", "Unknown artist"),
                "album": play.get("album"),
                "thumbnail": play.get("thumbnail"),
                "count": 0,
                "last_seen": play.get("seen", ""),
            },
        )
        entry["count"] += 1
        if play.get("seen", "") > entry["last_seen"]:
            entry["last_seen"] = play["seen"]
            if play.get("thumbnail"):
                entry["thumbnail"] = play["thumbnail"]

    ranked = sorted(tallies.values(), key=lambda e: (e["count"], e["last_seen"]), reverse=True)
    return ranked[:limit]


def save(path: Path, plays: list[dict[str, Any]], now: datetime) -> None:
    path.write_text(
        json.dumps(
            {
                "updated": now.isoformat(),
                "window_days": WINDOW_DAYS,
                "note": (
                    "Counts are built by diffing the full get_history() feed on "
                    "each run, so tracks played between polls are captured. The "
                    "feed lists each appearance once, so counts are a floor."
                ),
                "plays": plays,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
