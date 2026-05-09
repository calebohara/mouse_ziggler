# Security & known issues

This file tracks audit findings that have NOT yet been fully fixed.
The full audit (5 specialist reviewers, 119 findings across concurrency,
security, Win32, packaging, UX) was run before v0.3.4. Across v0.3.4,
v0.3.5, v0.3.6, and post-v0.3.7 fixes, **43 critical/high audit findings have been resolved**.
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

No open HIGH-severity items. See CRITs above for remaining work.

---

## Resolved items

### HIGH-1: Symlink/junction attack on log directory writes
**Status:** ✅ FIXED in v0.3.8

`mkdir + open("a")` on `%LOCALAPPDATA%\noidle\` previously followed
Windows directory junctions. A pre-positioned local attacker who created
that path as a junction could turn noidle into an arbitrary file write
primitive targeting any path they could redirect to.

**Fixed:** Added `path.is_symlink()` guard immediately after `mkdir` in
two locations:
- `src/zig/logging_setup.py` — raises `RuntimeError` before
  `RotatingFileHandler` opens the log file
- `noidle.py` `_crash_log_path()` — raises `RuntimeError` before the
  crash log is written

If the directory is a symlink or junction, noidle now raises rather than
following the reparse point.

### HIGH-2: GitHub Actions pinned to mutable major-version tags
**Status:** ✅ FIXED in v0.3.8

All external GitHub Actions in `build.yml`, `lint.yml`, and
`update-readme.yml` were pinned to mutable major-version tags
(`@v4`, `@v5`, `@v2`, `@v3`). A compromised upstream maintainer could
re-point a tag at malicious code and ship a backdoored release through
this repo's own pipeline.

**Fixed:** All 5 external actions pinned to immutable commit SHAs,
verified by fetching from the GitHub API and dereferencing annotated tags:

| Action | SHA | Version |
|--------|-----|---------|
| `actions/checkout` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | v4 |
| `actions/setup-python` | `a26af69be951a213d495a4c3e4e4022e16d87065` | v5 |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | v4 |
| `softprops/action-gh-release` | `3bb12739c298aeb8a4eeaf626c5b8d85266b0e65` | v2 |
| `sigstore/cosign-installer` | `398d4b0eeef1380460a10c8013a76f728fb906ac` | v3 |

Each pin has a `# v<major>` inline comment for readability. Upgrade
process: when Dependabot bumps a major tag, update the SHA by re-fetching
from the GitHub API and verifying the type is `commit` (not a tag object).

---

## Resolved items

### Additional post-v0.3.7 reliability fixes (not original audit items)

The following bugs were found during a fresh agent-team review and fixed
on main, pending the next release:

- **`jiggler.start()` state corruption** — `_state.running = True` was set
  before `prevent_sleep()`, so a `WinError` left the jiggler stuck in a
  "running" state with no thread behind it. Fixed: flag now set after the
  Win32 call succeeds.
- **`HotkeyListener` registration timeout race** — `start()` silently
  returned success on a 5-second registration timeout, leaking the
  background thread. Fixed: raises `TimeoutError` if `_ready` is not set
  after the wait.
- **`packaging` missing from dependencies** — the `_parse_tuple` fallback
  in `updater.py` incorrectly treated `0.4.0-rc.1` as newer than `0.4.0`.
  `packaging` is now in `requirements.txt` and `pyproject.toml`; the
  correct `packaging.version.Version` path is always taken.
- **Smoke test `assert` stripped by `python -O`** — all bare `assert`
  statements in `_smoke()` converted to explicit `if/raise AssertionError`
  so the check survives optimization mode.
- **Version consistency check** — `_smoke()` now compares `zig.__version__`
  against `pyproject.toml` via `tomllib` (gated on file presence, so it
  runs from source and is skipped in PyInstaller bundles).

---

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

See git history (v0.3.4, v0.3.5, v0.3.6, v0.3.7 release notes). Highlights:
- Tkinter on background thread → subprocess (v0.3.4)
- Shell injection in update-readme.yml heredoc (v0.3.4)
- Hotkey collision invisible to user (v0.3.4)
- No update-check rate limit → eventual GitHub 403 (v0.3.4)
- "Skip this version" wrong semantics (v0.3.4)
- GetTickCount wraparound at 49.7 days (v0.3.5)
- Missing single-instance guard (v0.3.5)
- Ctrl+C left wakelock pinned (v0.3.5)
- HiDPI dialog blur (v0.3.5)
- F1–F24 hotkey support (v0.3.5)
- HIGH-1 symlink/junction guard on log directory writes (v0.3.8)
- HIGH-2 GitHub Actions SHA pinning across all workflow files (v0.3.8)

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
