"""
Storage management for projects, recordings, and tasks.
Persists data as JSON files on disk.
"""
import json
import os
import uuid
import shutil
from datetime import datetime
from typing import Optional

from engine.models import Recording, RecordedAction, ActionType


# Project root = parent of engine/ directory
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_PROJECT_ROOT, "data")
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")
TASKS_DIR = os.path.join(DATA_DIR, "tasks")
SCREENSHOTS_DIR = os.path.join(_PROJECT_ROOT, "screenshots")


def _ensure_dirs():
    for d in [DATA_DIR, PROJECTS_DIR, RECORDINGS_DIR, TASKS_DIR, SCREENSHOTS_DIR]:
        os.makedirs(d, exist_ok=True)


def _load_json(filepath: str) -> dict:
    if not os.path.exists(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(filepath: str, data: dict):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Project Management ──────────────────────────────────────────

def list_projects() -> list[dict]:
    _ensure_dirs()
    projects = []
    for fname in sorted(os.listdir(PROJECTS_DIR)):
        if fname.endswith(".json"):
            data = _load_json(os.path.join(PROJECTS_DIR, fname))
            if data:
                projects.append(data)
    return projects


def get_project(project_id: str) -> Optional[dict]:
    _ensure_dirs()
    return _load_json(os.path.join(PROJECTS_DIR, f"{project_id}.json")) or None


def create_project(name: str, description: str = "", param_template: dict = None,
                   target_url: str = "", keywords: str = "") -> dict:
    _ensure_dirs()
    project = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "description": description,
        "target_url": target_url,
        "keywords": keywords,
        "param_template": param_template or {},
        "recordings": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save_json(os.path.join(PROJECTS_DIR, f"{project['id']}.json"), project)
    return project


def update_project(project_id: str, **kwargs) -> Optional[dict]:
    project = get_project(project_id)
    if not project:
        return None
    for k, v in kwargs.items():
        if k in ("name", "description", "param_template", "target_url", "keywords"):
            project[k] = v
    project["updated_at"] = datetime.now().isoformat()
    _save_json(os.path.join(PROJECTS_DIR, f"{project_id}.json"), project)
    return project


def delete_project(project_id: str) -> bool:
    fp = os.path.join(PROJECTS_DIR, f"{project_id}.json")
    if os.path.exists(fp):
        os.remove(fp)
        return True
    return False


# ─── Recording Management ────────────────────────────────────────

def save_recording(recording: Recording):
    _ensure_dirs()
    filepath = os.path.join(RECORDINGS_DIR, f"{recording.id}.json")
    _save_json(filepath, recording.to_dict())

    # Link to project if applicable
    if recording.project_id:
        project = get_project(recording.project_id)
        if project:
            if recording.id not in project.get("recordings", []):
                project.setdefault("recordings", []).append(recording.id)
                project["updated_at"] = datetime.now().isoformat()
                _save_json(os.path.join(PROJECTS_DIR, f"{project['id']}.json"), project)


def load_recording(recording_id: str) -> Optional[Recording]:
    _ensure_dirs()
    data = _load_json(os.path.join(RECORDINGS_DIR, f"{recording_id}.json"))
    if not data:
        return None
    return Recording.from_dict(data)


def list_recordings(project_id: str = "") -> list[dict]:
    _ensure_dirs()
    recordings = []
    for fname in sorted(os.listdir(RECORDINGS_DIR)):
        if fname.endswith(".json"):
            data = _load_json(os.path.join(RECORDINGS_DIR, fname))
            if data and (not project_id or data.get("project_id") == project_id):
                recordings.append(data)
    return recordings


def delete_recording(recording_id: str) -> bool:
    fp = os.path.join(RECORDINGS_DIR, f"{recording_id}.json")
    if os.path.exists(fp):
        data = _load_json(fp)
        os.remove(fp)
        # Remove from project
        if data and data.get("project_id"):
            project = get_project(data["project_id"])
            if project and recording_id in project.get("recordings", []):
                project["recordings"].remove(recording_id)
                project["updated_at"] = datetime.now().isoformat()
                _save_json(os.path.join(PROJECTS_DIR, f"{project['id']}.json"), project)
        return True
    return False


# ─── Task Management ─────────────────────────────────────────────

def list_tasks() -> list[dict]:
    _ensure_dirs()
    tasks = []
    for fname in sorted(os.listdir(TASKS_DIR)):
        if fname.endswith(".json"):
            data = _load_json(os.path.join(TASKS_DIR, fname))
            if data:
                tasks.append(data)
    return tasks


def get_task(task_id: str) -> Optional[dict]:
    _ensure_dirs()
    return _load_json(os.path.join(TASKS_DIR, f"{task_id}.json")) or None


def create_task(name: str, project_id: str, params: dict = None) -> dict:
    _ensure_dirs()
    task = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "project_id": project_id,
        "params": params or {},
        "status": "pending",  # pending | running | completed | failed
        "results": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _save_json(os.path.join(TASKS_DIR, f"{task['id']}.json"), task)
    return task


def update_task(task_id: str, **kwargs) -> Optional[dict]:
    task = get_task(task_id)
    if not task:
        return None
    for k, v in kwargs.items():
        if k in ("name", "params", "status", "results"):
            task[k] = v
    task["updated_at"] = datetime.now().isoformat()
    _save_json(os.path.join(TASKS_DIR, f"{task_id}.json"), task)
    return task


def delete_task(task_id: str) -> bool:
    fp = os.path.join(TASKS_DIR, f"{task_id}.json")
    if os.path.exists(fp):
        os.remove(fp)
        return True
    return False


# ─── Screenshot Management ──────────────────────────────────────

def list_screenshots(limit: int = 50) -> list[dict]:
    _ensure_dirs()
    screenshots = []
    for fname in sorted(os.listdir(SCREENSHOTS_DIR), reverse=True):
        if fname.endswith(".png"):
            fp = os.path.join(SCREENSHOTS_DIR, fname)
            stat = os.stat(fp)
            screenshots.append({
                "filename": fname,
                "path": fp,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
            if len(screenshots) >= limit:
                break
    return screenshots


def get_default_param_template() -> dict:
    """Default parameter template with common automation parameters."""
    return {
        "search_keyword": {
            "label": "Search Keyword",
            "type": "text",
            "default": "",
            "required": True,
            "description": "Keyword to search for",
        },
        "reply_text": {
            "label": "Reply Content",
            "type": "textarea",
            "default": "",
            "required": False,
            "description": "The reply text to post",
        },
        "username": {
            "label": "Username",
            "type": "text",
            "default": "",
            "required": False,
            "description": "Login username or email",
        },
        "password": {
            "label": "Password",
            "type": "password",
            "default": "",
            "required": False,
            "description": "Login password",
        },
        "max_pages": {
            "label": "Max Pages",
            "type": "number",
            "default": "3",
            "required": False,
            "description": "Maximum pages to process",
        },
        "delay_seconds": {
            "label": "Delay (seconds)",
            "type": "number",
            "default": "2",
            "required": False,
            "description": "Wait time between actions",
        },
    }
