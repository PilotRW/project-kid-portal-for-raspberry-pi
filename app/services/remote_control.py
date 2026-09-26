import os
import shutil
import subprocess
from pathlib import Path


class RemoteControlService:
    KEY_MAP = {
        "up": "Up",
        "down": "Down",
        "left": "Left",
        "right": "Right",
        "ok": "Return",
        "back": "Alt+Left",
        "escape": "Escape",
        "home": "Alt+Home",
        "play_pause": "space",
        "volume_up": "XF86AudioRaiseVolume",
        "volume_down": "XF86AudioLowerVolume",
        "mute": "XF86AudioMute",
    }
    MAX_TEXT_LENGTH = 160
    POINTER_STEP = 56
    POINTER_DIRECTIONS = {
        "up": (0, -POINTER_STEP),
        "down": (0, POINTER_STEP),
        "left": (-POINTER_STEP, 0),
        "right": (POINTER_STEP, 0),
    }

    def __init__(self, command: str | None = None, display: str | None = None, xauthority: str | None = None):
        self.command = command or os.environ.get("KID_PORTAL_XDOTOOL") or shutil.which("xdotool") or "/usr/bin/xdotool"
        self.display = display or os.environ.get("KID_PORTAL_REMOTE_DISPLAY", ":0")
        self.xauthority = xauthority or os.environ.get("KID_PORTAL_REMOTE_XAUTHORITY", "/home/pi/.Xauthority")

    def press_key(self, key: str) -> None:
        mapped = self.KEY_MAP.get(key)
        if mapped is None:
            raise ValueError("Unsupported remote key")
        self._run(["key", "--clearmodifiers", mapped])

    def type_text(self, text: str) -> None:
        normalized = text.strip()
        if not normalized:
            raise ValueError("Text cannot be empty")
        if len(normalized) > self.MAX_TEXT_LENGTH:
            raise ValueError(f"Text is limited to {self.MAX_TEXT_LENGTH} characters")
        self._run(["type", "--clearmodifiers", normalized])

    def control_pointer(self, action: str) -> None:
        if action == "click":
            self._run(["click", "1"])
            return
        if action == "scroll_up":
            self._run(["click", "--repeat", "3", "--delay", "20", "4"])
            return
        if action == "scroll_down":
            self._run(["click", "--repeat", "3", "--delay", "20", "5"])
            return
        movement = self.POINTER_DIRECTIONS.get(action)
        if movement is None:
            raise ValueError("Unsupported pointer action")
        dx, dy = movement
        self._run(["mousemove_relative", "--", str(dx), str(dy)])

    def _run(self, args: list[str]) -> None:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        if self.xauthority and Path(self.xauthority).exists():
            env["XAUTHORITY"] = self.xauthority
        try:
            subprocess.run([self.command, *args], check=True, timeout=5, env=env, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise RuntimeError("xdotool is not installed") from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("Remote command timed out") from error
        except subprocess.CalledProcessError as error:
            message = error.stderr.strip() or error.stdout.strip() or "Remote command failed"
            raise RuntimeError(message) from error
