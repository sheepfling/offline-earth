"""Page-level offline/error guard shared by the optional browser audits.

This is test instrumentation, not an OS firewall. HTTP and WebSocket routes are
blocked before loading the HTML; API calls and CSP violations are also recorded
so a denied request cannot accidentally count as a successful offline render.
"""
from __future__ import annotations

import re
from typing import Any, Final


NETWORK_GUARD_SCRIPT: Final[str] = r"""<script>
(() => {
  const attempts = [];
  window.__offlineEarthAudit = {attempts};
  const local = url => /^(data:|blob:|about:blank$)/i.test(String(url));
  const record = (kind, url) => attempts.push({kind, url: String(url)});
  const block = (kind, url) => {
    if (local(url)) return false;
    record(kind, url);
    return true;
  };
  document.addEventListener('securitypolicyviolation', event => {
    if (event.blockedURI && !['inline', 'eval'].includes(event.blockedURI))
      record('csp', event.blockedURI);
  });
  const fetchOriginal = window.fetch;
  window.fetch = function(input, ...args) {
    const url = input instanceof Request ? input.url : input;
    if (block('fetch', url)) return Promise.reject(new TypeError('Offline audit blocked fetch'));
    return fetchOriginal.call(this, input, ...args);
  };
  const openOriginal = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url, ...args) {
    if (block('xhr', url)) throw new DOMException('Offline audit blocked XHR', 'NetworkError');
    return openOriginal.call(this, method, url, ...args);
  };
  if (navigator.sendBeacon) navigator.sendBeacon = function(url) {
    record('beacon', url); return false;
  };
  for (const name of ['WebSocket', 'EventSource']) {
    if (!window[name]) continue;
    const Original = window[name];
    window[name] = class extends Original {
      constructor(url) {
        record(name.toLowerCase(), url);
        throw new DOMException('Offline audit blocked ' + name, 'NetworkError');
      }
    };
  }
})();
</script>"""


class OfflinePageAudit:
    """Capture rendering failures and attempted external traffic in one context."""

    def __init__(self, context: Any) -> None:
        self.network_attempts: list[dict[str, str]] = []
        self.script_errors: list[str] = []
        self.console_errors: list[str] = []
        context.route("**/*", self._block_request)
        # Playwright >=1.48: workers and nested frames cannot bypass this route.
        context.route_web_socket("**/*", self._block_websocket)

    def _block_request(self, route: Any) -> None:
        self.network_attempts.append({"kind": "request", "url": route.request.url})
        route.abort()

    def _block_websocket(self, route: Any) -> None:
        self.network_attempts.append({"kind": "websocket", "url": route.url})
        route.close()

    def attach(self, page: Any) -> None:
        page.on("pageerror", lambda error: self.script_errors.append(str(error)))
        page.on("console", self._console)
        page.on("crash", lambda _: self.script_errors.append("Browser page crashed"))

    def _console(self, message: Any) -> None:
        if message.type == "error":
            self.console_errors.append(message.text)

    def set_content(self, page: Any, html: str, *, timeout: int = 30000) -> None:
        """Install instrumentation before document scripts, including its CSP."""
        match = re.search(r"<head(?:\s[^>]*)?>", html, flags=re.IGNORECASE)
        if match is None:
            raise ValueError("Browser audit input must contain an HTML head element")
        instrumented = html[:match.end()] + NETWORK_GUARD_SCRIPT + html[match.end():]
        page.set_content(instrumented, wait_until="domcontentloaded", timeout=timeout)

    def snapshot(self, page: Any) -> dict[str, list[Any]]:
        injected = page.evaluate("""() => {
            if (!window.__offlineEarthAudit) throw Error('Offline instrumentation did not initialize');
            return window.__offlineEarthAudit.attempts;
        }""")
        return {
            "network_attempts": [*self.network_attempts, *injected],
            "script_errors": list(self.script_errors),
            "console_errors": list(self.console_errors),
        }

    def assert_clean(self, page: Any) -> None:
        result = self.snapshot(page)
        if any(result.values()):
            raise AssertionError(f"Browser audit detected errors or external requests: {result}")
