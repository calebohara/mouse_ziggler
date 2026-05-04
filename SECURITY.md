# Security & known issues

This file tracks audit findings that have NOT yet been fully fixed.
The full audit (5 specialist reviewers, 119 findings across concurrency,
security, Win32, packaging, UX) was run before v0.3.4. Across v0.3.4,
v0.3.5, and v0.3.6, **41 critical/high audit findings have been resolved**.
The items below are what remains.

If you find something not on this list, please open an issue:
https://github.com/calebohara/noidle.app/issues

## Threat model in one paragraph

`noidle.app` is a personal Windows tray app. The realistic threat surface
is: **a malicious update channel** (someone who controls the GitHub repo
or your DNS pushes a compromised .exe), **shell handlers reached via
crafted URLs** (release-note links pointing at non-https schemes),
**registry/filesystem mis-write** (configs written without proper
guards), and **CI supply chain** (compromised GitHub Action shipping a
backdoor release). Most of this surface is now hardened — see
[SIGNING.md](SIGNING.md) for what verification is currently possible.

---

## Open issues

### CRIT-A: Authenticode code signing (partial; SHA256+cosign shipped, MSFT cert pending)
**Status:** partial — see [SIGNING.md](SIGNING.md)  ·  **Severity:** CRITICAL  ·  **Tracked since:** v0.3.4 audit

**Shipped in v0.3.6:**
- `SHA256SUMS.txt` published with every release for tamper-evidence
- Cosign keyless signatures (`.sig` + `.pem`) for `noidle.exe`, `noidle.msi`,
  and `SHA256SUMS.txt` itself, generated via GitHub OIDC and logged to
  the Sigstore Rekor transparency log
- Verification instructions in [SIGNING.md](SIGNING.md)

**Still open:** Authenticode signing — the only thing that satisfies
Windows SmartScreen. Requires a code-signing certificate that costs
real money OR (preferred) approval into the
[SignPath.io OSS Foundation](https://signpath.io/foundation) free
program. SignPath application steps are in `SIGNING.md`.

Until Authenticode is in place, expect SmartScreen warnings on first
run. The README documents this honestly and points users at
`SHA256SUMS.txt` so they can verify the binary themselves.

### CRIT-C: Tray notifications + Windows 11 Focus Assist (partial)
**Status:** partial  ·  **Severity:** CRITICAL  ·  **Tracked since:** v0.3.4 audit

`pystray.Icon.notify()` posts a `Shell_NotifyIcon` balloon, which Focus
Assist filters with no feedback to the application.

**Shipped in v0.3.6:** the most important user-facing alert (hotkey
registration failed at startup) now uses a Tk dialog launched as a
subprocess instead of a tray balloon, so Focus Assist can't swallow it.
Update prompts already use a Tk modal (v0.3.4).

**Still open (low impact):** chatty / informational messages ("Show
stats", "Stats reset", "Show idle time", "Show autostart target")
still use the balloon API. These are nice-to-haves the user can also
read from the tooltip; missing one isn't harmful. A full notification
redesign would be overkill for the remaining surface.

---

## Open high-severity issues

| ID | Component | Issue | Fix sketch |
|---|---|---|---|
| HIGH-1 | logging_setup.py / noidle.py | `mkdir + open("a")` on `%LOCALAPPDATA%\noidle\` follows Windows junctions. A pre-positioned attacker creating that path as a junction turns noidle into a write primitive. | Check `path.is_symlink()` before write; refuse to follow reparse points. |
| HIGH-2 | .github/workflows/*.yml | `actions/checkout@v4`, `softprops/action-gh-release@v2`, `actions/setup-python@v5`, `sigstore/cosign-installer@v3` are pinned to mutable major-version tags (cosign IS pinned to a SHA in v0.3.6 — others not yet). A maintainer compromise could re-point a tag at malicious code that ships a malicious release. | Pin every external action to a commit SHA; document upgrade process in `docs/release.md`. |

---

## Resolved items

### CRIT-B: MSI install and portable .exe collide on `HKCU\Run` value name
**Status:** ✅ FIXED in v0.3.6

The MSI install and portable .exe used to fight over a single registry
value `noidle` under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

v0.3.6 introduces install-mode detection (`_install_mode()` in
`autostart.py`) that distinguishes between MSI installs (running from
`%LOCALAPPDATA%\Programs\noidle\`), portable runs, and dev runs. Each
mode writes its own registry value: `noidle.app` (MSI),
`noidle.app-portable`, `noidle.app-dev`. The legacy `noidle` value
from v0.3.0–v0.3.5 is opportunistically swept on the next `enable()`
or `disable()` call so upgrading users don't end up with two stale
autostart entries.

Single-instance enforcement was already added in v0.3.5 via a Win32
named mutex (`Global\noidle.app.singleinstance`).

### Other resolved CRIT/HIGH items

See git history (v0.3.4, v0.3.5, v0.3.6 release notes). Highlights:
- Tkinter on background thread → subprocess (v0.3.4)
- Shell injection in update-readme.yml heredoc (v0.3.4)
- Hotkey collision invisible to user (v0.3.4)
- No update-check rate limit → eventual GitHub 403 (v0.3.4)
- "Skip this version" wrong semantics (v0.3.4)
- GetTickCount wraparound at 49.7 days (v0.3.5)
- Asserts stripped by `python -O` (v0.3.5)
- Missing single-instance guard (v0.3.5)
- Ctrl+C left wakelock pinned (v0.3.5)
- HiDPI dialog blur (v0.3.5)
- F1–F24 hotkey support (v0.3.5)

---

## Where the full audit lives

The full audit reports — with file:line locations, repros, and per-finding
fix sketches — live at `/tmp/audit-{concurrency,security,win32,packaging,ux}.md`
on the maintainer's dev machine. They are NOT checked into this repo
because they include lots of internal references that aren't useful in
the public history. If you're contributing fixes and want the full text,
ping the maintainer.

## Reporting new issues

Please open a GitHub issue: https://github.com/calebohara/noidle.app/issues
For sensitive disclosures (e.g. an active exploit affecting downloaded
binaries), email `caleb.ohara@gmail.com` and include the word "noidle" in
the subject line.
