"""
Quora Automation System - Main Flask Application
Web-based mobile browser simulator with recording/playback and management dashboard.
"""
import os
import sys
import json
import threading
import time
from pathlib import Path

os.environ.pop("NODE_OPTIONS", None)

from flask import (
    Flask, render_template, request, jsonify, send_from_directory, Response,
    stream_with_context, make_response
)
from flask_socketio import SocketIO, emit

from engine.browser_engine import BrowserEngine
from engine.models import Recording, RecordedAction, ActionType
from engine.player import PlayerEngine
from engine import storage
from engine.adb_manager import adb_manager
from engine.i18n import I18n, t as _t, SUPPORTED_LANGUAGES

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.urandom(24)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ─── Global browser instance ─────────────────────────────────────
_browser: BrowserEngine = None
_player: PlayerEngine = None
_browser_lock = threading.Lock()
_current_recording: Recording = None
_play_thread: threading.Thread = None


def get_browser() -> BrowserEngine:
    global _browser
    if _browser is None:
        _browser = BrowserEngine()
    return _browser


def get_player() -> PlayerEngine:
    global _player
    if _player is None:
        _player = PlayerEngine(get_browser())
    return _player


def get_or_create_recording(name: str = "Untitled", project_id: str = "") -> Recording:
    global _current_recording
    if _current_recording is None:
        _current_recording = Recording(name=name, project_id=project_id)
    return _current_recording


# ─── Routes ──────────────────────────────────────────────────────

@app.route("/")
def index():
    """Dashboard home page."""
    return render_template("index.html")


@app.route("/test-page")
def test_page_home():
    """Mock forum test page for recording/playback testing."""
    return render_template("test-pages/home.html")


@app.route("/test-page/profile")
def test_page_profile():
    return render_template("test-pages/profile.html")


@app.route("/test-page/settings")
def test_page_settings():
    return render_template("test-pages/settings.html")


@app.route("/browser")
def browser_view():
    """Mobile browser simulator with cursor overlay."""
    return render_template("browser.html")


@app.route("/projects")
def projects_view():
    """Project management page."""
    return render_template("projects.html")


@app.route("/tasks")
def tasks_view():
    """Task management page."""
    return render_template("tasks.html")


@app.route("/recording")
def recording_view():
    """Recording editor page."""
    return render_template("recording.html")


# ─── Browser API ─────────────────────────────────────────────────

@app.route("/api/browser/start", methods=["POST"])
def api_browser_start():
    with _browser_lock:
        try:
            browser = get_browser()
            browser.start()
            info = browser.get_page_info()
            if not info.get("ready"):
                return jsonify({"status": "error", "error": info.get("error", "Browser failed to start"), "debug": info}), 500
            return jsonify({"status": "ok", "info": info})
        except Exception as e:
            import traceback
            return jsonify({"status": "error", "error": str(e), "debug": traceback.format_exc()}), 500


@app.route("/api/browser/stop", methods=["POST"])
def api_browser_stop():
    global _browser
    with _browser_lock:
        try:
            if _browser:
                _browser.close()
                _browser = None
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/browser/status", methods=["GET"])
def api_browser_status():
    with _browser_lock:
        try:
            browser = get_browser()
            info = browser.get_page_info()
            return jsonify({"status": "ok", "info": info})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})


@app.route("/api/browser/navigate", methods=["POST"])
def api_browser_navigate():
    data = request.get_json() or {}
    url = data.get("url", "")
    with _browser_lock:
        try:
            browser = get_browser()
            browser.navigate(url)
            info = browser.get_page_info()
            screenshot = browser.get_screenshot()
            return jsonify({"status": "ok", "info": info, "screenshot": screenshot})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/browser/back", methods=["POST"])
def api_browser_back():
    with _browser_lock:
        try:
            browser = get_browser()
            success = browser.execute_back()
            info = browser.get_page_info()
            screenshot = browser.get_screenshot()
            return jsonify({"status": "ok", "success": success, "info": info, "screenshot": screenshot})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/browser/screenshot", methods=["GET"])
def api_browser_screenshot():
    with _browser_lock:
        try:
            browser = get_browser()
            screenshot = browser.get_screenshot()
            return jsonify({"status": "ok", "screenshot": screenshot})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})


