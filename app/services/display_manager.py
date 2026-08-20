import os
import subprocess

from pydantic import BaseModel


class DisplayStatus(BaseModel):
    configured_mode: str
    current_resolution: str | None = None


class DisplayManager:
    def __init__(self, command: str = "/usr/local/sbin/kid-portal-display-mode") -> None:
        self.command = command

    def apply(self, mode: str) -> DisplayStatus:
        if mode not in {"1080p", "4k"}:
            raise ValueError("Unsupported display mode")
        self._run([mode])
        return self.status(mode)

    def status(self, configured_mode: str) -> DisplayStatus:
        current = None
        try:
            output = subprocess.check_output(
                ["xrandr", "--query"],
                env=self._env(),
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            output = ""
        for line in output.splitlines():
            if " connected " not in line:
                continue
            for item in line.split():
                if "x" in item and "+" in item:
                    current = item.split("+", 1)[0]
                    break
            break
        return DisplayStatus(configured_mode=configured_mode, current_resolution=current)

    def _run(self, args: list[str]) -> str:
        try:
            return subprocess.check_output(
                [self.command, *args],
                env=self._env(),
                stderr=subprocess.STDOUT,
                text=True,
                timeout=20,
            )
        except FileNotFoundError:
            raise RuntimeError("Display helper is not installed") from None
        except subprocess.CalledProcessError as error:
            detail = (error.output or "").strip() or "Display mode update failed"
            raise RuntimeError(detail) from None
        except subprocess.TimeoutExpired:
            raise RuntimeError("Display mode update timed out") from None

    @staticmethod
    def _env() -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        return env
