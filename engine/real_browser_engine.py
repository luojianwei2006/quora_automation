"""
Real desktop browser engine — uses xdotool for OS-level mouse/keyboard simulation
and a visible Chromium window. Completely bypasses bot detection.
"""
import os
import sys
import time
import json
import base64
import random
import math
import threading
import queue
import subprocess
from typing import Optional

# ─── Configuration ──────────────────────────────────────

VIEWPORT_WIDTH = 369
VIEWPORT_HEIGHT = 828
CHROMIUM_URL = "about:blank"

# Window position offset — Chromium window has a tab bar + address bar
# We position the window so the content area matches our viewport
WINDOW_X = 100  # left offset on screen
WINDOW_Y = 50   # top offset on screen
# Chromium chrome height (titlebar + tabs + address bar) ≈ 80px
CHROME_HEIGHT = 80

# ─── Helpers ────────────────────────────────────────────

def _xd(*args):
    """Run xdotool command, return output."""
    cmd = ["xdotool"] + [str(a) for a in args]
    result = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "DISPLAY": ":1"})
    return result.stdout.strip()


def _human_delay(min_ms=20, max_ms=80):
    time.sleep(random.randint(min_ms, max_ms) / 1000.0)


def _get_active_window():
    return _xd("getactivewindow")


def _screenshot(filepath: str):
    """Take screenshot of the browser content area."""
    subprocess.run([
        "import", "-window", "root",
        "-crop", f"{VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}+{WINDOW_X}+{WINDOW_Y + CHROME_HEIGHT}",
        filepath
    ], env={**os.environ, "DISPLAY": ":1"}, capture_output=True)
    return filepath


def _screenshot_base64():
    """Take screenshot and return as base64 data URL."""
    path = f"/tmp/real_browser_shot_{int(time.time()*1000)}.png"
    _screenshot(path)
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


