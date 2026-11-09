"""Guard and report contracts. Browser behavior is a separate opt-in audit."""
import json
from types import SimpleNamespace

import pytest

from tools.browser_audit import NETWORK_GUARD_SCRIPT, OfflinePageAudit
from tools import canvas_browser_audit


class FakeContext:
    def route(self, pattern, handler):
        assert pattern == '**/*'
        self.http = handler

    def route_web_socket(self, pattern, handler):
        assert pattern == '**/*'
        self.websocket = handler


class FakePage:
    def __init__(self):
        self.events = {}
        self.injected = []

    def on(self, name, handler):
        self.events[name] = handler

    def evaluate(self, _):
        return self.injected

    def set_content(self, html, **kwargs):
        self.html = html
        self.options = kwargs


def test_network_and_error_observers_block_and_fail():
    context, page = FakeContext(), FakePage()
    audit = OfflinePageAudit(context)
    audit.attach(page)
    calls = []
    context.http(SimpleNamespace(request=SimpleNamespace(url='https://example.invalid/a'),
                                 abort=lambda: calls.append('abort')))
    context.websocket(SimpleNamespace(url='wss://example.invalid/socket', close=lambda: calls.append('close')))
    page.events['pageerror'](RuntimeError('Uncaught failure'))
    page.events['console'](SimpleNamespace(type='error', text='WebGL failed'))
    page.events['console'](SimpleNamespace(type='warning', text='nonfatal warning'))
    page.events['crash'](page)
    page.injected = [{'kind': 'csp', 'url': 'https://example.invalid/blocked.png'}]
    snapshot = audit.snapshot(page)
    assert calls == ['abort', 'close']
    assert [attempt['kind'] for attempt in snapshot['network_attempts']] == ['request', 'websocket', 'csp']
    assert snapshot['script_errors'] == ['Uncaught failure', 'Browser page crashed']
    assert snapshot['console_errors'] == ['WebGL failed']
    with pytest.raises(AssertionError, match='external requests'):
        audit.assert_clean(page)


def test_guards_precede_csp_and_application_scripts():
    context, page = FakeContext(), FakePage()
    audit = OfflinePageAudit(context)
    html = '<!doctype html><HTML><HEAD lang="en"><meta http-equiv="Content-Security-Policy"><script>application()</script></HEAD></HTML>'
    audit.set_content(page, html, timeout=1234)
    assert page.html.index(NETWORK_GUARD_SCRIPT) < page.html.index('<meta') < page.html.index('application()')
    assert page.options == {'wait_until': 'domcontentloaded', 'timeout': 1234}
    audit.assert_clean(page)
    with pytest.raises(ValueError, match='head element'):
        audit.set_content(page, 'not a document')