@app.route("/api/browser/click", methods=["POST"])
def api_browser_click():
    data = request.get_json() or {}
    x = data.get("x", 0)
    y = data.get("y", 0)
    print(f"[API] CLICK x={x} y={y}", file=sys.stderr, flush=True)
    with _browser_lock:
        try:
            browser = get_browser()
            success = browser.execute_click(x=x, y=y, selector=data.get("selector", ""))
            screenshot = browser.get_screenshot()
            print(f"[API] CLICK done success={success}", file=sys.stderr, flush=True)
            return jsonify({"status": "ok", "success": success, "screenshot": screenshot})
        except Exception as e:
            print(f"[API] CLICK error: {e}", file=sys.stderr, flush=True)
            return jsonify({"status": "error", "error": str(e)}), 500
@app.route("/api/browser/longpress", methods=["POST"])
def api_browser_longpress():
    data = request.get_json() or {}
    with _browser_lock:
        try:
            browser = get_browser()
            success = browser.execute_long_press(
                x=data.get("x", 0), y=data.get("y", 0),
            )
            screenshot = browser.get_screenshot()
            return jsonify({"status": "ok", "success": success, "screenshot": screenshot})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})


@app.route("/api/browser/drag", methods=["POST"])
def api_browser_drag():
    data = request.get_json() or {}
    with _browser_lock:
        try:
            browser = get_browser()
            success = browser.execute_drag(
                x=data.get("x", 0), y=data.get("y", 0),
                target_x=data.get("target_x", 0), target_y=data.get("target_y", 0),
            )
            screenshot = browser.get_screenshot()
            return jsonify({"status": "ok", "success": success, "screenshot": screenshot})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})


@app.route("/api/browser/input", methods=["POST"])
def api_browser_input():
    data = request.get_json() or {}
    with _browser_lock:
        try:
            browser = get_browser()
            success = browser.execute_input(
                text=data.get("text", ""),
                selector=data.get("selector", ""),
                x=data.get("x", 0), y=data.get("y", 0),
            )
            screenshot = browser.get_screenshot()
            return jsonify({"status": "ok", "success": success, "screenshot": screenshot})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})


@app.route("/api/browser/scroll", methods=["POST"])
def api_browser_scroll():
    data = request.get_json() or {}
    with _browser_lock:
        try:
            browser = get_browser()
            success = browser.execute_scroll(
                delta_x=data.get("delta_x", 0), delta_y=data.get("delta_y", 300),
            )
            screenshot = browser.get_screenshot()
            return jsonify({"status": "ok", "success": success, "screenshot": screenshot})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})


@app.route("/api/browser/element", methods=["POST"])
def api_browser_element():
    data = request.get_json() or {}
    with _browser_lock:
        try:
            browser = get_browser()
            info = browser.get_element_at(x=data.get("x", 0), y=data.get("y", 0))
            return jsonify({"status": "ok", "element": info})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})


@app.route("/api/browser/pageinfo", methods=["GET"])
def api_browser_pageinfo():
    with _browser_lock:
        try:
            browser = get_browser()
            info = browser.get_page_info()
            return jsonify({"status": "ok", "info": info})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)})


# ─── Recording API ───────────────────────────────────────────────

@app.route("/api/recording/current", methods=["GET"])
def api_recording_current():
    recording = get_or_create_recording()
    return jsonify({"status": "ok", "recording": recording.to_dict()})


@app.route("/api/recording/new", methods=["POST"])
def api_recording_new():
    global _current_recording
    data = request.get_json() or {}
    _current_recording = Recording(
        name=data.get("name", "Untitled"),
        project_id=data.get("project_id", ""),
    )
    return jsonify({"status": "ok", "recording": _current_recording.to_dict()})


