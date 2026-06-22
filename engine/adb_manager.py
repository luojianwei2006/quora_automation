"""
ADB (Android Debug Bridge) Manager.
Handles connection to Android emulators and physical devices for
deploying and controlling the mobile browser app.
"""
import subprocess
import re
import time
import json
import os
from typing import Optional


class ADBManager:
    """Manages ADB connections to Android devices/emulators."""

    def __init__(self, adb_path: str = "adb"):
        self.adb_path = adb_path
        self._connected_devices: list[dict] = []
        self._default_device: Optional[str] = None

    def _run_adb(self, args: list[str], device: str = "") -> tuple[str, str]:
        """Run an ADB command."""
        cmd = [self.adb_path]
        if device:
            cmd.extend(["-s", device])
        cmd.extend(args)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return "", "Timeout"
        except FileNotFoundError:
            return "", f"ADB not found at {self.adb_path}"
        except Exception as e:
            return "", str(e)

    def list_devices(self) -> list[dict]:
        """List all connected Android devices/emulators."""
        stdout, stderr = self._run_adb(["devices", "-l"])
        if stderr and "error" in stderr.lower():
            return []

        devices = []
        for line in stdout.split("\n")[1:]:  # Skip "List of devices attached"
            line = line.strip()
            if not line or "offline" in line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                device_id = parts[0]
                status = parts[1]
                info = {}
                for p in parts[2:]:
                    if ":" in p:
                        k, v = p.split(":", 1)
                        info[k] = v

                devices.append({
                    "id": device_id,
                    "status": status,
                    "model": info.get("model", "Unknown"),
                    "product": info.get("product", ""),
                    "device": info.get("device", ""),
                    "transport_id": info.get("transport_id", ""),
                })

        self._connected_devices = devices
        if devices and not self._default_device:
            self._default_device = devices[0]["id"]

        return devices

    def get_device_info(self, device: str = "") -> dict:
        """Get detailed information about a device."""
        device = device or self._default_device
        if not device:
            return {"error": "No device specified"}

        info = {}
        props = [
            ("ro.product.model", "model"),
            ("ro.product.manufacturer", "manufacturer"),
            ("ro.build.version.release", "android_version"),
            ("ro.build.version.sdk", "sdk_version"),
            ("ro.product.cpu.abi", "abi"),
            ("persist.sys.locale", "locale"),
            ("ro.screenresolution", "resolution"),
        ]

        for prop, key in props:
            stdout, _ = self._run_adb(["shell", "getprop", prop], device)
            if stdout:
                info[key] = stdout

        # Get screen size
        stdout, _ = self._run_adb(["shell", "wm", "size"], device)
        if stdout:
            info["resolution"] = stdout.replace("Physical size: ", "").strip()

        # Get battery
        stdout, _ = self._run_adb(["shell", "dumpsys", "battery"], device)
        if stdout:
            for line in stdout.split("\n"):
                line = line.strip()
                if "level" in line:
                    info["battery"] = line.split(":")[-1].strip()
                    break

        info["device_id"] = device
        return info

    def install_app(self, apk_path: str, device: str = "") -> bool:
        """Install an APK on the device."""
        device = device or self._default_device
        if not device:
            return False

        stdout, stderr = self._run_adb(["install", "-r", apk_path], device)
        return "Success" in stdout

    def uninstall_app(self, package: str = "com.quora.automation", device: str = "") -> bool:
        """Uninstall the app from device."""
        device = device or self._default_device
        if not device:
            return False

        stdout, stderr = self._run_adb(["uninstall", package], device)
        return "Success" in stdout

    def launch_app(self, package: str = "com.quora.automation",
                   activity: str = ".ui.MainActivity", device: str = "") -> bool:
        """Launch the automation app on device."""
        device = device or self._default_device
        if not device:
            return False

        stdout, stderr = self._run_adb(
            ["shell", "am", "start", "-n", f"{package}/{activity}"], device
        )
        return "Error" not in stdout and "Error" not in stderr

    def stop_app(self, package: str = "com.quora.automation", device: str = "") -> bool:
        """Force stop the app."""
        device = device or self._default_device
        if not device:
            return False

        stdout, _ = self._run_adb(["shell", "am", "force-stop", package], device)
        return True

    def take_screenshot(self, device: str = "") -> Optional[str]:
        """Take a screenshot from the device and save to screenshots dir."""
        device = device or self._default_device
        if not device:
            return None

        timestamp = int(time.time() * 1000)
        remote_path = f"/sdcard/screenshot_{timestamp}.png"
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_path = os.path.join(root, "screenshots", f"device_{timestamp}.png")

        # Take screenshot on device
        self._run_adb(["shell", "screencap", "-p", remote_path], device)

        # Pull to local
        stdout, stderr = self._run_adb(["pull", remote_path, local_path], device)

        # Clean up remote
        self._run_adb(["shell", "rm", remote_path], device)

        if os.path.exists(local_path):
            return local_path
        return None

    def input_tap(self, x: int, y: int, device: str = "") -> bool:
        """Simulate a tap on the device at specified coordinates."""
        device = device or self._default_device
        if not device:
            return False

        stdout, _ = self._run_adb(["shell", "input", "tap", str(x), str(y)], device)
        return True

    def input_swipe(self, x1: int, y1: int, x2: int, y2: int,
                    duration_ms: int = 300, device: str = "") -> bool:
        """Simulate a swipe/drag on the device."""
        device = device or self._default_device
        if not device:
            return False

        stdout, _ = self._run_adb(
            ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2),
             str(duration_ms)], device
        )
        return True

    def input_text(self, text: str, device: str = "") -> bool:
        """Input text on the device."""
        device = device or self._default_device
        if not device:
            return False

        # Escape spaces
        escaped = text.replace(" ", "%s")
        stdout, _ = self._run_adb(["shell", "input", "text", escaped], device)
        return True

    def input_keyevent(self, keycode: int, device: str = "") -> bool:
        """Send a key event to the device."""
        device = device or self._default_device
        if not device:
            return False

        stdout, _ = self._run_adb(["shell", "input", "keyevent", str(keycode)], device)
        return True

    def get_app_logs(self, package: str = "com.quora.automation",
                     device: str = "", lines: int = 100) -> str:
        """Get recent logcat output for the app."""
        device = device or self._default_device
        if not device:
            return ""

        stdout, _ = self._run_adb(
            ["logcat", "-d", "-t", str(lines), f"|", "grep", package], device
        )
        return stdout

    def forward_port(self, local_port: int = 5000, device_port: int = 5000,
                     device: str = "") -> bool:
        """Forward a local port to the device for server communication."""
        device = device or self._default_device
        if not device:
            return False

        stdout, _ = self._run_adb(
            ["forward", f"tcp:{local_port}", f"tcp:{device_port}"], device
        )
        return True

    def reverse_port(self, device_port: int = 5000, local_port: int = 5000,
                     device: str = "") -> bool:
        """Reverse forward a port from device to local (for emulator)."""
        device = device or self._default_device
        if not device:
            return False

        stdout, _ = self._run_adb(
            ["reverse", f"tcp:{device_port}", f"tcp:{local_port}"], device
        )
        return True

    def get_app_status(self, package: str = "com.quora.automation",
                       device: str = "") -> str:
        """Check if the app is running on the device."""
        device = device or self._default_device
        if not device:
            return "unknown"

        stdout, _ = self._run_adb(
            ["shell", "pidof", package], device
        )
        if stdout and stdout.isdigit():
            return "running"
        return "stopped"

    def set_default_device(self, device_id: str):
        """Set the default target device."""
        self._default_device = device_id

    def get_default_device(self) -> Optional[str]:
        return self._default_device

    def to_dict(self) -> dict:
        """Get ADB manager state as dict."""
        return {
            "connected_devices": self._connected_devices,
            "default_device": self._default_device,
            "adb_path": self.adb_path,
        }


# Singleton instance
adb_manager = ADBManager()
