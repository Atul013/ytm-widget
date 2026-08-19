# Changelog

## 2026-08-19

Initial release.

- Scheduled Action fetches YouTube Music play history and renders an SVG card
- Auth passed as a header string via secret; converted in memory, never written to disk
- Auth failures open a reused issue and fail loudly; transient errors retry quietly
- Card is never overwritten on failure, so the last good version stays up
- Thumbnails base64-inlined; all text XML-escaped

## 2026-08-19 (later)

- Add most-played-this-week card built from a rolling 7-day observation log
- Retry push on concurrent-run races instead of failing the run
