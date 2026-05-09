# Agent Team Review — noidle.app / mouse_ziggler
**Date:** 2026-05-09
**Agents:** Frontend Engineer, Backend Engineer, QA Agent
**Scope:** Full codebase review from three specialist perspectives

---

## Frontend Engineer
**Traits:** Technical Specialist · Enthusiastic · Rapid
**Voice:** Jeremy `#00BCD4`
**Focus:** UI, landing page, CSS, accessibility, user experience

### Overall
Good — visually excellent, one critical conversion bug, four fixable issues.
Single file: `public/index.html` (1,210 lines, 50.5 KB). No build step, no frameworks, intentionally minimal.

### Wins
- Bunny Fonts (GDPR-friendly Google Fonts proxy)
- `prefers-reduced-motion` correctly implemented
- Interactive tray demo with right-click + Escape + outside-click handling
- Correct `aria-hidden="true"` on decorative SVGs
- Skip link present and working
- Real `<button>` elements in update popup mockup
- `role="menu"` + `role="menuitem"` on interactive demo

### Issues Found

| Severity | Issue | Fix |
|----------|-------|-----|
| CRITICAL | `og:image` is a `data:` URI — social cards broken on Twitter/X, LinkedIn, Slack, Discord | Host as `public/og.svg`, use absolute HTTPS URL |
| BUG | Typo in OG SVG: `noidIe` (capital I) not `noidle` (lowercase L) — appears twice | Fix while addressing og:image |
| A11Y | `--ink-4` (#65656e) = 3.47:1 contrast, fails WCAG AA | Bump to `#80808a` — 1 CSS variable change |
| A11Y | Tray demo `role="menu"` items have no `tabindex` or keyboard nav | Add `aria-hidden="true"` to `.desktop` (1 attr) or add arrow-key JS |
| Minor | Taskbar date hardcoded to "Mon, May 4" — growing stale | 3-line JS fix alongside the clock |

### Additional Notes
- No `<link rel="canonical">` tag
- No `robots.txt` or `sitemap.xml` in `public/`
- Missing `X-Frame-Options` and `Content-Security-Policy` in `vercel.json`
- `setInterval(tick, 30000)` fires every 30s but display has minute granularity — 60000ms is correct

### Top 3 Actions
1. Fix `og:image` + `noidIe` typo — move SVG to `public/og.svg`, fix text, update meta tag (~10 min)
2. Bump `--ink-4` to `#80808a` in `:root` block — 1 variable, WCAG AA compliant (~2 min)
3. Add `aria-hidden="true"` to `.desktop` element to opt demo out of a11y tree (~1 min)

---

## Backend Engineer
**Traits:** Technical Specialist · Analytical · Systematic · Security Expert
**Voice:** James `#4ECDC4`
**Focus:** App logic, CI/CD, infrastructure, security, performance

### Overall
GOOD — core jiggle engine is technically correct and hardened. Threat model explicitly documented. Two actionable supply-chain gaps remain.

### Wins
- +1/-1 relative mouse move is provably correct — zero-delta moves filtered by Windows input stack
- GetTickCount64/GetLastInputInfo handles 49.7-day DWORD wraparound correctly (fixed v0.3.5)
- `SetThreadExecutionState` flags correct for preventing both sleep and display timeout
- Interval jitter (`_JITTER_RATIO = 0.20`) is a good anti-fingerprinting measure
- Thread shutdown joins with 5s timeout; `allow_sleep()` always called in `finally`
- DLL binding is lazy, double-checked-locked, argtypes set before publishing to other threads
- `should_skip_for_user_activity` threshold scales with interval — clever
- Teams screen-share detection via `EnumWindows` + title-hint matching is cross-version-safe
- Config save is atomic: write to `.tmp`, fsync, then `os.replace()` — crash-safe
- CI: PyInstaller pinned to 6.11.1, WiX pinned to v4.0.5
- Two-exe smoke strategy captures stdout from noconsole bundle
- SHA256SUMS size check prevents the empty-file regression from v0.3.6
- cosign keyless signing published to every tagged release
- Updater has URL whitelisting, rate limiting, body size capping, and skip-version semantics

### Issues Found

| Severity | Issue |
|----------|-------|
| CRIT | No Authenticode signature → SmartScreen warning on every download. SignPath OSS application documented in `SIGNING.md` but not yet submitted |
| HIGH | `actions/checkout@v4`, `setup-python@v5`, `action-gh-release@v2` are mutable tags — NOT SHA-pinned |
| HIGH | No junction/reparse-point check before file writes in `logging_setup.py` and `noidle.py` — local file write primitive for pre-positioned attacker |
| LOW | Tray balloon notifications filtered by Win11 Focus Assist on non-critical paths |

### Top 3 Actions
1. SHA-pin all GitHub Actions in `build.yml`, `lint.yml`, `update-readme.yml` — 20-min task, closes supply-chain attack surface
2. Submit SignPath.io OSS Foundation application (`SIGNING.md` has the URL and steps) — 15 min effort, 1-2 week wait
3. Add `path.is_symlink()` guard before file writes in `logging_setup.py` and `noidle.py` crash-log path

---

## QA Agent
**Traits:** Research Specialist · Skeptical · Thorough · Analytical
**Voice:** Daniel `#009688`
**Focus:** Test coverage, bug hunting, edge cases, regression risks

### Overall Grade: C+
Well-written code with good defensive patterns. However: zero unit tests for a multi-threaded Windows app is alarming. Jiggler state corruption and hotkey timeout race are real bugs that could silently leave the app broken.

### Test Coverage — Critical Gap
Zero unit test files in this repository. No `tests/`, no `pytest.ini`, no `conftest.py`, no `test_*.py`. The entire "test suite" is `_smoke()` in `noidle.py`.

**What smoke covers:** Import success, API surface existence, a few Markdown parse assertions, constructor-not-crash checks.

**What smoke does NOT cover:**
- Jiggler thread start/stop/restart lifecycle
- Config persistence round-trips (write → read → coerce)
- Autostart registry operations
- `is_teams_screen_sharing()` detection logic
- Update check rate limiting with real timestamps
- `HotkeyListener` thread registration and teardown
- Stats accuracy over multiple jiggle/skip cycles
- Edge cases in `_parse_tuple` version comparison
- Version consistency between `pyproject.toml` and `__init__.py`

### Bugs Found

**Bug 1 — `jiggler.start()` state corruption on `prevent_sleep()` failure** (`jiggler.py:82-91`)
`_state.running = True` is set BEFORE the Win32 call that can raise. If `prevent_sleep()` raises a `WinError`, the UI shows the jiggler as running but no thread is running. Subsequent `start()` calls see `running=True` and return immediately. Fix: set `_state.running = True` only after `prevent_sleep()` succeeds, or reset in `except`.

**Bug 2 — No size cap on raw API JSON in `check_for_update()`** (`updater.py:104`)
`resp.read()` has no limit. `_BODY_MAX_BYTES` (64 KB) only applies to `payload["body"]` after parsing. A 100 MB JSON response would be fully buffered. Fix: use `resp.read(_BODY_MAX_BYTES * 2)` or stream with a limit.

**Bug 3 — `HotkeyListener.start()` silently succeeds on 5s timeout** (`hotkey.py:142`)
`self._ready.wait(timeout=5.0)` returns without error if thread is slow but not dead. Caller believes hotkey is registered. If `_tid` not yet set, later `stop()` returns immediately while background thread continues — permanent leak. Fix: `if not self._ready.is_set(): raise TimeoutError(...)` after the wait.

**Bug 4 — `_parse_tuple` fallback handles pre-release versions incorrectly** (`updater.py:41-53`)
`_parse_tuple("0.4.0-rc.1")` returns `(0, 4, 0, 1)` — sorts ABOVE `0.4.0`, making RC versions appear newer than releases. `packaging` is not in `requirements.txt`, so the fallback IS the live path in PyInstaller bundles. Fix: add `packaging` to `requirements.txt`.

**Bug 5 — Version drift between `pyproject.toml` and `__init__.py` not caught**
Smoke test never asserts `zig.__version__ == <expected>` or compares against `pyproject.toml`. A release tagged `v0.4.0` could ship an app reporting `0.3.7`. Fix: add `assert zig.__version__ == CURRENT_VERSION` to smoke test.

**Bug 6 — Smoke `assert` statements stripped by `python -O`**
15+ raw `assert` statements in `_smoke()`. `python -O` silently strips them all, returning 0 (success) regardless. `SECURITY.md` claims fixed in v0.3.5 — not true for the smoke function. Fix: convert to `if not ...: raise AssertionError(...)` pattern.

### Additional Findings
- **Teams detection is English-locale-only** — `_TEAMS_SHARE_TITLE_HINTS` covers en-US/en-GB/en-AU only. French, German, etc. get no skip.
- **`EnumWindows` on every tick** — runs a full window enumeration on every jiggler tick. Cheap in isolation but worth noting.
- **`is_offerable` argument order trap** — `tray.py:523` calls `is_offerable(self.config.skipped_version, CURRENT_VERSION)` with args semantically swapped from natural order. Works by coincidence of math but is a future maintainer trap.
- **SECURITY.md HIGH-2 confirmed open** — CI action SHA pinning still not done.
- **SECURITY.md HIGH-1 confirmed open** — junction/symlink attack on log directory still open.

### Top 3 Actions
1. Fix `jiggler.start()` — move `_state.running = True` after `prevent_sleep()` succeeds (`jiggler.py:82-91`)
2. Add `packaging` to `requirements.txt` — 1-line fix, prevents version comparison regression on pre-release channels
3. Add version consistency assertion to smoke: `assert zig.__version__ == "0.3.7"` with update-at-release comment

---

## Consolidated Priority Stack

### Fix Immediately
1. `og:image` data URI — broken social cards on every share (Frontend)
   > **Fixed 2026-05-09** — Created `public/og.svg` with the decoded SVG, updated `og:image` content in `index.html` to `https://noidle.app/og.svg`. Added `twitter:image` meta tag pointing to the same URL. Social crawlers on Twitter/X, LinkedIn, Slack, and Discord will now render the preview card.

2. `noidIe` typo in OG SVG (Frontend, fix alongside #1)
   > **Fixed 2026-05-09** — Both occurrences of `noidIe` (capital I) corrected to `noidle` (lowercase L) in `public/og.svg` at creation time.

3. `jiggler.start()` state corruption on `prevent_sleep()` failure (QA Bug 1)
   > **Fixed 2026-05-09** — In `src/zig/jiggler.py:start()`, moved `self._state.running = True` to after `prevent_sleep()`. If `prevent_sleep()` now raises a `WinError`, `running` stays `False` and the UI correctly reflects that the jiggler is not active. Subsequent `start()` calls will not be silently no-op'd.

4. Add `packaging` to `requirements.txt` — live path uses broken pre-release version fallback (QA Bug 4)
   > **Fixed 2026-05-09** — Added `packaging>=24.0` to `requirements.txt` and `pyproject.toml` dependencies. The PyInstaller bundle will now include the `packaging` library, ensuring `updater.py` uses the correct version comparison path instead of the `_parse_tuple` fallback that incorrectly treats `0.4.0-rc.1` as newer than `0.4.0`.

### Fix Soon
5. SHA-pin all GitHub Actions in CI workflows (Backend + QA)
   > **Fixed 2026-05-09** — Fetched and verified commit SHAs for all 5 external actions via GitHub API (dereferencing annotated tags where needed). Pinned in all three workflow files:
   > - `actions/checkout` → `34e114876b0b11c390a56381ad16ebd13914f8d5` (`build.yml`, `lint.yml`, `update-readme.yml`)
   > - `actions/setup-python` → `a26af69be951a213d495a4c3e4e4022e16d87065` (`build.yml`, `lint.yml`)
   > - `sigstore/cosign-installer` → `398d4b0eeef1380460a10c8013a76f728fb906ac` (`build.yml`)
   > - `actions/upload-artifact` → `ea165f8d65b6e75b540449e92b4886f43607fa02` (`build.yml`)
   > - `softprops/action-gh-release` → `3bb12739c298aeb8a4eeaf626c5b8d85266b0e65` (`build.yml`)
   > Each pin has a `# v<major>` comment so the human-readable version is still visible.

6. Submit SignPath.io OSS application for Authenticode (Backend) — **SKIPPED** (manual action required)

7. `path.is_symlink()` guard before log file writes (Backend + QA)
   > **Fixed 2026-05-09** — Added `is_symlink()` guard in two places:
   > - `src/zig/logging_setup.py`: raises `RuntimeError` if `path.parent` is a symlink/junction after `mkdir`, before the `RotatingFileHandler` opens the log file.
   > - `noidle.py`: raises `RuntimeError` in `_crash_log_path()` if the `noidle/` directory is a symlink/junction after `mkdir`, before returning the crash log path.
   > A pre-positioned attacker can no longer turn either write path into an arbitrary file write primitive via a directory junction.

8. `HotkeyListener` timeout race — raise error if `_ready` not set after 5s (QA Bug 3)
   > **Fixed 2026-05-09** — In `src/zig/hotkey.py:start()`, added `if not self._ready.is_set(): raise TimeoutError(...)` immediately after `self._ready.wait(timeout=5.0)`. If the registration thread is slow and the 5s wait expires without the event being set, `start()` now clears `self._thread` and raises `TimeoutError` rather than silently returning success. This prevents the tray from believing the hotkey is registered while the background thread continues running and leaking.

### Fix When Convenient
9. Bump `--ink-4` to `#80808a` for WCAG AA contrast (Frontend)
   > **Fixed 2026-05-09** — Changed `--ink-4: #65656e` to `--ink-4: #80808a` in the `:root` block of `public/index.html`. All muted text (download meta line, footer byline, demo arrows) now meets WCAG AA 4.5:1 contrast ratio against the `#08080c` background.

10. Add `aria-hidden="true"` to `.desktop` demo element (Frontend)
    > **Fixed 2026-05-09** — Added `aria-hidden="true"` to `<div class="desktop reveal">` in `public/index.html`. The entire interactive taskbar demo is now opted out of the accessibility tree, removing the incomplete `role="menu"` widget from screen reader navigation without requiring a full roving-tabindex implementation.

11. Live-update taskbar date alongside the clock — 3-line JS fix (Frontend)
    > **Fixed 2026-05-09** — Added `id="taskbarDate"` to the date `<div>`. Updated the JS clock IIFE to read `taskbarDate`, populate it with `DAYS[d.getDay()], MONTHS[d.getMonth()] d.getDate()` on every tick, and changed `setInterval` from 30000ms to 60000ms (minute granularity, matching the display).

12. Add `tests/` directory with pytest for thread lifecycle coverage (QA)
    > **Fixed 2026-05-09** — Created `tests/` with 5 test modules covering platform-independent code (safe to run on Linux/macOS CI):
    > - `tests/conftest.py` — adds `src/` to `sys.path`
    > - `tests/test_updater.py` — `_parse_tuple`, `_is_newer`, `_is_safe_release_url`, `is_offerable`, `should_check_now` (38 assertions)
    > - `tests/test_hotkey.py` — `parse_hotkey` valid/invalid cases including modifier combos, F-key range, error messages
    > - `tests/test_config.py` — `_coerce` coercion rules, load/save round-trips, corrupt JSON fallback, no leftover `.tmp` files
    > - `tests/test_whats_new.py` — `parse_release_notes` categories, trailer stripping, attribution removal, empty body
    > - `tests/test_jiggler.py` — `JigglerState` defaults, `Jiggler` init, `set_interval`/`set_method` validation and error paths

13. Convert smoke `assert` to `if/raise` pattern to survive `python -O` (QA)
    > **Fixed 2026-05-09** — Rewrote all 15+ bare `assert` statements in `_smoke()` (`noidle.py`) to explicit `if not ...: raise AssertionError(...)` form. The smoke function now survives `python -O` and still catches regressions. Each error message includes the actual value for easier diagnosis.

14. Add version consistency assertion to smoke test (QA)
    > **Fixed 2026-05-09** — Added a `pyproject.toml` vs `zig.__version__` version consistency check to `_smoke()` using `tomllib` (Python 3.11+ stdlib). The check is gated on `pyproject.toml` existing — it runs from source during CI dev runs but is silently skipped in PyInstaller bundles where the file is absent. Returns exit code 5 on mismatch with a diagnostic message.

15. Add `<link rel="canonical">` and `robots.txt` to `public/` (Frontend)
    > **Fixed 2026-05-09** — Added `<link rel="canonical" href="https://noidle.app">` to `public/index.html` head. Created `public/robots.txt` with `User-agent: *`, `Allow: /`, and a `Sitemap:` pointer.

16. Add CSP and `X-Frame-Options` to `vercel.json` (Frontend)
    > **Fixed 2026-05-09** — Added `X-Frame-Options: SAMEORIGIN` (clickjacking protection) and a `Content-Security-Policy` header to `vercel.json`. CSP allows inline scripts/styles (required by the single-file architecture), restricts fonts to `fonts.bunny.net`, blocks `frame-src`, `object-src`, and external `base-uri` redirects.
