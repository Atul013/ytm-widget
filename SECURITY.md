# Security

## Reporting a vulnerability

Email <atul@icarus13.in> or open an issue. This is a small personal project
with no formal disclosure process; please avoid including working
credentials in the report.

## How credentials are handled

`YTM_HEADERS` holds YouTube Music request headers, including a session cookie
that authenticates as your Google account. Treat it exactly like a password.

- It is stored as a **GitHub Actions secret**, encrypted at rest and masked in logs.
- It is passed to the script as an **environment variable** and converted in
  memory. It is **never written to the runner's filesystem**.
- `browser.json`, `oauth.json`, `headers_auth.json` and `.env` are gitignored so
  a local test file cannot be committed by accident.

## If you fork this

Your fork does **not** inherit the upstream secret — you must add your own.
Never commit header text to the repository, even briefly: anything pushed to a
public repo should be considered permanently disclosed, and rewriting history
does not reliably remove it.

## Revoking access

If the secret leaks, log out of YouTube Music in the browser session the headers
came from. That invalidates the cookie and renders the leaked value useless.
Delete the repository secret as well.

## What this project can and cannot do

The credential grants read access to your YouTube Music account. This code uses
it only to call `get_history()`. It never writes to your account, and no data
leaves GitHub except the request to YouTube itself and the album-art fetch.

## Note on a public repository

Making this repository public also makes `state.json` and the commit history
public. Together they form an ongoing, timestamped log of what you listen to.
That is inherent to the widget, but it is worth deciding deliberately.
