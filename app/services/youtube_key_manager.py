import re
import subprocess

from pydantic import BaseModel


API_KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{20,200}$")


class YouTubeKeyUpdateResult(BaseModel):
    status: str


class YouTubeKeyManager:
    def __init__(self, command: str = "/usr/local/sbin/kid-portal-youtube-key") -> None:
        self.command = command

    def set_key(self, api_key: str) -> YouTubeKeyUpdateResult:
        normalized = api_key.strip()
        if not API_KEY_RE.fullmatch(normalized):
            raise ValueError("API key must be 20-200 URL-safe characters without spaces")
        self._run(["set"], input_text=normalized)
        return YouTubeKeyUpdateResult(status="saved")

    def clear_key(self) -> YouTubeKeyUpdateResult:
        self._run(["clear"], input_text="")
        return YouTubeKeyUpdateResult(status="cleared")

    def _run(self, args: list[str], input_text: str) -> str:
        try:
            completed = subprocess.run(
                ["sudo", "-n", self.command, *args],
                input=input_text,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=True,
                timeout=20,
            )
            return completed.stdout
        except FileNotFoundError:
            raise RuntimeError("YouTube key helper is not installed") from None
        except subprocess.CalledProcessError as error:
            detail = (error.stdout or "").strip() or "YouTube API key update failed"
            raise RuntimeError(detail) from None
        except subprocess.TimeoutExpired:
            raise RuntimeError("YouTube API key update timed out") from None
