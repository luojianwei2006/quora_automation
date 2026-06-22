"""
Data models for recorded actions and projects.
"""
import uuid
import json
from datetime import datetime
from enum import Enum
from typing import Optional


class ActionType(str, Enum):
    CLICK = "click"
    LONG_PRESS = "longpress"
    DRAG = "drag"
    INPUT = "input"          # Type text into a field
    COPY = "copy"            # Copy selected text
    PASTE = "paste"          # Paste from clipboard
    SCROLL = "scroll"        # Scroll the page
    NAVIGATE = "navigate"    # Go to a URL
    WAIT = "wait"            # Wait for condition/time
    BACK = "back"            # Browser back
    FORWARD = "forward"      # Browser forward
    REFRESH = "refresh"      # Refresh page
    SCREENSHOT = "screenshot" # Take a screenshot
    EXTRACT = "extract"      # Extract text from page
    ASSERT = "assert"        # Assert a condition


class CompletionCheckType(str, Enum):
    SELECTOR_VISIBLE = "selector_visible"
    URL_CONTAINS = "url_contains"
    TEXT_CONTAINS = "text_contains"
    TIMEOUT = "timeout"
    ELEMENT_ENABLED = "element_enabled"
    ELEMENT_DISAPPEARED = "element_disappeared"


class RecordedAction:
    """A single recorded action step."""

    def __init__(self, action_type: ActionType, **kwargs):
        self.id: str = kwargs.get("id", str(uuid.uuid4())[:8])
        self.type: ActionType = action_type
        self.x: Optional[int] = kwargs.get("x")
        self.y: Optional[int] = kwargs.get("y")
        self.target_x: Optional[int] = kwargs.get("target_x")  # for drag
        self.target_y: Optional[int] = kwargs.get("target_y")
        self.text: Optional[str] = kwargs.get("text", "")
        self.selector: Optional[str] = kwargs.get("selector", "")
        self.scroll_delta_x: int = kwargs.get("scroll_delta_x", 0)
        self.scroll_delta_y: int = kwargs.get("scroll_delta_y", 300)
        self.url: Optional[str] = kwargs.get("url", "")
        self.description: str = kwargs.get("description", "")
        self.delay_ms: int = kwargs.get("delay_ms", 500)       # delay BEFORE this action
        self.timeout_ms: int = kwargs.get("timeout_ms", 10000)  # max wait for completion
        self.completion_check_type: Optional[str] = kwargs.get("completion_check_type")
        self.completion_check_value: Optional[str] = kwargs.get("completion_check_value")
        self.retry_on_failure: bool = kwargs.get("retry_on_failure", False)
        self.max_retries: int = kwargs.get("max_retries", 2)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "text": self.text,
            "selector": self.selector,
            "scroll_delta_x": self.scroll_delta_x,
            "scroll_delta_y": self.scroll_delta_y,
            "url": self.url,
            "description": self.description,
            "delay_ms": self.delay_ms,
            "timeout_ms": self.timeout_ms,
            "completion_check_type": self.completion_check_type,
            "completion_check_value": self.completion_check_value,
            "retry_on_failure": self.retry_on_failure,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            action_type=data["type"],
            id=data.get("id"),
            x=data.get("x"),
            y=data.get("y"),
            target_x=data.get("target_x"),
            target_y=data.get("target_y"),
            text=data.get("text", ""),
            selector=data.get("selector", ""),
            scroll_delta_x=data.get("scroll_delta_x", 0),
            scroll_delta_y=data.get("scroll_delta_y", 300),
            url=data.get("url", ""),
            description=data.get("description", ""),
            delay_ms=data.get("delay_ms", 500),
            timeout_ms=data.get("timeout_ms", 10000),
            completion_check_type=data.get("completion_check_type"),
            completion_check_value=data.get("completion_check_value"),
            retry_on_failure=data.get("retry_on_failure", False),
            max_retries=data.get("max_retries", 2),
        )


class Recording:
    """A complete recording consisting of multiple actions."""

    def __init__(self, name: str = "", project_id: str = ""):
        self.id: str = str(uuid.uuid4())[:8]
        self.name: str = name
        self.project_id: str = project_id
        self.actions: list[RecordedAction] = []
        self.created_at: str = datetime.now().isoformat()
        self.updated_at: str = self.created_at
        self.device: str = "iPhone 14 Pro Max"  # default mobile device
        self.viewport: dict = {"width": 390, "height": 844}

    def add_action(self, action: RecordedAction):
        self.actions.append(action)
        self.updated_at = datetime.now().isoformat()

    def remove_action(self, action_id: str):
        self.actions = [a for a in self.actions if a.id != action_id]
        self.updated_at = datetime.now().isoformat()

    def update_action(self, action_id: str, **kwargs):
        for action in self.actions:
            if action.id == action_id:
                for k, v in kwargs.items():
                    if hasattr(action, k):
                        setattr(action, k, v)
                self.updated_at = datetime.now().isoformat()
                return True
        return False

    def reorder_action(self, action_id: str, new_index: int):
        idx = next((i for i, a in enumerate(self.actions) if a.id == action_id), -1)
        if idx == -1:
            return False
        action = self.actions.pop(idx)
        self.actions.insert(new_index, action)
        self.updated_at = datetime.now().isoformat()
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "project_id": self.project_id,
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "device": self.device,
            "viewport": self.viewport,
        }

    @classmethod
    def from_dict(cls, data: dict):
        recording = cls(name=data.get("name", ""), project_id=data.get("project_id", ""))
        recording.id = data.get("id", recording.id)
        recording.actions = [RecordedAction.from_dict(a) for a in data.get("actions", [])]
        recording.created_at = data.get("created_at", recording.created_at)
        recording.updated_at = data.get("updated_at", recording.updated_at)
        recording.device = data.get("device", recording.device)
        recording.viewport = data.get("viewport", recording.viewport)
        return recording
