"""
Mac desktop browser engine — uses pyautogui for real mouse/keyboard simulation
and a visible Chrome browser. Works natively on macOS.
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

# Detect if we're on macOS
IS_MAC = sys.platform == "darwin"

if IS_MAC:
    import pyautogui
    pyautogui.FAILSAFE = False

VIEWPORT_WIDTH = 369
VIEWPORT_HEIGHT = 828
WINDOW_X = 200
WINDOW_Y = 60
CHROME_HEIGHT = 84  # macOS Chrome title bar + tabs + address bar


def _human_delay(min_ms=20, max_ms=80):
    time.sleep(random.randint(min_ms, max_ms) / 1000.0)


def _mac_screenshot(filepath):
    """Take screenshot of browser content area on macOS."""
    subprocess.run([
        "screencapture", "-x", "-R",
        f"{WINDOW_X},{WINDOW_Y + CHROME_HEIGHT},{VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}",
        filepath
    ], capture_output=True)
    return filepath


def _mac_screenshot_base64():
    path = f"/tmp/mac_browser_shot_{int(time.time()*1000)}.png"
    _mac_screenshot(path)
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def _mac_setup_chrome():
    """Open Chrome with specific window size and position using AppleScript."""
    script = f'''
    tell application "Google Chrome"
        activate
        set bounds of front window to {{{WINDOW_X}, {WINDOW_Y}, {WINDOW_X + VIEWPORT_WIDTH}, {WINDOW_Y + VIEWPORT_HEIGHT + CHROME_HEIGHT}}}
        set URL of active tab of front window to "about:blank"
    end tell
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)
    time.sleep(1.5)


def _mac_navigate(url):
    """Navigate Chrome to URL using AppleScript."""
    script = f'''
    tell application "Google Chrome"
        set URL of active tab of front window to "{url}"
    end tell
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _mac_get_url():
    """Get current Chrome URL."""
    script = '''
    tell application "Google Chrome"
        get URL of active tab of front window
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip()


class MacBrowserEngine:
    """Thread-safe browser engine using pyautogui on macOS."""

    def __init__(self):
        self._profile = {"viewport": {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}}
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._screenshot_dir = os.path.join(root, "screenshots")
        self._cmd_queue = queue.Queue()
        self._result_queue = queue.Queue()
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._running = False
        self._current_url = "about:blank"
        self._cached_screenshot = None
        self._cached_info = {"ready": False, "url": "", "title": ""}

    @property
    def is_running(self):
        return self._running

    def start(self):
        if not IS_MAC:
            raise RuntimeError("MacBrowserEngine requires macOS")
        with self._lock:
            if self._running:
                return
            self._running = True
            self._ready.clear()
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()
        if not self._ready.wait(timeout=15):
            raise RuntimeError("Mac browser failed to start")

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

    # ─── Public API (mirrors BrowserEngine) ──────────────────

    def navigate(self, url):
        self._send_command("navigate", {"url": url})

    def get_screenshot(self):
        return self._cached_screenshot

    def get_page_info(self):
        return self._cached_info

    def execute_click(self, x, y, selector=""):
        r = self._send_command("click", {"x": x, "y": y})
        return r.get("success", False)

    def execute_long_press(self, x, y, duration_ms=1000):
        r = self._send_command("longpress", {"x": x, "y": y, "duration": duration_ms})
        return r.get("success", False)

    def execute_drag(self, x, y, target_x, target_y):
        r = self._send_command("drag", {"x": x, "y": y, "tx": target_x, "ty": target_y})
        return r.get("success", False)

    def execute_input(self, text, selector="", x=0, y=0):
        r = self._send_command("input", {"text": text, "x": x, "y": y})
        return r.get("success", False)

    def execute_scroll(self, delta_x=0, delta_y=300):
        r = self._send_command("scroll", {"dx": delta_x, "dy": delta_y})
        return r.get("success", False)

    def execute_navigate(self, url):
        r = self._send_command("navigate", {"url": url})
        return r.get("success", False)

    def execute_back(self):
        r = self._send_command("back", {})
        return r.get("success", False)

    def execute_refresh(self):
        r = self._send_command("refresh", {})
        return r.get("success", False)

    def execute_copy(self): return True
    def execute_paste(self, text=""): return True
    def get_page_html(self): return ""
    def get_page_text(self): return ""
    def execute_extract_text(self, selector=""): return ""
    def check_completion(self, check_type="", check_value=""): return False
    def get_element_at(self, x, y): return {"tag": "", "text": "", "selector": ""}

    # ─── Main Loop ───────────────────────────────────────────

    def _loop(self):
        try:
            # Setup Chrome window
            _mac_setup_chrome()
            time.sleep(1)

            self._cached_info = {"ready": True, "url": "about:blank", "title": ""}
            self._ready.set()
            print("[MacBrowser] Ready", file=sys.stderr, flush=True)

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
                        _mac_navigate(url)
                        _human_delay(800, 1500)
                        self._current_url = url

                    elif cmd == "click":
                        x, y = params.get("x", 0), params.get("y", 0)
                        screen_x = WINDOW_X + x
                        screen_y = WINDOW_Y + CHROME_HEIGHT + y

                        # Smooth mouse movement
                        steps = random.randint(6, 12)
                        start_x, start_y = pyautogui.position()
                        for i in range(steps + 1):
                            t = i / steps
                            eased = t * t * (3 - 2 * t)
                            mx = int(start_x + (screen_x - start_x) * eased)
                            my = int(start_y + (screen_y - start_y) * eased)
                            pyautogui.moveTo(mx, my)
                            time.sleep(random.uniform(0.002, 0.008))

                        pyautogui.moveTo(screen_x, screen_y)
                        _human_delay(30, 60)
                        pyautogui.mouseDown()
                        _human_delay(40, 80)
                        pyautogui.mouseUp()
                        _human_delay(50, 100)
                        print(f"[MacBrowser] CLICK ({x},{y}) → screen ({screen_x},{screen_y})", file=sys.stderr, flush=True)

                    elif cmd == "input":
                        text = params.get("text", "")
                        x, y = params.get("x", 0), params.get("y", 0)
                        if x > 0 or y > 0:
                            self.execute_click(x, y)
                            _human_delay(100, 200)
                        pyautogui.hotkey("command", "a")
                        _human_delay(30, 50)
                        pyautogui.typewrite(text, interval=random.uniform(0.02, 0.06))

                    elif cmd == "scroll":
                        dy = params.get("dy", 300)
                        if dy > 0:
                            pyautogui.scroll(-abs(dy) // 10)
                        else:
                            pyautogui.scroll(abs(dy) // 10)
                        _human_delay(100, 200)

                    elif cmd == "longpress":
                        x, y = params.get("x", 0), params.get("y", 0)
                        screen_x = WINDOW_X + x
                        screen_y = WINDOW_Y + CHROME_HEIGHT + y
                        pyautogui.moveTo(screen_x, screen_y)
                        _human_delay(20, 40)
                        pyautogui.mouseDown()
                        time.sleep(params.get("duration", 1000) / 1000)
                        pyautogui.mouseUp()

                    elif cmd == "drag":
                        x, y = params["x"], params["y"]
                        tx, ty = params.get("tx", 100), params.get("ty", 100)
                        sx = WINDOW_X + x
                        sy = WINDOW_Y + CHROME_HEIGHT + y
                        ex = WINDOW_X + tx
                        ey = WINDOW_Y + CHROME_HEIGHT + ty
                        pyautogui.moveTo(sx, sy)
                        _human_delay(20, 40)
                        pyautogui.drag(ex - sx, ey - sy, duration=0.3)

                    elif cmd == "back":
                        pyautogui.hotkey("command", "[")
                        _human_delay(200, 400)

                    elif cmd == "refresh":
                        pyautogui.hotkey("command", "r")
                        _human_delay(200, 400)

                    elif cmd in ("click_js", "click_js_at", "get_html", "get_text"):
                        result["success"] = True

                except Exception as e:
                    result = {"status": "error", "error": str(e), "success": False}

                self._result_queue.put(result)

                # Update screenshot
                try:
                    b64 = _mac_screenshot_base64()
                    if b64:
                        self._cached_screenshot = b64
                except Exception:
                    pass

        except Exception as e:
            import traceback
            print(f"[MacBrowser] FATAL: {e}\n{traceback.format_exc()}", file=sys.stderr, flush=True)
            self._ready.set()
        finally:
            self._running = False