@app.route("/api/recording/add-action", methods=["POST"])
def api_recording_add_action():
    global _current_recording
    data = request.get_json() or {}
    recording = get_or_create_recording()

    action = RecordedAction(
        action_type=data.get("type", "click"),
        x=data.get("x"),
        y=data.get("y"),
        target_x=data.get("target_x"),
        target_y=data.get("target_y"),
        text=data.get("text", ""),
        selector=data.get("selector", ""),
        url=data.get("url", ""),
        description=data.get("description", ""),
        delay_ms=data.get("delay_ms", 500),
        timeout_ms=data.get("timeout_ms", 10000),
        completion_check_type=data.get("completion_check_type"),
        completion_check_value=data.get("completion_check_value"),
        scroll_delta_x=data.get("scroll_delta_x", 0),
        scroll_delta_y=data.get("scroll_delta_y", 300),
    )
    recording.add_action(action)
    return jsonify({"status": "ok", "action": action.to_dict(), "recording": recording.to_dict()})


@app.route("/api/recording/update-action/<action_id>", methods=["PUT"])
def api_recording_update_action(action_id):
    recording = get_or_create_recording()
    data = request.get_json() or {}
    success = recording.update_action(action_id, **data)
    return jsonify({"status": "ok" if success else "error", "recording": recording.to_dict()})


@app.route("/api/recording/remove-action/<action_id>", methods=["DELETE"])
def api_recording_remove_action(action_id):
    recording = get_or_create_recording()
    recording.remove_action(action_id)
    return jsonify({"status": "ok", "recording": recording.to_dict()})


@app.route("/api/recording/reorder-action/<action_id>", methods=["PUT"])
def api_recording_reorder_action(action_id):
    recording = get_or_create_recording()
    data = request.get_json() or {}
    success = recording.reorder_action(action_id, data.get("new_index", 0))
    return jsonify({"status": "ok" if success else "error", "recording": recording.to_dict()})


@app.route("/api/recording/save", methods=["POST"])
def api_recording_save():
    recording = get_or_create_recording()
    data = request.get_json() or {}
    if data.get("name"):
        recording.name = data["name"]
    if data.get("project_id"):
        recording.project_id = data["project_id"]

    storage.save_recording(recording)
    return jsonify({"status": "ok", "recording": recording.to_dict()})


@app.route("/api/recording/load/<recording_id>", methods=["GET"])
def api_recording_load(recording_id):
    global _current_recording
    recording = storage.load_recording(recording_id)
    if recording:
        _current_recording = recording
        return jsonify({"status": "ok", "recording": recording.to_dict()})
    return jsonify({"status": "error", "error": "Recording not found"}), 404


@app.route("/api/recordings", methods=["GET"])
def api_recordings_list():
    project_id = request.args.get("project_id", "")
    recordings = storage.list_recordings(project_id)
    return jsonify({"status": "ok", "recordings": recordings})


@app.route("/api/recording/delete/<recording_id>", methods=["DELETE"])
def api_recording_delete(recording_id):
    success = storage.delete_recording(recording_id)
    return jsonify({"status": "ok" if success else "error"})


# ─── Playback API ────────────────────────────────────────────────

@app.route("/api/play/test-step", methods=["POST"])
def api_play_test_step():
    """Execute a single action step for testing."""
    data = request.get_json() or {}
    action = RecordedAction.from_dict(data)

    with _browser_lock:
        try:
            player = get_player()
            result = player.play_single_step(action, 0)
            return jsonify({"status": "ok", "result": result.to_dict()})
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/play/start", methods=["POST"])
def api_play_start():
    """Start full recording playback."""
    global _play_thread
    data = request.get_json() or {}
    recording_id = data.get("recording_id", "")

    if recording_id:
        recording = storage.load_recording(recording_id)
    else:
        recording = get_or_create_recording()

    if not recording or not recording.actions:
        return jsonify({"status": "error", "error": "No actions to play"}), 400

    continue_on_error = data.get("continue_on_error", False)

    def playback_worker():
        socketio.emit("playback:start", {"total": len(recording.actions)})
        with _browser_lock:
            try:
                player = get_player()
                player._screenshot_every_step = True

                def on_step(result, progress):
                    socketio.emit("playback:step", {
                        "result": result.to_dict(),
                        "progress": progress,
                        "step": result.index + 1,
                        "total": len(recording.actions),
                    })

                player.set_callbacks(on_step=on_step)
                results = player.play_recording(
                    recording,
                    continue_on_error=continue_on_error,
                )
                summary = player.get_results_summary()
                socketio.emit("playback:complete", {"summary": summary})
            except Exception as e:
                socketio.emit("playback:error", {"error": str(e)})

    _play_thread = threading.Thread(target=playback_worker, daemon=True)
    _play_thread.start()
    return jsonify({"status": "ok", "message": "Playback started"})