def test_canvas_launch_failure_writes_failed_report(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise RuntimeError('Injected launch failure')
    monkeypatch.setattr(canvas_browser_audit, 'launch_browser', fail)
    monkeypatch.setattr(canvas_browser_audit, 'resolve_browser_executable', lambda *a: '/existing/chrome')
    paths = tuple(tmp_path / p for p in ('scene.html', 'scene.png', 'report.json'))
    assert canvas_browser_audit.run_canvas_audit([], ecef=True, paths=paths) == 1
    report = json.loads(paths[2].read_text(encoding='utf-8'))
    assert report['passed'] is False
    assert 'Injected launch failure' in report['error']
    assert len(report['html_sha256']) == 64
    assert paths[0].is_file()
    assert not paths[1].exists()


@pytest.mark.parametrize('pixels', [
    {'width': 0, 'height': 100, 'colors': 200},
    {'width': 680, 'height': 680, 'colors': 1},
])
def test_canvas_blank_pixel_evidence_fails(pixels):
    page = SimpleNamespace(evaluate=lambda _: pixels)
    with pytest.raises(AssertionError, match='rendered globe'):
        canvas_browser_audit.settled_pixels(page)


@pytest.mark.parametrize('snapshot_fails', [False, True])
def test_canvas_final_capture_cannot_leave_false_pass(monkeypatch, tmp_path, snapshot_fails):
    from contextlib import nullcontext
    import playwright.sync_api
    page = SimpleNamespace(is_closed=lambda: False, screenshot=lambda **kw: None)
    context = SimpleNamespace(new_page=lambda: page)
    browser = SimpleNamespace(version='test', new_context=lambda **kw: context, close=lambda: None)
    class Audit:
        def __init__(self, context): pass
        def attach(self, page): pass
        def set_content(self, page, html): pass
        def assert_clean(self, page): pass
        def snapshot(self, page):
            if snapshot_fails:
                raise RuntimeError('Page disappeared')
            return {'network_attempts': [{'kind': 'request', 'url': 'https://example.invalid/late'}],
                    'script_errors': [], 'console_errors': []}
    monkeypatch.setattr(playwright.sync_api, 'sync_playwright', lambda: nullcontext(object()))
    monkeypatch.setattr(canvas_browser_audit, 'launch_browser', lambda *a: browser)
    monkeypatch.setattr(canvas_browser_audit, 'resolve_browser_executable', lambda *a: '/test/chrome')
    monkeypatch.setattr(canvas_browser_audit, 'OfflinePageAudit', Audit)
    monkeypatch.setattr(canvas_browser_audit, 'exercise_canvas', lambda *a, **kw: {})
    paths = tuple(tmp_path / p for p in ('scene.html', 'scene.png', 'report.json'))
    assert canvas_browser_audit.run_canvas_audit([], ecef=True, paths=paths) == 1
    report = json.loads(paths[2].read_text(encoding='utf-8'))
    assert report['passed'] is False
    assert report.get('capture_error') if snapshot_fails else report['network_attempts']


def test_javascript_guard_rejects_network_apis_before_original_calls():
    # Optional JavaScript engine check only. This does not emulate browser rendering.
    import shutil
    import subprocess
    node = shutil.which('node')
    if node is None:
        pytest.skip('Optional JavaScript engine is not installed')
    setup = r'''
const originalCalls = [];
globalThis.window = globalThis;
const handlers = {};
globalThis.document = {addEventListener: (type, fn) => handlers[type] = fn};
globalThis.Request = class {constructor(url) {this.url = url}};
globalThis.fetch = async url => {originalCalls.push(['fetch', url]); return 'local'};
globalThis.XMLHttpRequest = class {open(method, url) {originalCalls.push(['xhr', url])}};
Object.defineProperty(globalThis, 'navigator', {value: {sendBeacon: () => {throw Error('Leaked beacon')}}, configurable: true});
globalThis.WebSocket = class {constructor() {throw Error('Leaked socket')}};
globalThis.EventSource = class {constructor() {throw Error('Leaked eventsource')}};
'''
    exercise = r'''
(async () => {
  await fetch('https://example.invalid/fetch').catch(() => {});
  await fetch(new Request('https://example.invalid/request')).catch(() => {});
  await fetch('data:text/plain,local');
  for (const f of [() => new XMLHttpRequest().open('GET', 'https://example.invalid/xhr'),
                   () => new WebSocket('wss://example.invalid/ws'),
                   () => new EventSource('https://example.invalid/events')]) {try {f()} catch (_) {}}
  navigator.sendBeacon('https://example.invalid/beacon');
  handlers.securitypolicyviolation({blockedURI:'https://example.invalid/image'});
  handlers.securitypolicyviolation({blockedURI:'inline'});
  console.log(JSON.stringify({attempts: window.__offlineEarthAudit.attempts, originalCalls}));
})().catch(e => {console.error(e); process.exitCode = 1});
'''
    script = setup + NETWORK_GUARD_SCRIPT.removeprefix('<script>').removesuffix('</script>') + exercise
    run = subprocess.run([node, '-e', script], capture_output=True, text=True, encoding='utf-8', check=True)
    result = json.loads(run.stdout)
    assert [item['kind'] for item in result['attempts']] == ['fetch', 'fetch', 'xhr', 'websocket', 'eventsource', 'beacon', 'csp']
    assert result['originalCalls'] == [['fetch', 'data:text/plain,local']]
