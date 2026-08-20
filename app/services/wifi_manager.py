import subprocess
from pydantic import BaseModel


class WifiNetwork(BaseModel):
    ssid: str
    signal: int
    security: str
    connected: bool = False


class WifiStatus(BaseModel):
    state: str
    connection: str | None = None


class WifiConnectResult(BaseModel):
    status: str
    message: str


class WifiManager:
    def __init__(self, command: str = "/usr/local/sbin/kid-portal-wifi") -> None:
        self.command = command

    def scan(self) -> list[WifiNetwork]:
        output = self._run(["scan"])
        networks: dict[str, WifiNetwork] = {}
        for line in output.splitlines():
            parts = self._split_nmcli(line)
            if len(parts) < 4:
                continue
            in_use, ssid, signal, security = parts[:4]
            if not ssid:
                continue
            current = networks.get(ssid)
            network = WifiNetwork(
                ssid=ssid,
                signal=self._parse_signal(signal),
                security=security or "Open",
                connected=in_use == "*",
            )
            if current is None or network.connected or network.signal > current.signal:
                networks[ssid] = network
        return sorted(networks.values(), key=lambda item: (not item.connected, -item.signal, item.ssid.lower()))

    def status(self) -> WifiStatus:
        output = self._run(["status"])
        values: dict[str, str] = {}
        for line in output.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            values[key] = self._unescape(value)
        state = values.get("GENERAL.STATE", "unknown")
        connection = values.get("GENERAL.CONNECTION")
        if connection in {"", "--"}:
            connection = None
        return WifiStatus(state=state, connection=connection)

    def connect(self, ssid: str, password: str | None = None) -> WifiConnectResult:
        normalized_ssid = ssid.strip()
        if not normalized_ssid:
            raise ValueError("SSID is required")
        args = ["connect", normalized_ssid]
        if password:
            args.append(password)
        output = self._run(args)
        return WifiConnectResult(status="connecting", message=output.strip() or "Connection request sent.")

    def _run(self, args: list[str]) -> str:
        try:
            return subprocess.check_output(
                ["sudo", "-n", self.command, *args],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=45,
            )
        except FileNotFoundError:
            raise RuntimeError("Wi-Fi helper is not installed") from None
        except subprocess.CalledProcessError as error:
            detail = (error.output or "").strip() or "Wi-Fi command failed"
            raise RuntimeError(detail) from None
        except subprocess.TimeoutExpired:
            raise RuntimeError("Wi-Fi command timed out") from None

    @staticmethod
    def _parse_signal(value: str) -> int:
        try:
            return max(0, min(100, int(value)))
        except ValueError:
            return 0

    @classmethod
    def _split_nmcli(cls, line: str) -> list[str]:
        parts: list[str] = []
        current = []
        escaped = False
        for char in line:
            if escaped:
                current.append(char)
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == ":":
                parts.append("".join(current))
                current = []
            else:
                current.append(char)
        parts.append("".join(current))
        return parts

    @classmethod
    def _unescape(cls, value: str) -> str:
        return cls._split_nmcli(value)[0] if "\\" in value else value
