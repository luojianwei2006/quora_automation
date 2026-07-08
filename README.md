# Quora Reply Automation System

A complete automation system for searching and replying to questions on Quora and other forum websites. Features a mobile browser simulator with cursor overlay, action recording/playback engine, and a web management dashboard.

## Features

### 📱 Mobile Browser Simulator
- Playwright-based Android Chrome emulation (Galaxy S23 / iPhone 14 Pro Max)
- Draggable simulated cursor overlay with right-click context menu
- Real-time screenshot streaming
- 12 action types: Click, Long Press, Drag, Input, Paste, Copy, Scroll, Navigate, Wait, Screenshot, Extract Text, Assert

### 🎬 Action Recording & Playback
- Record user actions step by step with configurable parameters
- Edit recorded actions: delay, timeout, completion checks, retries
- Single-step test playback with real-time parameter adjustment
- Full playback with automatic screenshots at each step

### 🖥️ Management Dashboard
- **Dashboard** — stats overview and quick actions
- **Projects** — project CRUD with JSON parameter templates
- **Tasks** — task creation with parameter filling, run with real-time progress
- **Recording Editor** — visual editing of all action parameters
- **ADB Manager** — Android device/emulator connection and control

### 🌐 Internationalization
- Full English (en) and Simplified Chinese (zh) language support
- One-click language switching, persisted via cookie

### 📱 Android App
- WebView-based mobile browser with floating cursor overlay
- Long-press context menu for recording actions
- REST API communication with the management backend
- ADB-deployable

## Project Structure

```
quora-automation/
├── app.py                    # Flask main entry point
├── engine/                   # Python backend engine
│   ├── browser_engine.py     # Thread-safe mobile browser (Playwright)
│   ├── player.py             # Action playback engine
│   ├── models.py             # Data models (Action, Recording)
│   ├── storage.py            # JSON-based data persistence
│   ├── i18n.py               # Internationalization engine
│   └── adb_manager.py        # ADB device management
├── templates/                # Jinja2 HTML templates
│   ├── index.html            # Dashboard
│   ├── browser.html          # Mobile browser simulator
│   ├── recording.html        # Recording editor
│   ├── projects.html         # Project management
│   └── tasks.html            # Task management
├── static/
│   ├── css/style.css         # Dark theme styles
│   ├── js/app.js             # Shared JavaScript (i18n, API helpers)
│   └── lang/                 # Language packs
│       ├── en.json           # English translations
│       └── zh.json           # Chinese translations
├── android-app/              # Android app source (Android Studio)
│   ├── build.gradle
│   ├── settings.gradle
│   ├── gradle.properties
│   └── app/src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/quora/automation/
│       │   ├── ui/MainActivity.java
│       │   ├── recording/
│       │   └── network/
│       └── res/
├── recordings/               # Saved recordings (JSON)
├── screenshots/              # Captured screenshots (PNG)
└── data/                     # Runtime data (auto-created)
```

## Quick Start

### Prerequisites
- Python 3.8+
- Chromium browser (installed automatically by Playwright)
- Android Studio (for Android app only)

### Setup

```bash
# Clone the repository
git clone https://github.com/luojianwei2006/quora_automation.git
cd quora_automation

# Install Python dependencies
pip install -r requirements.txt

# Install Chromium browser
python -m playwright install chromium

# Start the server
python app.py
```

The server starts at `http://localhost:5050` (default port; override with the `PORT` environment variable). Open your browser to start using the system.

### Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Stats overview and quick actions |
| Mobile Browser | `/browser` | Phone simulator with cursor recording |
| Recording Editor | `/recording` | Edit recorded action steps |
| Projects | `/projects` | Project and parameter template management |
| Tasks | `/tasks` | Create and run automation tasks |

### Language Switching

Click the 🌐 button in the top-right corner of any page, or use the API:

```bash
# Switch to Chinese
curl -X POST http://localhost:5050/api/lang/set -H 'Content-Type: application/json' -d '{"lang":"zh"}'

# Switch to English
curl -X POST http://localhost:5050/api/lang/set -H 'Content-Type: application/json' -d '{"lang":"en"}'
```

## Workflow

1. **Create a Project** — define parameter templates (Quora username, search keywords, reply text, etc.)
2. **Record Actions** — use the Mobile Browser to navigate Quora and record your reply workflow
3. **Edit & Refine** — adjust delays, completion checks, and retry logic for each step
4. **Create a Task** — fill in project parameters with actual values
5. **Run** — execute the automation and monitor real-time progress with screenshots

## Action Types

| Type | Description | Parameters |
|------|-------------|------------|
| `click` | Tap at coordinates or on selector | x, y, selector |
| `longpress` | Long press at coordinates | x, y, duration |
| `drag` | Drag from (x,y) to (target_x,target_y) | x, y, target_x, target_y |
| `input` | Type text into field | text, selector, x, y |
| `paste` | Paste text from clipboard | text |
| `copy` | Copy selected text | — |
| `scroll` | Scroll the page | delta_x, delta_y |
| `navigate` | Go to a URL | url |
| `wait` | Wait for specified duration | delay_ms |
| `screenshot` | Capture a screenshot | — |
| `extract` | Extract text from page | selector, description |
| `assert` | Assert a condition | completion_check_type, completion_check_value |

### Completion Checks

| Type | Description |
|------|-------------|
| `url_contains` | Check if URL contains expected string |
| `text_contains` | Check if page text contains expected string |
| `selector_visible` | Check if CSS selector is visible |
| `element_disappeared` | Check if element has disappeared |
| `element_enabled` | Check if element is enabled |

## Android App

Open `android-app/` in Android Studio to build the APK.

**Requirements:**
- Android Studio Hedgehog (2023.1.1) or later
- Gradle 8.0+ (configured in `gradle-wrapper.properties`)
- AGP 8.1.1 (configured in `build.gradle`)
- Android SDK 34 (compileSdk)

The app connects to the Flask backend at `http://10.0.2.2:5050` by default (Android emulator localhost alias). Change this in `ApiClient.java` for physical devices.

### ADB Commands

```bash
# List connected devices
adb devices

# Install APK
adb install -r app-debug.apk

# Launch the app
adb shell am start -n com.quora.automation/.ui.MainActivity

# The backend also provides ADB management via API:
curl http://localhost:5050/api/adb/devices
curl http://localhost:5050/api/adb/status
```

## API Endpoints

| Category | Endpoint | Methods |
|----------|----------|---------|
| Browser | `/api/browser/*` | GET, POST (start/stop/navigate/click/input/scroll/screenshot) |
| Recording | `/api/recording/*` | GET, POST, PUT, DELETE |
| Playback | `/api/play/*` | POST (start/abort/test-step) |
| Projects | `/api/projects/*` | GET, POST, PUT, DELETE |
| Tasks | `/api/tasks/*` | GET, POST, PUT, DELETE, run |
| Language | `/api/lang/set` | POST |
| ADB | `/api/adb/*` | GET, POST |
| Screenshots | `/api/screenshots` | GET |

## License

MIT