@app.route("/api/play/abort", methods=["POST"])
def api_play_abort():
    player = get_player()
    player.abort()
    return jsonify({"status": "ok", "message": "Playback aborted"})


# ─── Projects API ────────────────────────────────────────────────

@app.route("/api/projects", methods=["GET"])
def api_projects_list():
    projects = storage.list_projects()
    return jsonify({"status": "ok", "projects": projects})


@app.route("/api/projects", methods=["POST"])
def api_project_create():
    data = request.get_json() or {}
    param_template = data.get("param_template", storage.get_default_param_template())
    project = storage.create_project(
        name=data.get("name", "New Project"),
        description=data.get("description", ""),
        param_template=param_template,
    )
    return jsonify({"status": "ok", "project": project})


@app.route("/api/projects/<project_id>", methods=["GET"])
def api_project_get(project_id):
    project = storage.get_project(project_id)
    if project:
        return jsonify({"status": "ok", "project": project})
    return jsonify({"status": "error", "error": "Not found"}), 404


@app.route("/api/projects/<project_id>", methods=["PUT"])
def api_project_update(project_id):
    data = request.get_json() or {}
    project = storage.update_project(project_id, **data)
    if project:
        return jsonify({"status": "ok", "project": project})
    return jsonify({"status": "error", "error": "Not found"}), 404


@app.route("/api/projects/<project_id>", methods=["DELETE"])
def api_project_delete(project_id):
    success = storage.delete_project(project_id)
    return jsonify({"status": "ok" if success else "error"})


@app.route("/api/projects/default-template", methods=["GET"])
def api_project_default_template():
    return jsonify({
        "status": "ok",
        "template": storage.get_default_param_template(),
    })


# ─── Tasks API ───────────────────────────────────────────────────

@app.route("/api/tasks", methods=["GET"])
def api_tasks_list():
    tasks = storage.list_tasks()
    # Enrich with project info
    for task in tasks:
        project = storage.get_project(task.get("project_id", ""))
        if project:
            task["project_name"] = project.get("name", "")
            task["param_template"] = project.get("param_template", {})
    return jsonify({"status": "ok", "tasks": tasks})


@app.route("/api/tasks", methods=["POST"])
def api_task_create():
    data = request.get_json() or {}
    task = storage.create_task(
        name=data.get("name", "New Task"),
        project_id=data.get("project_id", ""),
        params=data.get("params", {}),
    )
    return jsonify({"status": "ok", "task": task})


@app.route("/api/tasks/<task_id>", methods=["GET"])
def api_task_get(task_id):
    task = storage.get_task(task_id)
    if task:
        # Enrich with project info
        project = storage.get_project(task.get("project_id", ""))
        if project:
            task["project_name"] = project.get("name", "")
            task["param_template"] = project.get("param_template", {})
        return jsonify({"status": "ok", "task": task})
    return jsonify({"status": "error", "error": "Not found"}), 404


@app.route("/api/tasks/<task_id>", methods=["PUT"])
def api_task_update(task_id):
    data = request.get_json() or {}
    task = storage.update_task(task_id, **data)
    if task:
        return jsonify({"status": "ok", "task": task})
    return jsonify({"status": "error", "error": "Not found"}), 404


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def api_task_delete(task_id):
    success = storage.delete_task(task_id)
    return jsonify({"status": "ok" if success else "error"})


