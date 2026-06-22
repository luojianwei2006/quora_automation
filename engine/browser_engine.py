"""
Mobile browser simulation engine using Playwright.
Thread-safe implementation with a dedicated browser thread.
"""
import os
import time
import json
import base64
import threading
import queue
from typing import Optional

os.environ.pop("NODE_OPTIONS", None)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/root/.cache/ms-playwright"

from playwright.sync_api import sync_playwright

# Mobile device profiles
IPHONE_14_PRO_MAX = {
    "user_agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "viewport": {"width": 390, "height": 844},
    "device_scale_factor": 3,
    "is_mobile": True,
    "has_touch": True,
}

GALAXY_S23 = {
    "user_agent": (
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36"
    ),
    "viewport": {"width": 412, "height": 915},
    "device_scale_factor": 3.5,
    "is_mobile": True,
    "has_touch": True,
}

MOBILE_PROFILES = {
    "iphone_14_pro_max": IPHONE_14_PRO_MAX,
    "galaxy_s23": GALAXY_S23,
}


class BrowserEngine:
    """
    Thread-safe mobile browser simulator.
    Runs Playwright on a dedicated background thread;
    commands are queued and results returned synchronously.
    """

    def __init__(self, profile: str = "iphone_14_pro_max"):
        self._profile_name = profile
        self._profile = MOBILE_PROFILES.get(profile, IPHONE_14_PRO_MAX)
        self._screenshot_dir = "/workspace/quora-automation/screenshots"

        # Threading
        self._cmd_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._running = False

        # Cached state (accessed from any thread)
        self._cached_screenshot: Optional[str] = None
        self._cached_info: dict = {"ready": False, "url": "", "title": ""}

    # ─── Properties ──────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def page(self):
        """Not directly accessible across threads."""
        return None

    # ─── Lifecycle ────────────────────────────────────────

    def start(self):
        """Start the browser worker thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._ready.clear()

        self._worker = threading.Thread(target=self._browser_loop, daemon=True)
        self._worker.start()

        # Wait for browser to be ready
        if not self._ready.wait(timeout=20):
            raise RuntimeError("Browser failed to start within 20s")

    def close(self):
        """Stop the browser."""
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._cmd_queue.put_nowait(("_STOP_", {}))
        if self._worker:
            self._worker.join(timeout=10)
            self._worker = None
        self._ready.clear()
        self._cached_info["ready"] = False

    # ─── Command Execution ────────────────────────────────

    def _send_command(self, command: str, params: dict = None, timeout: float = 60) -> dict:
        """Send a command to the browser thread and wait for the result."""
        if not self._running:
            self.start()
        params = params or {}
        self._cmd_queue.put_nowait((command, params))
        try:
            result = self._result_queue.get(timeout=timeout)
            return result
        except queue.Empty:
            return {"status": "error", "error": "Command timeout"}

    # ─── Public API ───────────────────────────────────────

    def navigate(self, url: str):
        self._send_command("navigate", {"url": url})

    def get_screenshot(self) -> Optional[str]:
        return self._cached_screenshot

    def get_page_info(self) -> dict:
        return self._cached_info

    def get_page_html(self) -> str:
        r = self._send_command("get_html", timeout=15)
        return r.get("html", "")

    def get_page_text(self) -> str:
        r = self._send_command("get_text", timeout=15)
        return r.get("text", "")

    def execute_click(self, x: int, y: int, selector: str = "") -> bool:
        r = self._send_command("click", {"x": x, "y": y, "selector": selector})
        return r.get("success", False)

    def execute_long_press(self, x: int, y: int, duration_ms: int = 1000) -> bool:
        r = self._send_command("longpress", {"x": x, "y": y, "duration": duration_ms})
        return r.get("success", False)

    def execute_drag(self, x: int, y: int, target_x: int, target_y: int) -> bool:
        r = self._send_command("drag", {"x": x, "y": y, "tx": target_x, "ty": target_y})
        return r.get("success", False)

    def execute_input(self, text: str, selector: str = "", x: int = 0, y: int = 0) -> bool:
        r = self._send_command("input", {"text": text, "selector": selector, "x": x, "y": y})
        return r.get("success", False)

    def execute_scroll(self, delta_x: int = 0, delta_y: int = 300) -> bool:
        r = self._send_command("scroll", {"dx": delta_x, "dy": delta_y})
        return r.get("success", False)

    def execute_navigate(self, url: str) -> bool:
        r = self._send_command("navigate", {"url": url})
        return r.get("success", False)

    def execute_back(self) -> bool:
        r = self._send_command("back", {})
        return r.get("success", False)

    def execute_refresh(self) -> bool:
        r = self._send_command("refresh", {})
        return r.get("success", False)

    def execute_copy(self) -> bool:
        r = self._send_command("copy", {})
        return r.get("success", False)

    def execute_paste(self, text: str = "") -> bool:
        r = self._send_command("paste", {"text": text})
        return r.get("success", False)

    def execute_extract_text(self, selector: str = "body") -> str:
        r = self._send_command("extract", {"selector": selector})
        return r.get("text", "")

    def check_completion(self, check_type: str, check_value: str) -> bool:
        r = self._send_command("check", {"type": check_type, "value": check_value})
        return r.get("matched", False)

    def get_element_at(self, x: int, y: int) -> dict:
        r = self._send_command("element_at", {"x": x, "y": y})
        return r.get("element", {"tag": "", "text": "", "selector": ""})

    # ─── Browser Worker Loop ─────────────────────────────

    def _browser_loop(self):
        """Dedicated thread that runs Playwright and handles commands."""
        pw = None
        browser = None
        context = None
        page = None

        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(
                headless=True,
                args=["--disable-web-security", "--disable-features=IsolateOrigins,site-per-process"],
            )
            context = browser.new_context(
                user_agent=self._profile["user_agent"],
                viewport=self._profile["viewport"],
                device_scale_factor=self._profile["device_scale_factor"],
                is_mobile=self._profile["is_mobile"],
                has_touch=self._profile["has_touch"],
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = context.new_page()

            # Update cache
            self._cached_info = {
                "ready": True,
                "url": "about:blank",
                "title": "",
                "viewport": self._profile["viewport"],
                "device": self._profile_name,
            }
            self._ready.set()

            def _update_cache():
                try:
                    url = page.url
                    title = page.title()
                    self._cached_info = {
                        "ready": True,
                        "url": url,
                        "title": title,
                        "viewport": self._profile["viewport"],
                        "device": self._profile_name,
                    }
                except Exception:
                    pass
                try:
                    screenshot_bytes = page.screenshot(type="png", full_page=False)
                    os.makedirs(self._screenshot_dir, exist_ok=True)
                    timestamp = int(time.time() * 1000)
                    filepath = os.path.join(self._screenshot_dir, f"screenshot_{timestamp}.png")
                    with open(filepath, "wb") as f:
                        f.write(screenshot_bytes)
                    b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                    self._cached_screenshot = f"data:image/png;base64,{b64}"
                except Exception:
                    pass

            def _screenshot():
                nonlocal page
                try:
                    return page.screenshot(type="png", full_page=False)
                except Exception:
                    return None

            # Command handler
            while self._running:
                try:
                    cmd, params = self._cmd_queue.get(timeout=0.5)
                except queue.Empty:
                    # Periodically update cache
                    if page and not page.is_closed():
                        _update_cache()
                    continue

                if cmd == "_STOP_":
                    break

                result = {"status": "ok"}
                try:
                    if cmd == "navigate":
                        page.goto(params["url"], wait_until="networkidle", timeout=30000)
                        result["success"] = True

                    elif cmd == "click":
                        if params.get("selector"):
                            page.click(params["selector"], timeout=10000)
                        else:
                            page.mouse.click(params["x"], params["y"])
                        result["success"] = True

                    elif cmd == "longpress":
                        page.mouse.move(params["x"], params["y"])
                        page.mouse.down()
                        time.sleep(params.get("duration", 1000) / 1000)
                        page.mouse.up()
                        result["success"] = True

                    elif cmd == "drag":
                        x, y = params["x"], params["y"]
                        tx, ty = params.get("tx", x + 100), params.get("ty", y + 100)
                        page.mouse.move(x, y)
                        page.mouse.down()
                        steps = 20
                        for i in range(1, steps + 1):
                            cx = x + (tx - x) * i // steps
                            cy = y + (ty - y) * i // steps
                            page.mouse.move(cx, cy)
                            time.sleep(0.01)
                        page.mouse.up()
                        result["success"] = True

                    elif cmd == "input":
                        if params.get("selector"):
                            page.fill(params["selector"], params.get("text", ""), timeout=10000)
                        else:
                            page.mouse.click(params.get("x", 0), params.get("y", 0))
                            time.sleep(0.2)
                            page.keyboard.type(params.get("text", ""), delay=50)
                        result["success"] = True

                    elif cmd == "scroll":
                        page.evaluate(f"window.scrollBy({params.get('dx', 0)}, {params.get('dy', 300)})")
                        result["success"] = True

                    elif cmd == "back":
                        page.go_back(wait_until="networkidle")
                        result["success"] = True

                    elif cmd == "refresh":
                        page.reload(wait_until="networkidle")
                        result["success"] = True

                    elif cmd == "copy":
                        page.keyboard.press("Control+C")
                        result["success"] = True

                    elif cmd == "paste":
                        if params.get("text"):
                            page.keyboard.type(params["text"], delay=30)
                        else:
                            page.keyboard.press("Control+V")
                        result["success"] = True

                    elif cmd == "extract":
                        text = page.inner_text(params.get("selector", "body"))
                        result["text"] = text
                        result["success"] = True

                    elif cmd == "check":
                        matched = False
                        ct = params.get("type", "")
                        cv = params.get("value", "")
                        if ct == "url_contains":
                            matched = cv in page.url
                        elif ct == "text_contains":
                            body_text = page.inner_text("body")
                            matched = cv.lower() in body_text.lower()
                        elif ct == "selector_visible":
                            matched = page.is_visible(cv, timeout=5000)
                        elif ct == "element_disappeared":
                            matched = not page.is_visible(cv, timeout=5000)
                        elif ct == "element_enabled":
                            matched = page.is_enabled(cv, timeout=5000)
                        else:
                            matched = True
                        result["matched"] = matched

                    elif cmd == "element_at":
                        el_info = page.evaluate(f"""
                            (() => {{
                                const el = document.elementFromPoint({params['x']}, {params['y']});
                                if (!el) return {{tag:'',text:'',selector:''}};
                                const gs = (e) => {{
                                    if (e.id) return '#'+e.id;
                                    if (e.className && typeof e.className === 'string') {{
                                        const c = e.className.trim().split(/\\s+/)[0];
                                        if (c) return e.tagName.toLowerCase()+'.'+c;
                                    }}
                                    return e.tagName.toLowerCase();
                                }};
                                return {{
                                    tag: el.tagName,
                                    text: (el.textContent||'').trim().substring(0,100),
                                    selector: gs(el),
                                    placeholder: el.placeholder||'',
                                    value: el.value||'',
                                    type: el.type||'',
                                }};
                            }})()
                        """)
                        result["element"] = el_info

                    elif cmd == "get_html":
                        result["html"] = page.content()

                    elif cmd == "get_text":
                        result["text"] = page.inner_text("body")

                except Exception as e:
                    result = {"status": "error", "error": str(e), "success": False}

                self._result_queue.put(result)
                _update_cache()

        except Exception as e:
            self._cached_info = {"ready": False, "error": str(e)}
            self._ready.set()
            # Put error result for any pending command
            try:
                self._result_queue.put({"status": "error", "error": str(e)})
            except Exception:
                pass
        finally:
            try:
                if page:
                    page.close()
                if context:
                    context.close()
                if browser:
                    browser.close()
                if pw:
                    pw.stop()
            except Exception:
                pass
            self._running = False
