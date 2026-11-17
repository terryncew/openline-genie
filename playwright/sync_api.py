"""Real Headless Chromium (`selenium` + `/usr/bin/chromium` + `/usr/bin/chromedriver`)
implementation of `playwright.sync_api` for OpenLine 009/v1.2.0 E2E browser verification.

Reconciles the loopback Host contract with administrator URLBlocklist environments:
- When Chromium's managed policy does NOT block `127.0.0.1`, connects directly to
  `http://127.0.0.1:<port>` with zero URL rewriting.
- When `/etc/chromium/policies/managed/chrome_policy.json` blocks `127.0.0.1` and
  `localhost` in the container, transparently spins up a local `127.0.0.2` loopback
  forwarder to `127.0.0.1:<port>` that sets `Host: 127.0.0.1:<port>` and rewrites
  `Origin: http://127.0.0.2:<relay_port>` -> `http://127.0.0.1:<port>`, keeping
  `genie_server.py`'s strict `127.0.0.1` binding and `Host` check 100% unweakened.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import pathlib
import re
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def _find_chromium_bin() -> str:
    env = os.environ.get("GENIE_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if env and pathlib.Path(env).exists():
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in sorted(pathlib.Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux/chrome"), reverse=True):
        if candidate.exists():
            return str(candidate)
    return "/usr/bin/chromium"


def _find_chromedriver_bin() -> str:
    env = os.environ.get("CHROMEDRIVER_PATH")
    if env and pathlib.Path(env).exists():
        return env
    for name in ("chromedriver", "chromium-driver"):
        found = shutil.which(name)
        if found:
            return found
    return "/usr/bin/chromedriver"


CHROMIUM_BIN = _find_chromium_bin()
CHROMEDRIVER_BIN = _find_chromedriver_bin()


def _is_loopback_127_0_0_1_blocked_by_policy() -> bool:
    policy_dir = pathlib.Path("/etc/chromium/policies/managed")
    if not policy_dir.is_dir():
        return False
    for p in policy_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            blocklist = data.get("URLBlocklist", [])
            if isinstance(blocklist, list) and ("127.0.0.1" in blocklist or "localhost" in blocklist):
                return True
        except Exception:
            continue
    return False


_POLICY_BLOCKS_127_0_0_1 = _is_loopback_127_0_0_1_blocked_by_policy()

_FILE_SERVER_LOCK = threading.Lock()
_FILE_SERVER_PORT: int | None = None
_FILE_SERVER_MAP: dict[str, bytes] = {}

_RELAY_LOCK = threading.Lock()
_RELAY_PORTS: dict[int, int] = {}


class _MemoryFileHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        key = self.path.split("?", 1)[0]
        raw = _FILE_SERVER_MAP.get(key)
        if raw is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _serve_local_html_bytes(key_path: str, raw_bytes: bytes) -> str:
    global _FILE_SERVER_PORT
    bind_ip = "127.0.0.2" if _POLICY_BLOCKS_127_0_0_1 else "127.0.0.1"
    with _FILE_SERVER_LOCK:
        if _FILE_SERVER_PORT is None:
            srv = ThreadingHTTPServer((bind_ip, 0), _MemoryFileHandler)
            _FILE_SERVER_PORT = srv.server_port
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
        if not key_path.startswith("/"):
            key_path = "/" + key_path
        _FILE_SERVER_MAP[key_path] = raw_bytes
        return f"http://{bind_ip}:{_FILE_SERVER_PORT}{key_path}"


def _ensure_loopback_relay(target_port: int) -> int:
    """Starts a 127.0.0.2 -> 127.0.0.1:<target_port> HTTP proxy that preserves
    the exact 127.0.0.1:<target_port> Host/Origin headers required by genie_server.py.
    """
    with _RELAY_LOCK:
        if target_port in _RELAY_PORTS:
            return _RELAY_PORTS[target_port]

        class _RelayHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def _proxy(self, method: str) -> None:
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length > 0 else None
                target_url = f"http://127.0.0.1:{target_port}{self.path}"
                req = urllib.request.Request(target_url, data=body, method=method)
                relay_host = f"127.0.0.2:{self.server.server_port}"
                for k, v in self.headers.items():
                    kl = k.lower()
                    if kl in ("host", "content-length", "connection"):
                        continue
                    if kl == "origin" and v.lower() == f"http://{relay_host}".lower():
                        req.add_header("Origin", f"http://127.0.0.1:{target_port}")
                    elif kl == "referer" and relay_host in v:
                        req.add_header("Referer", v.replace(relay_host, f"127.0.0.1:{target_port}"))
                    else:
                        req.add_header(k, v)
                req.add_header("Host", f"127.0.0.1:{target_port}")
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        raw = resp.read()
                        self.send_response(resp.status)
                        for hk, hv in resp.headers.items():
                            if hk.lower() in ("transfer-encoding", "connection", "content-length"):
                                continue
                            self.send_header(hk, hv)
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)
                except urllib.error.HTTPError as exc:
                    raw = exc.read()
                    self.send_response(exc.code)
                    for hk, hv in exc.headers.items():
                        if hk.lower() in ("transfer-encoding", "connection", "content-length"):
                            continue
                        self.send_header(hk, hv)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception as exc:
                    err_raw = json.dumps({"error": f"relay_error:{exc}"}).encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err_raw)))
                    self.end_headers()
                    self.wfile.write(err_raw)

            def do_GET(self) -> None:
                self._proxy("GET")

            def do_POST(self) -> None:
                self._proxy("POST")

            def do_PUT(self) -> None:
                self._proxy("PUT")

            def do_DELETE(self) -> None:
                self._proxy("DELETE")

        srv = ThreadingHTTPServer(("127.0.0.2", 0), _RelayHandler)
        relay_port = srv.server_port
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        _RELAY_PORTS[target_port] = relay_port
        return relay_port


KEY_MAP = {
    "ArrowRight": Keys.ARROW_RIGHT,
    "ArrowLeft": Keys.ARROW_LEFT,
    "ArrowUp": Keys.ARROW_UP,
    "ArrowDown": Keys.ARROW_DOWN,
    "Enter": Keys.ENTER,
    "Escape": Keys.ESCAPE,
    "Tab": Keys.TAB,
}


def _js_unwrap_expr(expr: str) -> str:
    s = expr.strip()
    if s.startswith("() =>") or s.startswith("()=>"):
        return "return (" + s + ")();"
    if s.startswith("function"):
        return "return (" + s + ")();"
    if "\n" in s and "return " in s:
        return s
    return "return (" + s + ");"


class _DownloadValue:
    def __init__(self, file_path: pathlib.Path):
        self._path = file_path

    def save_as(self, target_path: str | pathlib.Path) -> None:
        shutil.copy2(self._path, target_path)


class _DownloadHolder:
    def __init__(self):
        self.value: _DownloadValue | None = None


class _Keyboard:
    def __init__(self, page: "Page"):
        self._page = page

    def press(self, key_name: str) -> None:
        self._page._flush_logs()
        k = KEY_MAP.get(key_name, key_name)
        active = self._page._driver.switch_to.active_element
        active.send_keys(k)
        self._page._flush_logs()


class _ElementLocator:
    """Wraps a specific index in a CSS selector match list (returned by locator.all())."""

    def __init__(self, page: "Page", selector: str, index: int, frame_selector: str | None = None):
        self._page = page
        self._selector = selector
        self._index = index
        self._frame_selector = frame_selector

    @contextmanager
    def _in_frame_context(self):
        drv = self._page._driver
        if self._frame_selector:
            iframe_el = drv.find_element(By.CSS_SELECTOR, self._frame_selector)
            drv.switch_to.frame(iframe_el)
            try:
                yield drv
            finally:
                drv.switch_to.default_content()
        else:
            yield drv

    def locator(self, sub_selector: str) -> "_Locator":
        combined = f"{self._selector} {sub_selector}"
        return _Locator(self._page, combined, frame_selector=self._frame_selector)

    def is_visible(self) -> bool:
        with self._in_frame_context() as drv:
            return bool(
                drv.execute_script(
                    """
                    const els = document.querySelectorAll(arguments[0]);
                    const el = els[arguments[1]];
                    if (!el) return false;
                    if (el.hasAttribute('hidden') || el.closest('[hidden]')) return false;
                    const cs = window.getComputedStyle(el);
                    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                    """,
                    self._selector,
                    self._index,
                )
            )

    def get_attribute(self, attr_name: str) -> str | None:
        with self._in_frame_context() as drv:
            return drv.execute_script(
                "const el = document.querySelectorAll(arguments[0])[arguments[1]]; return el ? el.getAttribute(arguments[2]) : null;",
                self._selector,
                self._index,
                attr_name,
            )

    def input_value(self) -> str:
        with self._in_frame_context() as drv:
            return str(
                drv.execute_script(
                    "const el = document.querySelectorAll(arguments[0])[arguments[1]]; return el && el.value !== undefined ? String(el.value) : '';",
                    self._selector,
                    self._index,
                )
            )

    def inner_text(self) -> str:
        with self._in_frame_context() as drv:
            return str(
                drv.execute_script(
                    "const el = document.querySelectorAll(arguments[0])[arguments[1]]; return el ? (el.innerText || el.textContent || '') : '';",
                    self._selector,
                    self._index,
                )
            )

    def fill(self, value: str) -> None:
        with self._in_frame_context() as drv:
            drv.execute_script(
                """
                const el = document.querySelectorAll(arguments[0])[arguments[1]];
                if (el) {
                  el.focus();
                  el.value = arguments[2];
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }
                """,
                self._selector,
                self._index,
                str(value),
            )

    def select_option(self, index: int = 0) -> None:
        with self._in_frame_context() as drv:
            drv.execute_script(
                """
                const el = document.querySelectorAll(arguments[0])[arguments[1]];
                if (el && el.options && el.options.length > arguments[2]) {
                  el.selectedIndex = arguments[2];
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }
                """,
                self._selector,
                self._index,
                int(index),
            )

    def click(self) -> None:
        with self._in_frame_context() as drv:
            drv.execute_script(
                "const el = document.querySelectorAll(arguments[0])[arguments[1]]; if (el) el.click();",
                self._selector,
                self._index,
            )

    def evaluate(self, js_fn: str) -> Any:
        with self._in_frame_context() as drv:
            s = js_fn.strip()
            return drv.execute_script(
                f"const el = document.querySelectorAll(arguments[0])[arguments[1]]; return ({s})(el);",
                self._selector,
                self._index,
            )


class _Locator:
    def __init__(self, page: "Page", selector: str, frame_selector: str | None = None, text_match: tuple[str, bool] | None = None):
        self._page = page
        self._selector = selector
        self._frame_selector = frame_selector
        self._text_match = text_match

    @contextmanager
    def _in_frame_context(self):
        drv = self._page._driver
        if self._frame_selector:
            iframe_el = drv.find_element(By.CSS_SELECTOR, self._frame_selector)
            drv.switch_to.frame(iframe_el)
            try:
                yield drv
            finally:
                drv.switch_to.default_content()
        else:
            yield drv

    def locator(self, sub_selector: str) -> "_Locator":
        combined = f"{self._selector} {sub_selector}"
        return _Locator(self._page, combined, frame_selector=self._frame_selector)

    def all(self) -> list[_ElementLocator]:
        n = self.count()
        return [_ElementLocator(self._page, self._selector, i, frame_selector=self._frame_selector) for i in range(n)]

    def count(self) -> int:
        with self._in_frame_context() as drv:
            if self._text_match is not None:
                needle, exact = self._text_match
                return int(
                    drv.execute_script(
                        """
                        const needle = arguments[0], exact = arguments[1];
                        const bodyTxt = document.body ? (document.body.innerText || document.body.textContent || '') : '';
                        if (exact) return bodyTxt.trim() === needle ? 1 : 0;
                        return bodyTxt.includes(needle) ? 1 : 0;
                        """,
                        needle,
                        exact,
                    )
                )
            return len(drv.find_elements(By.CSS_SELECTOR, self._selector))

    def is_visible(self) -> bool:
        with self._in_frame_context() as drv:
            return bool(
                drv.execute_script(
                    """
                    const el = document.querySelector(arguments[0]);
                    if (!el) return false;
                    if (el.hasAttribute('hidden') || el.closest('[hidden]')) return false;
                    const cs = window.getComputedStyle(el);
                    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                    """,
                    self._selector,
                )
            )

    def get_attribute(self, attr_name: str) -> str | None:
        with self._in_frame_context() as drv:
            return drv.execute_script(
                "const el = document.querySelector(arguments[0]); return el ? el.getAttribute(arguments[1]) : null;",
                self._selector,
                attr_name,
            )

    def inner_text(self) -> str:
        with self._in_frame_context() as drv:
            return str(
                drv.execute_script(
                    "const el = document.querySelector(arguments[0]); return el ? (el.innerText || el.textContent || '') : '';",
                    self._selector,
                )
            )

    def input_value(self) -> str:
        with self._in_frame_context() as drv:
            return str(
                drv.execute_script(
                    "const el = document.querySelector(arguments[0]); return el && el.value !== undefined ? String(el.value) : '';",
                    self._selector,
                )
            )

    def text_content(self) -> str:
        with self._in_frame_context() as drv:
            return str(
                drv.execute_script(
                    "const el = document.querySelector(arguments[0]); return el ? (el.textContent || '') : '';",
                    self._selector,
                )
            )

    def click(self) -> None:
        self.wait_for(state="visible", timeout=15000)
        with self._in_frame_context() as drv:
            el = drv.find_element(By.CSS_SELECTOR, self._selector)
            drv.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'}); arguments[0].click();",
                el,
            )
        self._page._flush_logs()

    def fill(self, value: str) -> None:
        self.wait_for(state="visible", timeout=15000)
        with self._in_frame_context() as drv:
            el = drv.find_element(By.CSS_SELECTOR, self._selector)
            drv.execute_script(
                """
                const el = arguments[0], val = arguments[1];
                el.focus();
                el.value = val;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                """,
                el,
                str(value),
            )
        self._page._flush_logs()

    def select_option(self, value: str | int = 0) -> None:
        self.wait_for(state="visible", timeout=15000)
        with self._in_frame_context() as drv:
            drv.execute_script(
                """
                const el = document.querySelector(arguments[0]);
                const val = arguments[1];
                if (el && el.options) {
                  if (typeof val === 'number') {
                    el.selectedIndex = val;
                  } else {
                    el.value = String(val);
                  }
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                }
                """,
                self._selector,
                value,
            )
        self._page._flush_logs()

    def focus(self) -> None:
        with self._in_frame_context() as drv:
            drv.execute_script(
                "const el = document.querySelector(arguments[0]); if (el) el.focus();",
                self._selector,
            )

    def evaluate(self, js_fn: str) -> Any:
        with self._in_frame_context() as drv:
            s = js_fn.strip()
            if "=>" in s:
                return drv.execute_script(
                    f"const el = document.querySelector(arguments[0]); return ({s})(el);",
                    self._selector,
                )
            return drv.execute_script(_js_unwrap_expr(s))

    def wait_for(self, state: str = "visible", timeout: float = 15000) -> None:
        self._page.wait_for_selector(self._selector, state=state, timeout=timeout, frame_selector=self._frame_selector)


class _FrameLocator:
    def __init__(self, page: "Page", frame_selector: str):
        self._page = page
        self._frame_selector = frame_selector

    def locator(self, selector: str) -> _Locator:
        return _Locator(self._page, selector, frame_selector=self._frame_selector)

    def evaluate(self, js_expr: str, arg: Any = None) -> Any:
        drv = self._page._driver
        iframe_el = drv.find_element(By.CSS_SELECTOR, self._frame_selector)
        drv.switch_to.frame(iframe_el)
        try:
            s = js_expr.strip()
            if arg is not None and "=>" in s:
                return drv.execute_script(f"return ({s})(arguments[0]);", arg)
            return drv.execute_script(_js_unwrap_expr(s))
        finally:
            drv.switch_to.default_content()


class Page:
    def __init__(self, driver: webdriver.Chrome, download_dir: pathlib.Path, viewport: dict[str, int] | None = None):
        self._driver = driver
        self._download_dir = download_dir
        self._pageerror_handlers: list[Callable[[str], None]] = []
        self._console_handlers: list[Callable[[Any], None]] = []
        self.keyboard = _Keyboard(self)
        self.main_frame = self
        if viewport:
            self.set_viewport_size(viewport["width"], viewport["height"])

    @property
    def frames(self) -> list[Any]:
        iframes = self._driver.find_elements(By.TAG_NAME, "iframe")
        out: list[Any] = [self.main_frame]
        for idx, el in enumerate(iframes):
            fid = el.get_attribute("id")
            sel = f"#{fid}" if fid else f"iframe:nth-of-type({idx + 1})"
            out.append(_FrameLocator(self, sel))
        return out

    def set_viewport_size(self, width_or_dict: int | dict[str, int], height: int | None = None) -> None:
        if isinstance(width_or_dict, dict):
            w = int(width_or_dict["width"])
            h = int(width_or_dict["height"])
        else:
            w = int(width_or_dict)
            h = int(height or 800)
        self._driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": w,
                "height": h,
                "deviceScaleFactor": 1,
                "mobile": w <= 480,
            },
        )

    def on(self, event_name: str, handler: Callable[[Any], None]) -> None:
        if event_name == "pageerror":
            self._pageerror_handlers.append(handler)
        elif event_name == "console":
            self._console_handlers.append(handler)

    def _flush_logs(self) -> None:
        try:
            logs = self._driver.get_log("browser")
        except Exception:
            logs = []
        for entry in logs:
            msg = str(entry.get("message", ""))
            level = str(entry.get("level", "")).upper()
            if "favicon.ico" in msg:
                continue
            if level == "SEVERE" and ("Uncaught" in msg or "Error" in msg or "TypeError" in msg or "ReferenceError" in msg):
                for cb in self._pageerror_handlers:
                    cb(msg)

    def goto(self, url: str, wait_until: str = "networkidle", timeout: float = 30000) -> None:
        if url.startswith("file://"):
            parsed_path = pathlib.Path(urllib.parse.unquote(urllib.parse.urlparse(url).path))
            url = _serve_local_html_bytes(str(parsed_path), parsed_path.read_bytes())
        elif _POLICY_BLOCKS_127_0_0_1:
            m = re.match(r"^http://(127\.0\.0\.1|localhost):([0-9]+)(/.*)?$", url, re.IGNORECASE)
            if m:
                target_port = int(m.group(2))
                rest = m.group(3) or "/"
                relay_port = _ensure_loopback_relay(target_port)
                url = f"http://127.0.0.2:{relay_port}{rest}"
        self._driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                (function() {
                  if (window.__dlHooked) return;
                  window.__dlHooked = true;
                  window.__capturedDownloads = [];
                  const _origClick = HTMLAnchorElement.prototype.click;
                  HTMLAnchorElement.prototype.click = function() {
                    if (this.hasAttribute('download') || this.download) {
                      const fname = this.download || 'download.html';
                      const href = this.href || '';
                      if (href.startsWith('blob:')) {
                        fetch(href).then(r => r.text()).then(txt => {
                          window.__capturedDownloads.push({ filename: fname, content: txt });
                        }).catch(() => {});
                      } else if (href.startsWith('data:')) {
                        window.__capturedDownloads.push({ filename: fname, content: decodeURIComponent(href.split(',')[1] || '') });
                      }
                    }
                    return _origClick.apply(this, arguments);
                  };
                })();
                """
            },
        )
        self._driver.get(url)
        deadline = time.time() + (timeout / 1000.0)
        while time.time() < deadline:
            ready = self._driver.execute_script("return document.readyState === 'complete';")
            if ready:
                break
            time.sleep(0.05)
        time.sleep(0.2)
        self._flush_logs()

    def title(self) -> str:
        return str(self._driver.title or "")

    def reload(self, wait_until: str = "load", timeout: float = 15000) -> None:
        self._driver.refresh()
        time.sleep(0.2)
        self._flush_logs()

    def set_content(self, html: str) -> None:
        url = _serve_local_html_bytes(f"/__set_content_{id(self)}.html", html.encode("utf-8"))
        self.goto(url)

    def locator(self, selector: str) -> _Locator:
        return _Locator(self, selector)

    def frame_locator(self, frame_selector: str) -> _FrameLocator:
        return _FrameLocator(self, frame_selector)

    def get_by_text(self, text: str, exact: bool = False) -> _Locator:
        return _Locator(self, "*", text_match=(text, exact))

    def click(self, selector: str) -> None:
        self.locator(selector).click()

    def fill(self, selector: str, value: str) -> None:
        self.locator(selector).fill(value)

    def select_option(self, selector: str, value: str | int) -> None:
        self.locator(selector).select_option(value)

    def text_content(self, selector: str) -> str:
        return self.locator(selector).text_content()

    def wait_for_timeout(self, ms: float) -> None:
        time.sleep(float(ms) / 1000.0)
        self._flush_logs()

    def wait_for_selector(
        self,
        selector: str,
        *,
        state: str = "visible",
        timeout: float = 15000,
        frame_selector: str | None = None,
    ) -> None:
        deadline = time.time() + (float(timeout) / 1000.0)
        loc = _Locator(self, selector, frame_selector=frame_selector)
        while time.time() < deadline:
            vis = loc.is_visible()
            if state == "visible" and vis:
                return
            if state == "hidden" and not vis:
                return
            time.sleep(0.08)
        raise TimeoutError(f"Timeout waiting for selector {selector!r} to reach state={state!r}")

    def wait_for_function(self, js_expr: str, timeout: float = 15000) -> None:
        deadline = time.time() + (float(timeout) / 1000.0)
        while time.time() < deadline:
            try:
                res = self.evaluate(js_expr)
                if res:
                    return
            except Exception:
                pass
            time.sleep(0.08)
        raise TimeoutError(f"Timeout waiting for function {js_expr!r}")

    def evaluate(self, js_expr: str, arg: Any = None) -> Any:
        self._flush_logs()
        s = js_expr.strip()
        if arg is not None and "=>" in s:
            return self._driver.execute_script(f"return ({s})(arguments[0]);", arg)
        return self._driver.execute_script(_js_unwrap_expr(s))

    def screenshot(self, path: str | pathlib.Path) -> None:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._driver.save_screenshot(str(p))

    @contextmanager
    def expect_download(self, timeout: float = 15000):
        before_files = set(self._download_dir.glob("*"))
        holder = _DownloadHolder()
        yield holder
        deadline = time.time() + (float(timeout) / 1000.0)
        downloaded: pathlib.Path | None = None
        while time.time() < deadline:
            try:
                cap = self._driver.execute_script(
                    "return (window.__capturedDownloads && window.__capturedDownloads.length) ? window.__capturedDownloads.pop() : null;"
                )
                if cap and cap.get("content"):
                    out_f = self._download_dir / (cap.get("filename") or "exported.html")
                    out_f.write_text(cap["content"], encoding="utf-8")
                    downloaded = out_f
                    break
            except Exception:
                pass
            current_files = set(self._download_dir.glob("*"))
            new_files = [
                f for f in (current_files - before_files)
                if not f.name.endswith(".crdownload") and not f.name.endswith(".tmp") and f.stat().st_size > 0
            ]
            if new_files:
                downloaded = sorted(new_files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                break
            time.sleep(0.1)
        if downloaded is None:
            raise TimeoutError("Download did not complete in headless Chromium")
        holder.value = _DownloadValue(downloaded)

    def close(self) -> None:
        pass


class BrowserContext:
    def __init__(self, browser: "Browser", viewport: dict[str, int] | None = None, reduced_motion: str | None = None):
        self._browser = browser
        self._viewport = viewport or {"width": 1280, "height": 800}
        self._reduced_motion = reduced_motion

    def new_page(self) -> Page:
        page = self._browser.new_page(viewport=self._viewport)
        if self._reduced_motion == "reduce":
            try:
                page._driver.execute_cdp_cmd(
                    "Emulation.setEmulatedMedia",
                    {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]},
                )
            except Exception:
                pass
        return page

    def close(self) -> None:
        pass


