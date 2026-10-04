"""Real browser automation via Playwright (optional) + HTML portal server."""
import os
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

from src.executor import ActionResult

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False


class PortalServer:
    """Serves the local invoice portal over HTTP (file:// breaks JS in some browsers)."""

    def __init__(self, directory: str, port: int = 8765):
        self.directory = directory
        self.port = port
        self._httpd = None
        self._thread = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    class _QuietHandler(SimpleHTTPRequestHandler):
        """Suppresses the default per-request stderr logging."""
        def log_message(self, fmt, *args):
            pass

    def start(self) -> str:
        handler = partial(self._QuietHandler, directory=self.directory)
        self._httpd = HTTPServer(("127.0.0.1", self.port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


class PlaywrightBrowser:
    """Real Chromium driven over Playwright.

    Replaces BrowserSimulator in executor.py. Same four methods, so the
    agent loop above does not change.
    """

    def __init__(self, portal_url: str = ""):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        self.portal_url = portal_url.rstrip("/")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True, args=["--no-sandbox"])
        self._page = self._browser.new_page()
        self.last_rows = []

    def navigate_to(self, url: str) -> ActionResult:
        target = url
        if url.endswith("/portal") and self.portal_url:
            target = f"{self.portal_url}/invoices.html"
        try:
            self._page.goto(target, wait_until="domcontentloaded", timeout=15000)
            title = self._page.title()
            return ActionResult(True, f"Loaded {target} — title: {title}",
                               {"url": target, "page_loaded": True, "title": title})
        except Exception as e:
            return ActionResult(False, f"Navigation failed: {e}", confidence=0.2)

    def search(self, query: str) -> ActionResult:
        try:
            company = query.replace(" latest invoice", "").replace("invoice", "").strip()
            self._page.fill("#q", company)
            self._page.click("#searchBtn")
            self._page.wait_for_timeout(300)
            rows = self._page.eval_on_selector_all(
                "#rows tr",
                """els => els.map(e => ({
                    id: e.querySelector('.inv-id')?.textContent || '',
                    company: e.querySelector('.company')?.textContent || '',
                    vendor: e.querySelector('.vendor')?.textContent || '',
                    amount: e.querySelector('.amount')?.textContent || '',
                    due_date: e.querySelector('.due')?.textContent || '',
                    date: e.querySelector('.date')?.textContent || ''
                }))"""
            )
            self.last_rows = rows
            return ActionResult(True, f"Browser search '{company}' returned {len(rows)} row(s)",
                               {"results": rows, "company": company})
        except Exception as e:
            return ActionResult(False, f"Search failed: {e}", confidence=0.2)

    def close(self):
        try:
            self._browser.close()
            self._pw.stop()
        except Exception:
            pass
