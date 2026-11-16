# Platform Limits — Genie v1.2.0-rc3

Honest statement of what was and was not verified for this candidate.
Anything listed NOT VERIFIED was not tested; do not claim it.

## Verified (Linux, headless Chromium, this acceptance run)

- Linux (Python 3.12.3) clean install, seven applications, Decision Recall,
  signed receipts, role enforcement, import/export, spend-ledger fail-closed
  behavior. See the acceptance report for per-gate logs.
- Desktop 1280px and mobile 390px browser gates (headless Chromium via
  Playwright), including immediate STOP→Resume, repeated STOP, delayed stale
  operations, concurrent STOP+Resume+STOP in the same tick (6/6, second
  STOP survives), fresh-server seeding, and accepted-state preservation.
- Node projection suite.
- Corrected first-run dogfood: 33 PASS / 0 FAIL desktop, 8 PASS / 0 FAIL
  mobile, zero console errors in either viewport.

## NOT VERIFIED

- **iOS Safari:** not tested (no iOS device or simulator in this environment).
- **macOS:** not tested (no macOS host in this environment).
- **Windows:** not tested (no Windows host in this environment).
- **OS-identity security:** not tested. Same-OS-user processes with access to
  the state directory can read the signing keys and SQLite database; the
  boundary holds only between separate OS users.
- **Chromium-binary browser tests:** the selenium-driven browser suites
  require a system Chromium binary (`/usr/bin/chromium` or
  `/usr/bin/chromedriver`). On the qualification host neither exists, so
  11 suite tests error with `ValueError: The path is not a valid file:
  /usr/bin/chromedriver` and 1 fails on the missing binary; the same
  checks pass in the real headless Chromium (Playwright) used by the
  browser gates. See the acceptance report for the per-error evidence.
- **Physical robot hardware:** Robotics Studio is simulation only. No hardware
  validation exists or is claimed.

## Environmental limitations of the qualification host

- This sandbox cannot reach Google Fonts / chart.js / tailwind CDNs.
  Measured on the merged tree, the corrected first-run dogfood showed
  zero console errors on desktop and mobile (the Robotics and Ratchet
  pages no longer depend on those CDNs); a console error naming one of
  those hosts on another page would be environmental, not a product
  failure.
- The full Python suite runs in ~160 s on the shared 1.5-CPU
  qualification host. No test-server load failures appeared in the final
  re-runs (unlike R7.2); see the acceptance report for the per-error
  evidence.
