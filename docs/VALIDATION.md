# Validation

Linux x86_64 / Python 3.12.14, 2026-11-08.

- 59 pytest cases pass, including rendering with Python socket/DNS operations
  blocked, JSON metadata rejection and compatibility, and import-safe example helpers.
- Wheel built with `--no-index --no-build-isolation`, then installed with
  `--no-index --no-deps --only-binary=:all:` into an isolated environment.
  The stdlib-only smoke test generates six SVG/Canvas outputs and verifies asset hashes.
- Browser audit is **unverified**: Chromium cannot create its process-singleton
  socket in this environment. No security settings were changed.
- Plotly WebGL, other platforms and a clean optional-extras wheelhouse installation
  are **unverified**. No CI pass is claimed.

Development dependencies are acquired online as wheels, separately from offline
runtime testing. Python socket monkeypatches and Canvas's network-denying CSP do
not constitute an OS network sandbox or prove every native-library path offline.
