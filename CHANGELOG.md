# Changelog

## 2026-08-19

Initial release.

- Scheduled Action fetches YouTube Music play history and renders an SVG card
- Auth passed as a header string via secret; converted in memory, never written to disk
- Auth failures open a reused issue and fail loudly; transient errors retry quietly
- Card is never overwritten on failure, so the last good version stays up
- Thumbnails base64-inlined; all text XML-escaped
