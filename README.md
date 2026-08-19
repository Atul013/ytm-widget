# YT Music Last-Played Widget

An SVG card showing the most recent track played on my YouTube Music account,
refreshed every 30 minutes by a GitHub Action. No server, no hosting.

![Last played](https://raw.githubusercontent.com/USER/REPO/main/music.svg)

> Replace `USER/REPO` above with your GitHub username and repository name.

## How it works

A scheduled Action calls `ytmusicapi.get_history()`, takes the top entry, renders
`music.svg`, and commits it only when the track has changed. The README embeds
that file directly, so GitHub serves it fresh rather than through its image cache.

History is tied to your **Google account**, not to a device — tracks played in the
YouTube Music phone app count exactly the same as tracks played in a browser.

## Setup

1. **Create the secret.** Open <https://music.youtube.com> while logged in.
   DevTools → Network → click any POST request to `music.youtube.com` → copy the
   full request headers. Save them as a repository secret named `YTM_HEADERS`
   (Settings → Secrets and variables → Actions).
2. **Fix the embed URL** in this README.
3. **Run it.** Actions tab → *Update YT Music widget* → *Run workflow*.

## What this is not

YouTube Music has **no now-playing API**. This reads play *history*, and a track
only enters history once it finishes or is skipped. The card therefore trails live
playback by roughly one track length plus the cron interval. It is labelled
"Last played" because that is what the data actually is.

## Known limitations

- **Up to ~30 minutes stale**, and GitHub's scheduled runners slip under load, so
  40–50 minute gaps are normal. The cron is a target, not a guarantee.
- **The "N min ago" label is approximate.** History entries carry no timestamp, so
  it measures from when the workflow first observed the change, not actual play time.
- **Paused is indistinguishable from stopped.** If you stop listening, the card
  holds the last track indefinitely.
- **Scheduled workflows are disabled after 60 days of repository inactivity.**
  Normal listening produces commits, which keeps it alive.
- **Silent death is not alerted.** If the workflow stops running altogether,
  nothing fails, so nothing notifies. A dead-man's-switch (e.g. Healthchecks.io)
  would cover this; it is deliberately out of scope here.

## When it breaks

Credentials last as long as your YouTube Music browser session — roughly two years
unless you log out. **Logging out of YTM in the browser you copied headers from is
what invalidates them**, not the passage of time.

On an auth failure the workflow opens an issue titled `YTM widget: re-auth needed`
(reused, not re-filed) and fails the run so GitHub emails you. The card is never
overwritten on failure, so the last good version stays up. Fix by repeating step 1
of Setup.

Transient errors — timeouts, YouTube 5xx — exit quietly and retry on the next run.

## Files

| Path | Purpose |
|---|---|
| `.github/workflows/widget.yml` | Cron, commit-if-changed, issue-on-auth-failure |
| `scripts/update_widget.py` | Fetch, state comparison, error routing |
| `scripts/render.py` | SVG template |
| `state.json` | Last seen track + first-observed timestamp |
| `music.svg` | The generated card |
