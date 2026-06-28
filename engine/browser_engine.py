"""
Mobile browser simulation engine using Playwright.
Thread-safe implementation with a dedicated browser thread.
Includes anti-detection stealth measures and human-like behavior simulation.
"""
import os
import sys
import traceback
import time
import json
import base64
import random
import math
import threading
import queue
from typing import Optional

os.environ.pop("NODE_OPTIONS", None)

from playwright.sync_api import sync_playwright

# ─── Mobile Device Profiles ──────────────────────────────

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

# ─── Stealth Script ──────────────────────────────────────
# Injected into every page to hide automation traces.

STEALTH_SCRIPT = """
// === Anti-Detection Stealth ===
(function() {
    'use strict';

    // 1. Hide webdriver flag (most common detection)
    Object.defineProperty(navigator, 'webdriver', { get: () => false });

    // 2. Fake plugins array (empty plugins = bot signal)
    Object.defineProperty(navigator, 'plugins', {
        get: () => {
            const plugins = [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1 },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1 },
                { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2 },
            ];
            plugins.item = (i) => plugins[i] || null;
            plugins.namedItem = (n) => plugins.find(p => p.name === n) || null;
            plugins.refresh = () => {};
            return plugins;
        }
    });

    // 3. Override permissions query to look natural
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission, onchange: null }) :
            originalQuery(parameters)
    );

    // 4. Hide Chrome automation extension
    Object.defineProperty(navigator, 'chrome', {
        get: () => ({
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        })
    });

    // 5. Fake languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });

    // 6. Remove Playwright-specific marks
    delete window.__playwright__binding__;
    delete window.__pwInitScripts;
    delete window.__playwright;

    // 7. Override toString on native functions to look natural
    const nativeToString = Function.prototype.toString;
    Function.prototype.toString = function() {
        if (this === window.navigator.permissions.query) {
            return 'function query() { [native code] }';
        }
        return nativeToString.call(this);
    };

    // 8. Fix Intl.DateTimeFormat for headless detection
    const originalDateTimeFormat = Intl.DateTimeFormat;
    Intl.DateTimeFormat = function(locales, options) {
        return new originalDateTimeFormat(locales, options || { timeZone: 'America/New_York' });
    };
    Intl.DateTimeFormat.prototype = originalDateTimeFormat.prototype;

    // 9. Override hardware concurrency (headless often reports 1)
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8
    });

    // 10. Override deviceMemory
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8
    });

})();
"""


# ─── Human-like Behavior Helpers ─────────────────────────

def _human_delay(min_ms: int = 50, max_ms: int = 300) -> float:
    """Random delay between actions to mimic human reaction time."""
    return random.randint(min_ms, max_ms) / 1000.0


