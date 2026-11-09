# Browser audits

These checkout-only development tools complement the Python/offline-wheel tests.
They do not change library runtime dependencies, install a browser, use your signed-in
profile, or certify every browser/OS/GPU combination. Each run uses a fresh profile.
Run from the repository root after installing the project with its `[dev]` extra.
Playwright 1.48 or later is needed for WebSocket interception; third-party Python
dependencies must be acquired as wheels. The browser is separate installed software.

## Run

```sh
python -m tools.verify_browser
python -m tools.verify_ecef_browser
python -m tools.verify_plotly_browser
```

The tools generate representative self-contained HTML themselves; running both
full example galleries first is unnecessary. Canvas uses only the core renderer;
Plotly uses the optional interactive dependencies. Importing the tools does not
generate files, load optional plotting/browser packages, or launch a browser.

The default output directories are `artifacts/earth`, `artifacts/ecef`, and
`artifacts/browser/plotly`. They are ignored by Git. All tools accept
`--output-dir PATH`, `--headed`, `--browser-executable PATH`, and repeated
`--browser-arg=--flag`. The two Canvas tools also accept `--html PATH` to test
an existing output instead of generating one. The ECEF audit requires multiple
sample times and visibly changing paths. Plotly accepts `--timeout-ms`.

## Select an installed browser

Selection is deterministic: an explicit CLI path wins over
`OFFLINE_EARTH_BROWSER_EXECUTABLE`, followed by known system/user install locations,
PATH, then Playwright's already installed Chromium binary. Discovery checks Chrome,
Chromium and Edge locations on Linux, macOS and Windows. It does not run an installer
or download missing binaries. Firefox and Safari are not supported by these Chromium
audits. Custom locations should use an explicit executable path, not an application
directory or shell command. Paths containing spaces must be quoted.

Examples (adapt the path to your actual installation):

```sh
# Linux
python -m tools.verify_ecef_browser --browser-executable /usr/bin/chromium
# macOS
python -m tools.verify_ecef_browser --browser-executable "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

```powershell
# Windows PowerShell
python -m tools.verify_ecef_browser --browser-executable "C:\Program Files\Google\Chrome\Application\chrome.exe"
$env:OFFLINE_EARTH_BROWSER_EXECUTABLE = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
python -m tools.verify_plotly_browser
```

An invalid explicit path fails instead of silently selecting another browser.
A launch failure is reported without trying a different browser or disabling its
sandbox. The helper keeps Chromium sandboxing enabled. Extra arguments are explicit
opt-ins for an environment you control; no Linux-specific or sandbox-disabling
arguments are added by our code. Playwright itself supplies its normal automation
arguments, which can change by version. A system browser may not match Playwright's
tested revision; retain both versions with the run evidence.

## What is checked

- Canvas: actual nonblank pixels, three distinct layer views, drag changing the
  globe, and no continued rotation after releasing the pointer. The ECEF audit
  additionally checks time scrubbing changes pixels and the clock, playback
  advances, and Pause stops it.
- Plotly: generated ECEF trajectory coordinates match the graph, a WebGL context
  has a nonzero drawing buffer and is not lost, the scene has varied pixels, and
  hiding the trajectories visibly changes the canvas. Fixed scene ranges prevent
  automatic resizing from being mistaken for trajectory evidence. Screenshots
  include the scene with and without trajectories and the complete page.
- Both: uncaught JavaScript exceptions, console errors, attempted HTTP requests,
  WebSockets, common networking APIs, and CSP-blocked resource attempts are errors.
  HTTP/WebSocket routes are blocked before loading, service workers are blocked,
  and instrumentation is inserted before the application's scripts. Embedded data
  and blob resources remain usable. Attempts count as failures even when blocked.

HTML bytes are loaded with `page.set_content`; no HTTP server is needed. This
tests the embedded scripts/DOM, not browser-specific `file://` navigation rules.
Isolation is scoped to the page/context. It is not an OS firewall or certification
that the browser executable makes no background traffic. It does not test arbitrary
malicious HTML; use it for the trusted generated outputs. Retain the HTML hash,
browser executable/version, dependency versions, options, JSON report and screenshots
for a reproducible result. Inspect the screenshots as well as the machine checks.

## Failures and test coverage

A failed audit returns a nonzero process exit status and writes a failed JSON report,
including the original exception and any captured diagnostics. Failure screenshots
are saved when a page exists. A browser launch failure produces no rendering evidence;
empty network/error arrays in that report do **not** mean the page passed.

If the OS denies Chromium's socket/process setup, the audit cannot verify Canvas
interactions or WebGL output there. Run the same commands in an environment that
supports browser execution rather than treating a Python test pass as a browser pass.
Do not silently relax security settings or install a different browser.

The ordinary pytest suite tests discovery with mocked Linux/macOS/Windows paths,
explicit-config failures, network/error guard wiring, failed-report behavior and
pixel-evidence rejection. Those tests do not launch or certify browsers. Actual
macOS/Windows launches, graphics hardware/drivers and browser versions each need
their own audit runs. Browser validation is independent of licensing and release.