@app.route("/api/tasks/<task_id>/run", methods=["POST"])
def api_task_run(task_id):
    """Run a task: load recording from project and execute playback."""
    task = storage.get_task(task_id)
    if not task:
        return jsonify({"status": "error", "error": "Task not found"}), 404

    project = storage.get_project(task.get("project_id", ""))
    if not project:
        return jsonify({"status": "error", "error": "Project not found"}), 404

    recordings = project.get("recordings", [])
    if not recordings:
        return jsonify({"status": "error", "error": "No recordings in project"}), 400

    # Load the first recording
    recording = storage.load_recording(recordings[-1])
    if not recording:
        return jsonify({"status": "error", "error": "Recording not found"}), 404

    # Merge task params into variable store
    task_params = task.get("params", {})

    global _play_thread

    def task_worker():
        socketio.emit("task:start", {"task_id": task_id, "total": len(recording.actions)})
        with _browser_lock:
            try:
                browser = get_browser()
                browser.start()
                player = get_player()
                player._screenshot_every_step = True
                player._variable_store.update(task_params)

                def on_step(result, progress):
                    socketio.emit("task:step", {
                        "task_id": task_id,
                        "result": result.to_dict(),
                        "progress": progress,
                    })

                player.set_callbacks(on_step=on_step)
                results = player.play_recording(recording)
                summary = player.get_results_summary()

                # Update task status
                storage.update_task(
                    task_id,
                    status="completed" if summary["failed"] == 0 else "failed",
                    results=[r.to_dict() for r in results],
                )
                socketio.emit("task:complete", {
                    "task_id": task_id,
                    "summary": summary,
                })
            except Exception as e:
                storage.update_task(task_id, status="failed")
                socketio.emit("task:error", {"task_id": task_id, "error": str(e)})

    storage.update_task(task_id, status="running")
    _play_thread = threading.Thread(target=task_worker, daemon=True)
    _play_thread.start()
    return jsonify({"status": "ok", "message": "Task started"})


# ─── Screenshots API ─────────────────────────────────────────────

@app.route("/api/screenshots", methods=["GET"])
def api_screenshots_list():
    screenshots = storage.list_screenshots()
    return jsonify({"status": "ok", "screenshots": screenshots})


@app.route("/screenshots/<filename>")
def screenshot_file(filename):
    return send_from_directory(storage.SCREENSHOTS_DIR, filename)


# ─── Socket.IO Events ───────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    emit("connected", {"message": "Connected to automation server"})


@socketio.on("browser:click")
def handle_browser_click(data):
    """Handle click from the browser cursor overlay."""
    with _browser_lock:
        try:
            browser = get_browser()
            success = browser.execute_click(
                x=data.get("x", 0), y=data.get("y", 0)
            )
            screenshot = browser.get_screenshot()
            element = browser.get_element_at(x=data.get("x", 0), y=data.get("y", 0))
            emit("browser:update", {
                "success": success,
                "screenshot": screenshot,
                "element": element,
            })
        except Exception as e:
            emit("browser:error", {"error": str(e)})


@socketio.on("browser:rightclick")
def handle_browser_rightclick(data):
    """Handle right-click on cursor overlay."""
    with _browser_lock:
        try:
            browser = get_browser()
            element = browser.get_element_at(x=data.get("x", 0), y=data.get("y", 0))
            emit("browser:element_info", {
                "x": data.get("x", 0),
                "y": data.get("y", 0),
                "element": element,
            })
        except Exception as e:
            emit("browser:error", {"error": str(e)})


@socketio.on("browser:screenshot")
def handle_browser_screenshot():
    with _browser_lock:
        try:
            browser = get_browser()
            screenshot = browser.get_screenshot()
            emit("browser:screenshot_result", {"screenshot": screenshot})
        except Exception as e:
            emit("browser:error", {"error": str(e)})


# ─── I18n / Language Support ────────────────────────────────────

@app.context_processor
def inject_i18n():
    """Inject translation function and language info into all templates."""
    lang = request.cookies.get("lang", "en")
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    i18n = I18n(lang)
    return {
        "t": i18n.translate,
        "current_lang": lang,
        "supported_languages": SUPPORTED_LANGUAGES,
    }


@app.route("/api/lang/set", methods=["POST"])
def api_lang_set():
    """Set language preference via cookie."""
    data = request.get_json() or {}
    lang = data.get("lang", "en")
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    resp = make_response(jsonify({"status": "ok", "lang": lang}))
    resp.set_cookie("lang", lang, max_age=365*24*3600)  # 1 year
    return resp


# ─── ADB Management API ─────────────────────────────────────────

@app.route("/api/adb/devices", methods=["GET"])
def api_adb_devices():
    """List connected Android devices/emulators."""
    try:
        devices = adb_manager.list_devices()
        return jsonify({"status": "ok", "devices": devices})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