def _bezier_curve(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    """Cubic bezier interpolation."""
    return (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t ** 2 * p2
        + t ** 3 * p3
    )


def _generate_mouse_path(start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 30):
    """Generate a human-like mouse movement path using bezier curves."""
    # Add random overshoot and correction
    mid_x = (start_x + end_x) / 2 + random.randint(-40, 40)
    mid_y = (start_y + end_y) / 2 + random.randint(-30, 30)
    # Control points with slight randomness
    cp1_x = start_x + (mid_x - start_x) * random.uniform(0.3, 0.7)
    cp1_y = start_y + random.randint(-20, 20)
    cp2_x = mid_x + (end_x - mid_x) * random.uniform(0.3, 0.7)
    cp2_y = end_y + random.randint(-20, 20)

    path = []
    for i in range(steps + 1):
        t = i / steps
        # Ease-in-out timing
        eased_t = t ** 2 * (3 - 2 * t) if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
        x = _bezier_curve(eased_t, start_x, cp1_x, cp2_x, end_x)
        y = _bezier_curve(eased_t, start_y, cp1_y, cp2_y, end_y)
        path.append((int(x), int(y)))
    return path


class BrowserEngine:
    """
    Thread-safe mobile browser simulator with anti-detection stealth.
    Runs Playwright on a dedicated background thread;
    commands are queued and results returned synchronously.
    """

    def __init__(self, profile: str = "iphone_14_pro_max"):
        self._profile_name = profile
        self._profile = MOBILE_PROFILES.get(profile, IPHONE_14_PRO_MAX)
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._screenshot_dir = os.path.join(root, "screenshots")

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

        if not self._ready.wait(timeout=30):
            raise RuntimeError("Browser failed to start within 30s")

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

            # ── Browser args to hide automation ──
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--disable-background-networking",
                "--disable-sync",
                "--disable-default-apps",
                "--hide-scrollbars",
                "--metrics-recording-only",
                "--mute-audio",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-features=TranslateUI,BlinkGenPropertyTrees",
                "--disable-ipc-flooding-protection",
            ]

            browser = pw.chromium.launch(
                headless=True,
                args=browser_args,
            )

            # ── Context with realistic fingerprint ──
            context = browser.new_context(
                user_agent=self._profile["user_agent"],
                viewport=self._profile["viewport"],
                device_scale_factor=self._profile["device_scale_factor"],
                is_mobile=self._profile["is_mobile"],
                has_touch=self._profile["has_touch"],
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"],
                geolocation={"latitude": 40.7128, "longitude": -74.0060},  # NYC
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Upgrade-Insecure-Requests": "1",
                },
            )

            # ── Inject stealth script on every new page ──
            context.add_init_script(STEALTH_SCRIPT)

            page = context.new_page()

            # ── Randomize viewport slightly to avoid fingerprinting ──
            w, h = self._profile["viewport"]["width"], self._profile["viewport"]["height"]
            page.set_viewport_size({
                "width": w + random.randint(-2, 2),
                "height": h + random.randint(-2, 2),
            })

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

            # ── Human-like action helpers (must run in browser thread) ──

            def _human_mouse_move(target_x: int, target_y: int):
                """Move mouse like a human: bezier path + variable steps."""
                try:
                    # Get current mouse position approximation
                    js_pos = page.evaluate("""
                        ({x: window._lastMouseX || 200, y: window._lastMouseY || 400})
                    """)
                    start_x, start_y = js_pos["x"], js_pos["y"]
                except Exception:
                    start_x, start_y = 200, 400

                # Generate path
                path = _generate_mouse_path(start_x, start_y, target_x, target_y, steps=25)
                for px, py in path:
                    page.mouse.move(px, py)
                    time.sleep(random.uniform(0.005, 0.015))

                # Save position for next movement
                page.evaluate(f"window._lastMouseX = {target_x}; window._lastMouseY = {target_y};")

            def _human_type(text: str):
                """Type text with variable delays between keystrokes."""
                for char in text:
                    page.keyboard.type(char)
                    # Variable typing speed: faster for common chars
                    if char in " etaoinsrh":
                        time.sleep(random.uniform(0.03, 0.08))
                    else:
                        time.sleep(random.uniform(0.06, 0.15))

            def _human_scroll(scroll_y: int):
                """Scroll with easing, like a human."""
                current = page.evaluate("window.scrollY")
                target = current + scroll_y
                steps = random.randint(8, 15)
                for i in range(1, steps + 1):
                    t = i / steps
                    # Ease-out cubic
                    eased = 1 - (1 - t) ** 3
                    pos = current + scroll_y * eased
                    page.evaluate(f"window.scrollTo(0, {int(pos)})")
                    time.sleep(random.uniform(0.02, 0.06))

            def _random_micro_pause():
                """Tiny random pause like a human thinking."""
                time.sleep(random.uniform(0.1, 0.5))

            def _simulate_human_presence():
                """Occasionally do random micro-actions to simulate a real user."""
                actions = random.randint(0, 2)
                for _ in range(actions):
                    r = random.random()
                    if r < 0.3:
                        # Tiny scroll wiggle
                        page.evaluate(f"window.scrollBy(0, {random.randint(-5, 5)})")
                    elif r < 0.6:
                        # Move mouse a tiny bit
                        try:
                            js_x = page.evaluate("window._lastMouseX || 200")
                            js_y = page.evaluate("window._lastMouseY || 400")
                            page.mouse.move(
                                js_x + random.randint(-10, 10),
                                js_y + random.randint(-10, 10),
                            )
                        except Exception:
                            pass
                    time.sleep(random.uniform(0.05, 0.2))

            # ── Main command loop ──
            while self._running:
                try:
                    cmd, params = self._cmd_queue.get(timeout=0.5)
                except queue.Empty:
                    if page and not page.is_closed():
                        _update_cache()
                    continue

                if cmd == "_STOP_":
                    break

                result = {"status": "ok"}
                try:
                    if cmd == "navigate":
                        page.goto(params["url"], wait_until="domcontentloaded", timeout=30000)
                        # Wait a bit like a human looking at the page
                        time.sleep(random.uniform(0.5, 1.5))
                        _simulate_human_presence()
                        result["success"] = True

                    elif cmd == "click":
                        _random_micro_pause()
                        x, y = params.get("x", 0), params.get("y", 0)
                        if params.get("selector"):
                            # Get element position for human movement
                            box = page.locator(params["selector"]).bounding_box()
                            if box:
                                x = box["x"] + box["width"] / 2
                                y = box["y"] + box["height"] / 2
                        # Human-like movement to target
                        _human_mouse_move(x, y)
                        time.sleep(random.uniform(0.05, 0.15))
                        # Playwright click
                        page.mouse.click(x, y)
                        time.sleep(random.uniform(0.03, 0.08))
                        # Fallback: native JS click on the element at coordinates (handles SPAs)
                        try:
                            page.evaluate(f"""
                                (() => {{
                                    const el = document.elementFromPoint({x}, {y});
                                    if (!el) return 'no element';
                                    el.focus();
                                    el.dispatchEvent(new MouseEvent('click', {{
                                        bubbles: true, cancelable: true,
                                        clientX: {x}, clientY: {y}, view: window
                                    }}));
                                    // If it's an anchor, try to navigate
                                    if (el.tagName === 'A' && el.href) {{
                                        el.click();
                                    }}
                                    // If it's a label, click its associated input
                                    if (el.tagName === 'LABEL' && el.getAttribute('for')) {{
                                        const input = document.getElementById(el.getAttribute('for'));
                                        if (input) input.click();
                                    }}
                                    return 'clicked ' + el.tagName + (el.href ? ' ' + el.href : '');
                                }})()
                            """)
                        except Exception:
                            pass
                        _random_micro_pause()
                        result["success"] = True

                    elif cmd == "longpress":
                        _random_micro_pause()
                        x, y = params["x"], params["y"]
                        _human_mouse_move(x, y)
                        time.sleep(random.uniform(0.05, 0.1))
                        page.mouse.down()
                        time.sleep(params.get("duration", 1000) / 1000)
                        page.mouse.up()
                        _random_micro_pause()
                        result["success"] = True

                    elif cmd == "drag":
                        _random_micro_pause()
                        x, y = params["x"], params["y"]
                        tx, ty = params.get("tx", x + 100), params.get("ty", y + 100)
                        _human_mouse_move(x, y)
                        time.sleep(random.uniform(0.05, 0.1))
                        page.mouse.down()
                        # Human-like drag with multiple intermediate steps
                        path = _generate_mouse_path(x, y, tx, ty, steps=20)
                        for px, py in path:
                            page.mouse.move(px, py)
                            time.sleep(random.uniform(0.008, 0.02))
                        page.mouse.up()
                        _random_micro_pause()
                        result["success"] = True

                    elif cmd == "input":
                        _random_micro_pause()
                        x, y = params.get("x", 0), params.get("y", 0)
                        text = params.get("text", "")
                        if params.get("selector"):
                            # Click the field first with human movement
                            box = page.locator(params["selector"]).bounding_box()
                            if box:
                                x = box["x"] + box["width"] / 2
                                y = box["y"] + box["height"] / 2
                            _human_mouse_move(x, y)
                            time.sleep(random.uniform(0.05, 0.15))
                            page.click(params["selector"])
                            time.sleep(random.uniform(0.1, 0.3))
                            # Clear existing text and type
                            page.fill(params["selector"], "")
                            time.sleep(random.uniform(0.05, 0.15))
                            _human_type(text)
                        else:
                            _human_mouse_move(x, y)
                            time.sleep(random.uniform(0.05, 0.1))
                            page.mouse.click(x, y)
                            time.sleep(random.uniform(0.1, 0.3))
                            _human_type(text)
                        _random_micro_pause()
                        result["success"] = True

                    elif cmd == "scroll":
                        _random_micro_pause()
                        dy = params.get("dy", 300)
                        _human_scroll(dy)
                        _random_micro_pause()
                        result["success"] = True

                    elif cmd == "back":
                        page.go_back(wait_until="domcontentloaded")
                        time.sleep(random.uniform(0.3, 0.8))
                        result["success"] = True

                    elif cmd == "refresh":
                        page.reload(wait_until="domcontentloaded")
                        time.sleep(random.uniform(0.5, 1.0))
                        result["success"] = True

                    elif cmd == "copy":
                        page.keyboard.press("Control+C")
                        _random_micro_pause()
                        result["success"] = True

                    elif cmd == "paste":
                        _random_micro_pause()
                        if params.get("text"):
                            _human_type(params["text"])
                        else:
                            page.keyboard.press("Control+V")
                        _random_micro_pause()
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

                    elif cmd == "click_js":
                        page.evaluate(f"""
                            const el = document.querySelector('{params["selector"]}');
                            if (el) {{
                                el.focus();
                                el.dispatchEvent(new MouseEvent('click', {{bubbles:true,cancelable:true,view:window}}));
                                if (el.tagName === 'A') el.click();
                            }}
                        """)
                        result["success"] = True

                    elif cmd == "click_js_at":
                        page.evaluate(f"""
                            const el = document.elementFromPoint({params['x']}, {params['y']});
                            if (el) {{
                                el.focus();
                                el.dispatchEvent(new MouseEvent('click', {{bubbles:true,cancelable:true,view:window,clientX:{params['x']},clientY:{params['y']}}}));
                                if (el.tagName === 'A' && el.href) el.click();
                            }}
                        """)
                        result["success"] = True

                except Exception as e:
                    result = {"status": "error", "error": str(e), "success": False}

                self._result_queue.put(result)
                _update_cache()

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[BrowserEngine] FATAL: {e}\n{tb}", file=sys.stderr, flush=True)
            self._cached_info = {"ready": False, "error": str(e), "traceback": tb}
            self._ready.set()
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