class RealBrowserEngine:
    """
    Thread-safe browser engine using real OS mouse/keyboard (xdotool)
    and a visible Chromium window.
    """

    def __init__(self):
        self._profile = {"viewport": {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}}
        self._screenshot_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots"
        )
        self._cmd_queue = queue.Queue()
        self._result_queue = queue.Queue()
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._running = False
        self._window_id = ""
        self._current_url = "about:blank"
        self._cached_screenshot = None
        self._cached_info = {"ready": False, "url": "", "title": ""}

    @property
    def is_running(self):
        return self._running

    # ─── Lifecycle ───────────────────────────────────────

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._ready.clear()

        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()
        if not self._ready.wait(timeout=20):
            raise RuntimeError("Real browser failed to start")

    def close(self):
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._cmd_queue.put_nowait(("_STOP_", {}))
        if self._worker:
            self._worker.join(timeout=5)

    def _send_command(self, cmd, params=None, timeout=60):
        if not self._running:
            self.start()
        self._cmd_queue.put_nowait((cmd, params or {}))
        try:
            return self._result_queue.get(timeout=timeout)
        except queue.Empty:
            return {"status": "error", "error": "timeout"}

    # ─── Public API ──────────────────────────────────────

    def navigate(self, url: str):
        self._send_command("navigate", {"url": url})

    def get_screenshot(self):
        return self._cached_screenshot

    def get_page_info(self):
        return self._cached_info

    def execute_click(self, x: int, y: int, selector=""):
        r = self._send_command("click", {"x": x, "y": y})
        return r.get("success", False)

    def execute_long_press(self, x: int, y: int, duration_ms=1000):
        r = self._send_command("longpress", {"x": x, "y": y, "duration": duration_ms})
        return r.get("success", False)

    def execute_drag(self, x: int, y: int, target_x: int, target_y: int):
        r = self._send_command("drag", {"x": x, "y": y, "tx": target_x, "ty": target_y})
        return r.get("success", False)

    def execute_input(self, text: str, selector="", x=0, y=0):
        r = self._send_command("input", {"text": text, "x": x, "y": y})
        return r.get("success", False)

    def execute_scroll(self, delta_x=0, delta_y=300):
        r = self._send_command("scroll", {"dx": delta_x, "dy": delta_y})
        return r.get("success", False)

    def execute_navigate(self, url: str):
        r = self._send_command("navigate", {"url": url})
        return r.get("success", False)

    def execute_back(self):
        r = self._send_command("back", {})
        return r.get("success", False)

    def execute_copy(self):
        r = self._send_command("copy", {})
        return r.get("success", False)

    def execute_paste(self, text=""):
        r = self._send_command("paste", {"text": text})
        return r.get("success", False)

    def get_page_html(self):
        return "<html></html>"

    def get_page_text(self):
        return ""

    def execute_extract_text(self, selector=""):
        return ""

    def check_completion(self, check_type="", check_value=""):
        return False

    def get_element_at(self, x, y):
        return {"tag": "", "text": "", "selector": ""}

    def execute_refresh(self):
        r = self._send_command("refresh", {})
        return r.get("success", False)

    # ─── Main Loop ───────────────────────────────────────

    def _loop(self):
        try:
            # Kill any existing chromium
            subprocess.run(["pkill", "-9", "chromium"], capture_output=True)
            time.sleep(0.5)

            # Launch Chromium with specific window size
            window_width = VIEWPORT_WIDTH
            window_height = VIEWPORT_HEIGHT + CHROME_HEIGHT

            chrom = subprocess.Popen([
                "chromium",
                f"--window-size={window_width},{window_height}",
                f"--window-position={WINDOW_X},{WINDOW_Y}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--disable-sync",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-background-networking",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-features=TranslateUI",
                "about:blank",
            ], env={**os.environ, "DISPLAY": ":1"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            time.sleep(3)

            # Find the Chromium window
            wins = _xd("search", "--name", "Chromium")
            if not wins:
                wins = _xd("search", "--name", "chromium")
            if not wins:
                wins = _xd("search", "--name", "Google")

            if wins:
                self._window_id = wins.split("\n")[0].strip()
                _xd("windowactivate", self._window_id)
                # Resize precisely
                _xd("windowsize", self._window_id, window_width, window_height)
                _xd("windowmove", self._window_id, WINDOW_X, WINDOW_Y)
                print(f"[RealBrowser] Window: {self._window_id} size={window_width}x{window_height}", file=sys.stderr, flush=True)
            else:
                print("[RealBrowser] WARNING: could not find Chromium window", file=sys.stderr, flush=True)

            self._cached_info = {"ready": True, "url": "about:blank", "title": ""}
            self._ready.set()

            while self._running:
                try:
                    cmd, params = self._cmd_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if cmd == "_STOP_":
                    break

                result = {"status": "ok", "success": True}
                try:
                    if cmd == "navigate":
                        url = params.get("url", "")
                        # Focus address bar: Ctrl+L
                        _xd("key", "ctrl+l")
                        _human_delay(100, 200)
                        # Clear and type URL
                        _xd("key", "ctrl+a")
                        _human_delay(30, 50)
                        _xd("type", url)
                        _human_delay(100, 200)
                        _xd("key", "Return")
                        _human_delay(500, 1000)
                        self._current_url = url
                        result["success"] = True

                    elif cmd == "click":
                        x, y = params.get("x", 0), params.get("y", 0)
                        # Map content coordinates to screen coordinates
                        screen_x = WINDOW_X + x
                        screen_y = WINDOW_Y + CHROME_HEIGHT + y

                        # Realistic mouse movement
                        steps = random.randint(5, 10)
                        cur_x = WINDOW_X + VIEWPORT_WIDTH // 2
                        cur_y = WINDOW_Y + CHROME_HEIGHT + VIEWPORT_HEIGHT // 2
                        for i in range(steps + 1):
                            t = i / steps
                            eased = t ** 2 * (3 - 2 * t)  # smoothstep
                            mx = int(cur_x + (screen_x - cur_x) * eased)
                            my = int(cur_y + (screen_y - cur_y) * eased)
                            _xd("mousemove", mx, my)
                            time.sleep(random.uniform(0.003, 0.01))

                        # Click with human timing
                        _xd("mousemove", screen_x, screen_y)
                        _human_delay(30, 60)
                        _xd("mousedown", "1")
                        _human_delay(40, 80)
                        _xd("mouseup", "1")
                        _human_delay(50, 100)

                        print(f"[RealBrowser] CLICK ({x},{y}) → screen ({screen_x},{screen_y})", file=sys.stderr, flush=True)
                        result["success"] = True

                    elif cmd == "input":
                        text = params.get("text", "")
                        x = params.get("x", 0)
                        y = params.get("y", 0)
                        # Click to focus first
                        if x > 0 or y > 0:
                            screen_x = WINDOW_X + x
                            screen_y = WINDOW_Y + CHROME_HEIGHT + y
                            _xd("mousemove", screen_x, screen_y)
                            _human_delay(20, 40)
                            _xd("click", "1")
                            _human_delay(100, 200)
                        # Select all and type
                        _xd("key", "ctrl+a")
                        _human_delay(30, 50)
                        _xd("type", text)
                        _human_delay(50, 100)
                        result["success"] = True

                    elif cmd == "scroll":
                        dy = params.get("dy", 300)
                        if dy > 0:
                            _xd("key", "Page_Down")
                        else:
                            _xd("key", "Page_Up")
                        _human_delay(100, 200)
                        result["success"] = True

                    elif cmd == "longpress":
                        x, y = params.get("x", 0), params.get("y", 0)
                        screen_x = WINDOW_X + x
                        screen_y = WINDOW_Y + CHROME_HEIGHT + y
                        _xd("mousemove", screen_x, screen_y)
                        _human_delay(20, 40)
                        _xd("mousedown", "1")
                        time.sleep(params.get("duration", 1000) / 1000)
                        _xd("mouseup", "1")
                        result["success"] = True

                    elif cmd == "drag":
                        x, y = params["x"], params["y"]
                        tx, ty = params.get("tx", x + 100), params.get("ty", y + 100)
                        sx = WINDOW_X + x
                        sy = WINDOW_Y + CHROME_HEIGHT + y
                        ex = WINDOW_X + tx
                        ey = WINDOW_Y + CHROME_HEIGHT + ty
                        _xd("mousemove", sx, sy)
                        _human_delay(20, 40)
                        _xd("mousedown", "1")
                        steps = 15
                        for i in range(1, steps + 1):
                            t = i / steps
                            mx = int(sx + (ex - sx) * t)
                            my = int(sy + (ey - sy) * t)
                            _xd("mousemove", mx, my)
                            time.sleep(0.01)
                        _xd("mouseup", "1")
                        result["success"] = True

                    elif cmd == "back":
                        _xd("key", "Alt+Left")
                        _human_delay(200, 400)
                        result["success"] = True

                    elif cmd == "refresh":
                        _xd("key", "F5")
                        _human_delay(200, 400)
                        result["success"] = True

                    elif cmd == "copy":
                        _xd("key", "ctrl+c")
                        result["success"] = True

                    elif cmd == "paste":
                        _xd("key", "ctrl+v")
                        result["success"] = True

                    elif cmd == "click_js":
                        # Not supported in real browser mode — already real clicks
                        result["success"] = True

                    elif cmd == "click_js_at":
                        result["success"] = True

                    elif cmd == "get_html":
                        result["html"] = "<html></html>"

                    elif cmd == "get_text":
                        result["text"] = ""

                except Exception as e:
                    result = {"status": "error", "error": str(e), "success": False}

                self._result_queue.put(result)

                # Update screenshot cache
                try:
                    b64 = _screenshot_base64()
                    if b64:
                        self._cached_screenshot = b64
                except Exception:
                    pass

        except Exception as e:
            import traceback
            print(f"[RealBrowser] FATAL: {e}\n{traceback.format_exc()}", file=sys.stderr, flush=True)
            self._ready.set()
        finally:
            try:
                subprocess.run(["pkill", "-9", "chromium"], capture_output=True)
            except Exception:
                pass
            self._running = False