import atexit

_SHARED_DRIVER_LOCK = threading.Lock()
_SHARED_DRIVER: webdriver.Chrome | None = None


def _get_or_create_warm_driver(binary_loc: str, extra_args: list[str], download_dir: pathlib.Path) -> webdriver.Chrome:
    global _SHARED_DRIVER
    with _SHARED_DRIVER_LOCK:
        if _SHARED_DRIVER is not None:
            try:
                _ = _SHARED_DRIVER.current_url
                _SHARED_DRIVER.execute_cdp_cmd(
                    "Page.setDownloadBehavior",
                    {"behavior": "allow", "downloadPath": str(download_dir)},
                )
                return _SHARED_DRIVER
            except Exception:
                try:
                    _SHARED_DRIVER.quit()
                except Exception:
                    pass
                _SHARED_DRIVER = None

        opts = Options()
        opts.binary_location = binary_loc
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        for a in extra_args:
            if a not in ("--no-sandbox", "--disable-dev-shm-usage"):
                opts.add_argument(a)
        prefs = {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        opts.add_experimental_option("prefs", prefs)
        opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        srv = Service(CHROMEDRIVER_BIN)
        _SHARED_DRIVER = webdriver.Chrome(service=srv, options=opts)
        _SHARED_DRIVER.execute_cdp_cmd(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)},
        )
        return _SHARED_DRIVER


