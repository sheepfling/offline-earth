# Validation of 0.3.1

Run on Linux x86_64 / Python 3.12.14, 2026-11-07.

- 34 pytest cases passed, including actual PNG/SVG/Canvas/Plotly generation while Python
  socket and DNS operations were monkeypatched to fail. Includes eight new Canvas option tests.
- Built `trenton_offline_maps-0.3.1-py3-none-any.whl` with `--no-index --no-build-isolation`.
- Installed the wheel into a fresh virtual environment using `--no-index --no-deps
  --only-binary=:all:`. From outside the checkout, the stdlib-only smoke script generated
  six core outputs (three modes × SVG/Canvas), validated 177 countries and asset hashes,
  with Python socket/DNS calls blocked.
- Wheel includes both assets, manifest/provenance and upstream license texts.
- Browser regression attempted, but **not run successfully**: Chromium cannot create its
  process-singleton socket in this execution environment (`Operation not permitted`).
  No security settings were changed. The archived v0.3.0 browser report is historical and
  must not be represented as a successful browser check for v0.3.1.
- Plotly browser/WebGL, other OS/Python combinations, and clean optional-extras wheelhouse
  installation are not certified. No CI run is claimed.

Dependencies were acquired online as wheels for the development environment. This does not
invalidate offline runtime testing; it also does not constitute an offline wheelhouse delivery.
Python monkeypatch tests do not prove absence of every conceivable native-library network call.
Canvas's deny-network CSP is defense in depth, not a general OS network sandbox.

## Ingestion regression update (2026-11-08)

Explicitly conflicting JSON frame, spatial units and time units are now rejected
at document and trajectory levels, including single-trajectory input. Missing
metadata preserves the legacy ECEF/metres/seconds defaults. The full suite now
has 55 passing cases, including metadata round-trip, 18 conflicting/null cases,
and two legacy compatibility cases. Browser and optional wheelhouse claims
remain unchanged and unverified.
