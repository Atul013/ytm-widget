# YT Music Widget

A card showing the last track played on my YouTube Music account, in my GitHub
profile README. It refreshes every 30 minutes. There is no server — a scheduled
GitHub Action does the work and commits the result back to this repository.

![Last played](https://raw.githubusercontent.com/Atul013/ytm-widget/main/music.svg)

![Most played this week](https://raw.githubusercontent.com/Atul013/ytm-widget/main/top.svg)

---

## The constraint everything else follows from

**YouTube Music has no now-playing API.** Not private, not undocumented — it does
not exist. Spotify publishes a currently-playing endpoint; YouTube Music has no
equivalent, for any client.

So this reads your play **history** and shows the most recent entry. A track only
enters history once it finishes or you skip it, which means the card structurally
trails live playback by roughly one track length plus however long until the next
scheduled run. The card is labelled "Last played" rather than "Now playing"
because that is honestly what the data is.

If you want a genuinely live now-playing card, scrobble to Last.fm (via Web
Scrobbler or the mobile app) and use a Last.fm widget instead. Last.fm receives a
"now playing" signal *while* a track plays. That is a different project from this
one, and a better fit if live is what matters to you.

## Play counts are observed, not reported

There is no play-count API either — nothing in `ytmusicapi` returns "times
played". `get_history()` is a flat recency list with no counts and no timestamps.

So the weekly card counts what the workflow itself sees. Every 30 minutes it
records the current top-of-history track, and a track is counted once per
observation. A track still sitting at the top on the next poll is the same play,
not a new one.

This **undercounts, by design**. Anything played and replaced between two polls
is never observed, so short tracks are missed more often than long ones, and a
heavy listening session collapses into a handful of observations. Treat the
ranking as directionally right rather than exact — the card says "approximate"
for this reason.

Observations older than 7 days are pruned, and the log is capped at 4000 entries.
The card is empty on day one and becomes meaningful after a few days of listening.

## Why a GitHub Action instead of a hosted service

The obvious design is a small web service that renders the SVG on request. That
approach has two specific problems this one avoids:

- **Serverless filesystems are read-only.** `ytmusicapi` wants to write its token
  to disk, so running it on Vercel means patching or vendoring the library. Here
  the credential is converted in memory and never touched to disk at all.
- **GitHub caches external images.** README images are proxied through Camo, so a
  live endpoint's output gets cached anyway and the "live" part is largely lost.
  A committed file has no such layer — it updates when the commit lands.

The tradeoff is granularity: a cron cannot go finer than a minute, and in practice
GitHub's scheduled runners slip under load. That is acceptable for data that is
already minutes stale by nature.

## How it works

```
GitHub Action (cron: */30)
  └─ ytmusicapi, auth from YTM_HEADERS secret (converted in memory)
     └─ get_history()[0]
        └─ compare with state.json
           ├─ same track  → exit, no commit
           └─ new track   → render music.svg → commit
```

History is tied to your **Google account, not a device.** Tracks played in the
phone app count exactly the same as tracks played in a browser, so your computer
does not need to be on — or even to exist.

Two details that are not obvious but matter:

- **Album art is base64-inlined into the SVG.** GitHub's SVG sanitizer blocks
  remote `<image href>`, so a Google CDN URL renders as nothing. It must be embedded.
- **All text is XML-escaped.** One track title containing `&` or `<` will otherwise
  produce a malformed SVG and a blank card. "Tom & Jerry" is enough to break it.

## Setup

You need a GitHub account and a YouTube Music account. Nothing else — no hosting,
no local runtime after setup.

**1. Fork this repository**, then clone your fork.

**2. Get your YouTube Music headers.**

- Open <https://music.youtube.com> while logged in
- Open DevTools (`F12`) → **Network** tab
- Reload the page (`Ctrl+R`) — Network only records while it is open
- Click any request with method **POST** to `music.youtube.com`
  (`next`, `browse`, `account_menu`, and `get_search_suggestions` all work)
- Open the **Headers** panel → scroll to **Request Headers** → switch to **Raw**
- Copy the whole block

Check what you copied contains both an `Authorization:` line and a long `Cookie:`
line. If there is no `Cookie:`, you copied *Response* headers by mistake — they sit
directly above Request headers and are easy to hit.

**3. Store it as a secret** named exactly `YTM_HEADERS`:

```bash
gh secret set YTM_HEADERS
# paste, then Ctrl+Z + Enter on Windows, Ctrl+D on macOS/Linux
```

Or via the web UI: *Settings → Secrets and variables → Actions → New repository secret*.

**4. Point the embed at your own repository** — edit the image URL at the top of
this README to use your username and repository name.

**5. Run it.** *Actions → Update YT Music widget → Run workflow.* It should finish
in well under a minute and commit `music.svg`.

**6. Embed it in your profile.** Add this to the README of the repository named
after your GitHub username:

```markdown
![Last played](https://raw.githubusercontent.com/YOUR_USERNAME/ytm-widget/main/music.svg)
```

If you keep this repository **private**, `raw.githubusercontent.com` returns 404
for everyone but you, and the image will appear broken on your profile. Either
make it public, or have the workflow push the SVG into your public profile
repository instead.

## Configuration

**Schedule** — edit the cron in `.github/workflows/widget.yml`:

```yaml
- cron: "*/30 * * * *"   # every 30 minutes
```

GitHub's scheduled runners are best-effort and slip under load, so treat any
interval as a ceiling rather than a promise. Below about 15 minutes you are mostly
adding runs, not freshness.

**Appearance** — `scripts/render.py` holds the whole card: 420×140, with light and
dark palettes driven by `prefers-color-scheme` so it suits either GitHub theme.

## Failure handling

Failures are split into two kinds, deliberately:

| Kind | Example | Behaviour |
|---|---|---|
| **Auth** | invalid or expired cookie | Opens an issue, fails the run (GitHub emails you) |
| **Transient** | timeout, YouTube 5xx, empty history | Logs and exits 0, retries next run |

In both cases `music.svg` is left untouched, so a failed run keeps the last good
card on your profile instead of replacing it with an error state.

The auth issue is titled `YTM widget: re-auth needed` and is **reused rather than
re-filed**, so a weekend of failures produces one issue rather than ninety-six.

This split matters more than it looks. During development a malformed-credential
error was being classified as transient, so a completely broken run exited 0 and
reported success while doing nothing at all. A silent failure on a widget is
particularly bad, because a stale card is indistinguishable from a working one.

## Credential lifetime

Browser credentials remain valid as long as the YouTube Music browser session
does — [about two years unless you log out][ytmusicapi-browser].

**Logging out of YouTube Music in the browser you copied the headers from is what
invalidates them**, not the passage of time. Closing the browser is fine.

[ytmusicapi-browser]: https://ytmusicapi.readthedocs.io/en/stable/setup/browser.html

## Known limitations

- **Up to ~30 minutes stale**, plus runner slippage. 40–50 minute gaps are normal.
- **The relative timestamp is approximate.** History entries carry no played-at
  field, so elapsed time is measured from when the workflow first observed the
  change — not when you actually played the track.
- **Paused is indistinguishable from stopped.** Stop listening and the card holds
  the last track indefinitely. There is no idle signal to detect.
- **Requires YouTube history to be enabled.** If history is paused on your Google
  account, or you listen in incognito, nothing is recorded and the card never moves.
- **Scheduled workflows are disabled after 60 days of repository inactivity.**
  Normal listening produces commits, which counts as activity.
- **Weekly counts undercount actual plays**, because polling is coarser than
  listening. See "Play counts are observed, not reported" above.
- **A silently dead workflow is not alerted.** If runs stop entirely, nothing
  fails, so nothing notifies. A dead-man's-switch (e.g. Healthchecks.io) would
  cover this; it is deliberately out of scope here.

## Repository layout

| Path | Purpose |
|---|---|
| `.github/workflows/widget.yml` | Cron, commit-if-changed, issue-on-auth-failure |
| `scripts/update_widget.py` | Fetch, state comparison, error classification |
| `scripts/render.py` | SVG template and text escaping |
| `scripts/history_log.py` | Rolling observation log and weekly ranking |
| `scripts/render_top.py` | Most-played card template |
| `state.json` | Last seen track and first-observed timestamp |
| `history.json` | Rolling 7-day observation log |
| `music.svg` | The last-played card |
| `top.svg` | The most-played-this-week card |

## Prior art

[moguism/YTMusicReadme](https://github.com/moguism/YTMusicReadme) does the same
thing as a Flask app on Vercel, and is where the `ytmusicapi` approach came from.
This repository shares no code with it — dropping the hosting layer removed most
of what that project consists of.

Worth distinguishing from playlist-based widgets, which display a random track
from a public playlist you choose. Those require no authentication because they
never touch your account, and they do not reflect your listening at all.

## Security

`YTM_HEADERS` authenticates as your Google account. Treat it like a password —
see [SECURITY.md](SECURITY.md) for handling and revocation.

Note that a public repository also makes `state.json` and the commit history
public, which together are an ongoing log of what you listen to. That is inherent
to how the widget works, but it is worth deciding on deliberately.

## Acknowledgements

Built on [ytmusicapi](https://github.com/sigma67/ytmusicapi), which does the
hard part of talking to an API that was never meant to be talked to.

## License

[MIT](LICENSE)

Built with [ytmusicapi](https://github.com/sigma67/ytmusicapi) by sigma67.