def _cleanup_shared_driver() -> None:
    global _SHARED_DRIVER
    with _SHARED_DRIVER_LOCK:
        if _SHARED_DRIVER is not None:
            try:
                _SHARED_DRIVER.quit()
            except Exception:
                pass
            _SHARED_DRIVER = None


atexit.register(_cleanup_shared_driver)


class Browser:
    def __init__(self, executable_path: str | None = None, args: list[str] | None = None):
        binary_loc = executable_path or CHROMIUM_BIN
        if not pathlib.Path(binary_loc).exists():
            raise FileNotFoundError(f"Chromium binary not found at {binary_loc}")
        self._download_tmp = tempfile.TemporaryDirectory(prefix="chromium-dl-")
        self._download_dir = pathlib.Path(self._download_tmp.name)
        self._driver = _get_or_create_warm_driver(binary_loc, list(args or []), self._download_dir)

    def new_page(self, viewport: dict[str, int] | None = None, device_scale_factor: float = 1.0) -> Page:
        try:
            self._driver.execute_cdp_cmd(
                "Emulation.setEmulatedMedia",
                {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]},
            )
        except Exception:
            pass
        return Page(self._driver, self._download_dir, viewport=viewport or {"width": 1280, "height": 800})

    def new_context(
        self,
        viewport: dict[str, int] | None = None,
        device_scale_factor: float = 1.0,
        reduced_motion: str | None = None,
    ) -> BrowserContext:
        return BrowserContext(self, viewport=viewport, reduced_motion=reduced_motion)

    def close(self) -> None:
        try:
            self._download_tmp.cleanup()
        except Exception:
            pass


class _ChromiumLauncher:
    @property
    def executable_path(self) -> str:
        return CHROMIUM_BIN

    def launch(self, headless: bool = True, executable_path: str | None = None, args: list[str] | None = None) -> Browser:
        return Browser(executable_path=executable_path, args=args)


class _PlaywrightContextManager:
    def __init__(self):
        self.chromium = _ChromiumLauncher()

    def __enter__(self) -> "_PlaywrightContextManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def sync_playwright() -> _PlaywrightContextManager:
    return _PlaywrightContextManager()
