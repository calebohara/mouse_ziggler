# Security & known issues

This file tracks audit findings that have NOT yet been fixed in the shipped
release. The full audit (5 specialist reviewers, 119 findings across
concurrency, security, Win32, packaging, UX) was run before v0.3.4. v0.3.4
shipped fixes for 11 CRIT + HIGH items; the remainder are recorded here so
the project is honest about what's known and what isn't fixed yet.

If you find something not on this list, please open an issue:
https://github.com/calebohara/noidle.app/issues

## Threat model in one paragraph

`noidle.app` is a personal Windows tray app. The realistic threat surface
is: **a malicious update channel** (someone who controls the GitHub repo or
your DNS pushes a compromised .exe), **shell handlers reached via crafted
URLs** (release-note links pointing at non-https schemes), **registry/
filesystem mis-write** (configs written without proper guards), and **CI
supply chain** (compromised GitHub Action shipping a backdoor release).
v0.3.4 hardened the latter three. The first one is open — see below.

---

## Open critical issues

### CRIT-A: No code signing, no signature verification on the update path
**Status:** open  ·  **Severity:** CRITICAL  ·  **Tracked since:** v0.3.4 audit

The `.exe` and `.msi` are not Authenticode-signed, and `updater.py` does no
detached-signature check on the downloaded artifact. If an attacker
compromises this GitHub repo (or their CI), they can ship a backdoored
release that the in-app updater happily presents to users. The README also
trains users to click through SmartScreen warnings, which makes a phishing-
style "lookalike installer" attack easier.

**Realistic fixes:**
- Code-signing certificate (~$200–$500/year for an OV cert, free via
  SignPath.io's OSS program for projects that meet their criteria)
- Detached cosign or minisign signatures on each release artifact + verify
  in `updater.py` before opening the download URL
- Publish a public-key fingerprint in this README so users can manually
  verify

Until that's done, treat every release like any other unsigned download:
verify the SHA256 against the GitHub release page, and prefer building
from source.

### CRIT-B: MSI install and portable .exe collide on `HKCU\Run` value name
**Status:** open  ·  **Severity:** CRITICAL  ·  **Tracked since:** v0.3.4 audit

Both the WiX MSI install and the portable .exe use the registry value name
`noidle` under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` for
"Start with Windows". If a user installs the MSI, then later runs the
portable .exe and toggles autostart, the MSI's Run entry is silently
overwritten and points at the .exe's last-known location. After an MSI
upgrade, autostart launches the stale Downloads-folder .exe instead of the
freshly installed one.

There's also no named mutex, so MSI-installed and portable copies can run
simultaneously, double-jiggling the input pipeline.

**Fix sketch:**
- Differentiate the autostart value name by install mode (`noidle-msi` vs
  `noidle-portable`)
- Add a process-wide named mutex (`Global\noidle.app.singleinstance`)
  checked at startup; second instance shows a notification and exits

### CRIT-C: Tray notifications are swallowed by Windows 11 Focus Assist
**Status:** open  ·  **Severity:** CRITICAL  ·  **Tracked since:** v0.3.4 audit

`pystray.Icon.notify()` posts a `Shell_NotifyIcon` balloon, which Focus
Assist filters with no feedback to the application. This affects every
"Show stats", "Show idle time", "autostart error" message, etc. The "What's
New" update prompt is **unaffected** because v0.3.4 changed it from a
balloon to a Tk modal subprocess.

**Fix sketch:** for non-update messages, switch to either (a) a small
always-on-top Tk dialog or (b) update the tray tooltip and use a transient
visual indicator (icon color flash) instead of a notification.

---

## Open high-severity issues

| ID | Component | Issue | Fix sketch |
|---|---|---|---|
| HIGH-1 | logging_setup.py / noidle.py | `mkdir + open("a")` on `%LOCALAPPDATA%\noidle\` follows Windows junctions. A pre-positioned attacker creating that path as a junction turns noidle into a write primitive. | Check `path.is_symlink()` before write; refuse to follow reparse points. |
| HIGH-2 | .github/workflows/*.yml | `actions/checkout@v4`, `softprops/action-gh-release@v2`, `actions/setup-python@v5` are pinned to mutable major-version tags, not commit SHAs. A maintainer compromise could re-point the tag at malicious code that ships a malicious release with this repo's `contents: write`. | Pin every external action to a commit SHA; document upgrade process in `docs/release.md`. |
| HIGH-3 | activity.py / jiggler.py | Smart-pause is a hardcoded 5-second threshold. At a 15-second interval with a fast typist, every tick can skip and Teams Away can still fire. | Cap effective skip-window at `min(5s, interval × 0.3)`; surface "Skipped (last 5min)" in the tooltip so the user knows. |
| HIGH-4 | jiggler.py | Locked workstation produces a `post-jiggle idle=N (expected ~0)` log warning every cycle indefinitely. No backoff. | Detect the lock state via `WTSGetActiveConsoleSessionId` / `WM_WTSSESSION_CHANGE`; sleep without trying to inject. |
| HIGH-5 | tray.py shutdown | If the hotkey thread is wedged on PostThreadMessageW the join times out at 2s and orphans the thread. Daemon flag means Python rips it on quit but Tcl/native handles aren't cleaned. | Bound shutdown to a hard deadline; force `os._exit()` if normal join doesn't complete. |
| HIGH-6 | requirements.txt vs pyproject.toml | Pinned vs ranged dependencies are out of sync. CI installs one set, `pip install .` users get another. | Single source of truth — generate one from the other in CI. |

---

## Where the full audit lives

The full audit reports — with file:line locations, repros, and per-finding
fix sketches — were generated by 5 specialist reviewers and saved to
`/tmp/audit-{concurrency,security,win32,packaging,ux}.md` on the dev
machine. They are NOT checked into this repo because they include lots of
internal references that aren't useful in the public history. If you're
contributing fixes and want the full text, ping the maintainer.

## Reporting new issues

Please open a GitHub issue: https://github.com/calebohara/noidle.app/issues
For sensitive disclosures (e.g. an active exploit affecting downloaded
binaries), email `caleb.ohara@gmail.com` and include the word "noidle" in
the subject line.
