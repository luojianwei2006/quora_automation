"""
Action playback engine.
Executes recorded actions step by step with configurable delays and completion checks.
"""
import time
import json
import os
from typing import Callable, Optional

from engine.models import RecordedAction, Recording, ActionType
from engine.browser_engine import BrowserEngine


class PlaybackResult:
    """Result of a single playback step."""

    def __init__(self, action: RecordedAction, success: bool, index: int):
        self.action = action
        self.success = success
        self.index = index
        self.error: Optional[str] = None
        self.screenshot: Optional[str] = None
        self.duration_ms: float = 0
        self.extracted_text: Optional[str] = None

    def to_dict(self):
        return {
            "index": self.index,
            "action_id": self.action.id,
            "action_type": self.action.type,
            "success": self.success,
            "error": self.error,
            "screenshot": self.screenshot,
            "duration_ms": self.duration_ms,
            "extracted_text": self.extracted_text,
        }


class PlayerEngine:
    """Executes a sequence of recorded actions."""

    def __init__(self, browser: BrowserEngine):
        self.browser = browser
        self._on_step_callback: Optional[Callable] = None
        self._on_error_callback: Optional[Callable] = None
        self._abort_flag = False
        self._current_step = 0
        self._total_steps = 0
        self._results: list[PlaybackResult] = []
        self._screenshot_every_step = True
        self._variable_store: dict = {}  # store extracted values

    def set_callbacks(self, on_step=None, on_error=None):
        """Set callbacks for step execution and errors."""
        self._on_step_callback = on_step
        self._on_error_callback = on_error

    def abort(self):
        """Signal the player to abort."""
        self._abort_flag = True

    @property
    def progress(self) -> float:
        if self._total_steps == 0:
            return 0
        return self._current_step / self._total_steps

    def play_single_step(self, action: RecordedAction, step_index: int = 0) -> PlaybackResult:
        """Execute a single action step and return the result."""
        result = PlaybackResult(action, False, step_index)
        start_time = time.time()

        try:
            # Wait for pre-delay
            if action.delay_ms > 0:
                time.sleep(action.delay_ms / 1000)

            success = False
            error_msg = None
            extracted = None
            screenshot = None

            # Execute based on action type
            if action.type == ActionType.CLICK:
                success = self.browser.execute_click(
                    x=action.x or 0, y=action.y or 0,
                    selector=action.selector
                )
                # Double-insurance: always try JS click as fallback for tough sites
                if action.selector:
                    try:
                        # Query selector click for SPA/React pages
                        self.browser._send_command("click_js", {"selector": action.selector})
                    except Exception:
                        pass
                elif (action.x or action.y):
                    try:
                        # Coordinate-based JS click fallback
                        self.browser._send_command("click_js_at", {
                            "x": action.x, "y": action.y
                        })
                    except Exception:
                        pass

            elif action.type == ActionType.LONG_PRESS:
                success = self.browser.execute_long_press(
                    x=action.x or 0, y=action.y or 0,
                    duration_ms=1000
                )

            elif action.type == ActionType.DRAG:
                success = self.browser.execute_drag(
                    x=action.x or 0, y=action.y or 0,
                    target_x=action.target_x or 0,
                    target_y=action.target_y or 0,
                )

            elif action.type == ActionType.INPUT:
                text = action.text or ""
                # Support variable substitution
                for var_name, var_value in self._variable_store.items():
                    text = text.replace(f"{{{{{var_name}}}}}", str(var_value))
                success = self.browser.execute_input(
                    text=text,
                    selector=action.selector,
                    x=action.x or 0, y=action.y or 0,
                )

            elif action.type == ActionType.SCROLL:
                success = self.browser.execute_scroll(
                    delta_x=action.scroll_delta_x,
                    delta_y=action.scroll_delta_y,
                )

            elif action.type == ActionType.NAVIGATE:
                success = self.browser.execute_navigate(url=action.url or "")

            elif action.type == ActionType.BACK:
                success = self.browser.execute_back()

            elif action.type == ActionType.FORWARD:
                success = self.browser.execute_forward()

            elif action.type == ActionType.REFRESH:
                success = self.browser.execute_refresh()

            elif action.type == ActionType.COPY:
                success = self.browser.execute_copy()

            elif action.type == ActionType.PASTE:
                success = self.browser.execute_paste(text=action.text or "")

            elif action.type == ActionType.EXTRACT:
                extracted = self.browser.execute_extract_text(
                    selector=action.selector or "body"
                )
                if action.description and extracted:
                    self._variable_store[action.description] = extracted
                success = True

            elif action.type == ActionType.SCREENSHOT:
                screenshot = self.browser.get_screenshot()
                success = screenshot is not None

            elif action.type == ActionType.WAIT:
                time.sleep((action.delay_ms or 1000) / 1000)
                success = True

            elif action.type == ActionType.ASSERT:
                # Check if a condition is true
                if action.completion_check_type and action.completion_check_value:
                    success = self.browser.check_completion(
                        action.completion_check_type,
                        action.completion_check_value,
                    )
                else:
                    success = True
            else:
                success = False
                error_msg = f"Unknown action type: {action.type}"

            # Check completion condition
            if success and action.completion_check_type and action.completion_check_value:
                check_ok = self._wait_for_completion(
                    action.completion_check_type,
                    action.completion_check_value,
                    action.timeout_ms,
                )
                if not check_ok:
                    success = False
                    error_msg = f"Completion check failed: {action.completion_check_type}={action.completion_check_value}"

            # Take screenshot after each step
            if self._screenshot_every_step or action.type == ActionType.SCREENSHOT:
                screenshot = self.browser.get_screenshot()

            result.success = success
            result.error = error_msg
            result.screenshot = screenshot
            result.extracted_text = extracted

        except Exception as e:
            result.success = False
            result.error = str(e)
            try:
                result.screenshot = self.browser.get_screenshot()
            except Exception:
                pass

        result.duration_ms = (time.time() - start_time) * 1000
        return result

    def play_recording(
        self,
        recording: Recording,
        start_index: int = 0,
        end_index: Optional[int] = None,
        continue_on_error: bool = False,
    ) -> list[PlaybackResult]:
        """Execute a full recording sequence."""
        self._abort_flag = False
        self._current_step = 0
        self._variable_store = {}
        self._results = []

        actions = recording.actions[start_index:end_index]
        self._total_steps = len(actions)

        for i, action in enumerate(actions):
            if self._abort_flag:
                break

            self._current_step = i + 1
            result = self.play_single_step(action, start_index + i)
            self._results.append(result)

            if self._on_step_callback:
                self._on_step_callback(result, self.progress)

            if not result.success and not continue_on_error:
                if action.retry_on_failure:
                    retried = False
                    for retry in range(action.max_retries):
                        if self._abort_flag:
                            break
                        time.sleep(1)
                        retry_result = self.play_single_step(action, start_index + i)
                        if retry_result.success:
                            self._results[-1] = retry_result
                            retried = True
                            break
                    if not retried:
                        break
                else:
                    break

        return self._results

    def _wait_for_completion(self, check_type: str, check_value: str, timeout_ms: int) -> bool:
        """Wait for a completion condition to be met."""
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if self._abort_flag:
                return False
            if self.browser.check_completion(check_type, check_value):
                return True
            time.sleep(0.5)
        return False

    def get_results_summary(self) -> dict:
        """Get a summary of the playback results."""
        total = len(self._results)
        passed = sum(1 for r in self._results if r.success)
        errors = [r.to_dict() for r in self._results if not r.success]

        return {
            "total_steps": total,
            "passed": passed,
            "failed": total - passed,
            "success_rate": (passed / total * 100) if total > 0 else 0,
            "errors": errors,
            "variables": self._variable_store,
        }