@app.route("/api/adb/device-info", methods=["GET"])
def api_adb_device_info():
    """Get detailed info about a device."""
    device_id = request.args.get("device_id", "")
    try:
        info = adb_manager.get_device_info(device_id)
        return jsonify({"status": "ok", "info": info})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


@app.route("/api/adb/set-default-device", methods=["POST"])
def api_adb_set_default():
    """Set the default ADB device."""
    data = request.get_json() or {}
    device_id = data.get("device_id", "")
    adb_manager.set_default_device(device_id)
    return jsonify({"status": "ok"})


@app.route("/api/adb/launch-app", methods=["POST"])
def api_adb_launch_app():
    """Launch the automation app on device."""
    data = request.get_json() or {}
    success = adb_manager.launch_app(
        package=data.get("package", "com.quora.automation"),
        activity=data.get("activity", ".ui.MainActivity"),
        device=data.get("device_id", ""),
    )
    return jsonify({"status": "ok" if success else "error"})


@app.route("/api/adb/stop-app", methods=["POST"])
def api_adb_stop_app():
    """Stop the automation app on device."""
    data = request.get_json() or {}
    success = adb_manager.stop_app(
        package=data.get("package", "com.quora.automation"),
        device=data.get("device_id", ""),
    )
    return jsonify({"status": "ok" if success else "error"})


@app.route("/api/adb/install-app", methods=["POST"])
def api_adb_install_app():
    """Install APK on device."""
    data = request.get_json() or {}
    apk_path = data.get("apk_path", "")
    if not os.path.exists(apk_path):
        return jsonify({"status": "error", "error": "APK file not found"}), 404
    success = adb_manager.install_app(apk_path, data.get("device_id", ""))
    return jsonify({"status": "ok" if success else "error"})


@app.route("/api/adb/tap", methods=["POST"])
def api_adb_tap():
    """Simulate a tap on the device."""
    data = request.get_json() or {}
    success = adb_manager.input_tap(
        x=data.get("x", 0), y=data.get("y", 0),
        device=data.get("device_id", ""),
    )
    return jsonify({"status": "ok" if success else "error"})


@app.route("/api/adb/swipe", methods=["POST"])
def api_adb_swipe():
    """Simulate a swipe on the device."""
    data = request.get_json() or {}
    success = adb_manager.input_swipe(
        x1=data.get("x1", 0), y1=data.get("y1", 0),
        x2=data.get("x2", 0), y2=data.get("y2", 0),
        duration_ms=data.get("duration_ms", 300),
        device=data.get("device_id", ""),
    )
    return jsonify({"status": "ok" if success else "error"})


@app.route("/api/adb/text", methods=["POST"])
def api_adb_text():
    """Input text on the device."""
    data = request.get_json() or {}
    success = adb_manager.input_text(
        text=data.get("text", ""),
        device=data.get("device_id", ""),
    )
    return jsonify({"status": "ok" if success else "error"})


@app.route("/api/adb/screenshot", methods=["POST"])
def api_adb_screenshot():
    """Take a screenshot from the device."""
    data = request.get_json() or {}
    path = adb_manager.take_screenshot(device=data.get("device_id", ""))
    if path:
        return jsonify({"status": "ok", "path": path})
    return jsonify({"status": "error", "error": "Screenshot failed"}), 500


@app.route("/api/adb/status", methods=["GET"])
def api_adb_status():
    """Get ADB and app status."""
    try:
        devices = adb_manager.list_devices()
        app_status = "unknown"
        if devices:
            app_status = adb_manager.get_app_status()
        return jsonify({
            "status": "ok",
            "devices": devices,
            "app_status": app_status,
            "default_device": adb_manager.get_default_device(),
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})


# ─── Main ────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(storage.DATA_DIR, exist_ok=True)
    port = int(os.environ.get("PORT", 5050))
    print("=" * 60)
    print("  Quora Automation System")
    print(f"  Management Dashboard: http://0.0.0.0:{port}")
    print(f"  Mobile Browser View:  http://0.0.0.0:{port}/browser")
    print("=" * 60)
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
