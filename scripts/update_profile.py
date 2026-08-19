"""Write the current track's link into the profile README.

The card image is static markup, but the track it shows changes. A visitor
clicking it should land on that specific song, which means the link URL has to
be rewritten whenever the track changes. The profile README lives in a separate
repository, so this needs a token with contents:write on that repo - the
built-in GITHUB_TOKEN only reaches the repo the workflow runs in.

Only the text between the marker comments is touched. Everything else in the
README is left exactly as it was.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request

START = "<!--YTM:START-->"
END = "<!--YTM:END-->"
API = "https://api.github.com"


def log(msg: str) -> None:
    print(msg, flush=True)


def _request(url: str, token: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "ytm-widget")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_block(video_id: str, card_url: str, width: int = 420) -> str:
    """The markup placed between the markers.

    Wrapping the image in an anchor is what makes the card clickable; GitHub
    strips <a> inside SVG, so the link has to live in the README markup.
    """
    href = f"https://music.youtube.com/watch?v={video_id}"
    return (
        f'{START}\n'
        f'<a href="{href}">\n'
        f'  <img src="{card_url}" alt="Last played on YouTube Music" width="{width}" />\n'
        f'</a>\n'
        f'{END}'
    )


def replace_block(content: str, block: str) -> str | None:
    """Swap the marked region. Returns None if markers are missing or malformed."""
    start = content.find(START)
    end = content.find(END)
    if start == -1 or end == -1 or end < start:
        return None
    return content[:start] + block + content[end + len(END):]


def main() -> int:
    token = os.environ.get("PROFILE_TOKEN", "").strip()
    if not token:
        log("PROFILE_TOKEN not set; skipping profile link update.")
        return 0

    video_id = os.environ.get("TRACK_VIDEO_ID", "").strip()
    if not video_id:
        log("No videoId available; skipping profile link update.")
        return 0

    repo = os.environ.get("PROFILE_REPO", "").strip()
    path = os.environ.get("PROFILE_PATH", "README.md").strip()
    card_url = os.environ.get("CARD_URL", "").strip()
    if not repo or not card_url:
        log("PROFILE_REPO or CARD_URL missing; skipping profile link update.")
        return 0

    url = f"{API}/repos/{repo}/contents/{path}"

    try:
        current = _request(url, token)
    except urllib.error.HTTPError as exc:
        # A bad or expired token is worth shouting about; anything else is
        # transient and should not take down the widget run.
        if exc.code in (401, 403):
            log(f"::error::PROFILE_TOKEN rejected ({exc.code}). It may have expired.")
            return 1
        log(f"Could not read {repo}/{path} ({exc.code}); skipping.")
        return 0
    except Exception as exc:  # noqa: BLE001
        log(f"Could not read {repo}/{path} ({exc}); skipping.")
        return 0

    try:
        content = base64.b64decode(current["content"]).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        log(f"Could not decode {path} ({exc}); skipping.")
        return 0

    updated = replace_block(content, build_block(video_id, card_url))
    if updated is None:
        log(
            f"::warning::{START} / {END} markers not found in {repo}/{path}. "
            "Add them around the card so the link can be kept current."
        )
        return 0

    if updated == content:
        log("Profile link already current.")
        return 0

    try:
        _request(
            url,
            token,
            method="PUT",
            payload={
                "message": "chore: update now playing link",
                "content": base64.b64encode(updated.encode("utf-8")).decode("ascii"),
                "sha": current["sha"],
            },
        )
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            log(f"::error::PROFILE_TOKEN lacks write access ({exc.code}).")
            return 1
        # 409 means someone else wrote first; the next run will catch up.
        log(f"Could not write {repo}/{path} ({exc.code}); will retry next run.")
        return 0
    except Exception as exc:  # noqa: BLE001
        log(f"Could not write {repo}/{path} ({exc}); will retry next run.")
        return 0

    log(f"Profile link updated -> {video_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
