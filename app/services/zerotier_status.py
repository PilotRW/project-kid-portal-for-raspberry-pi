import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field


class ZeroTierNetwork(BaseModel):
    network_id: str
    name: str = ""
    status: str = "UNKNOWN"
    network_type: str = ""
    interface: str = ""
    assigned_addresses: list[str] = Field(default_factory=list)


class ZeroTierStatus(BaseModel):
    installed: bool
    service_active: bool
    online: bool = False
    node_id: str = ""
    version: str = ""
    networks: list[ZeroTierNetwork] = Field(default_factory=list)
    error: str | None = None


class ZeroTierStatusService:
    def __init__(self, helper_path: str = "/usr/local/sbin/kid-portal-zerotier-status") -> None:
        self.helper_path = Path(helper_path)

    def get_status(self) -> ZeroTierStatus:
        installed = self.helper_path.exists() or shutil.which("zerotier-cli") is not None
        service_active = self._service_active()
        if not self.helper_path.exists():
            return ZeroTierStatus(installed=installed, service_active=service_active)

        try:
            result = subprocess.run(
                ["sudo", "-n", str(self.helper_path)],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return ZeroTierStatus(
                installed=installed,
                service_active=service_active,
                error=str(error),
            )

        if result.returncode != 0:
            detail = result.stderr.strip() or "ZeroTier status command failed"
            return ZeroTierStatus(
                installed=installed,
                service_active=service_active,
                error=detail,
            )

        try:
            payload = json.loads(result.stdout)
            info = payload.get("info", {})
            networks = [self._network_from_payload(item) for item in payload.get("networks", [])]
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
            return ZeroTierStatus(
                installed=installed,
                service_active=service_active,
                error="Invalid ZeroTier status response",
            )

        return ZeroTierStatus(
            installed=True,
            service_active=service_active,
            online=bool(info.get("online")),
            node_id=str(info.get("address", "")),
            version=str(info.get("version", "")),
            networks=networks,
        )

    @staticmethod
    def _network_from_payload(payload: dict[str, object]) -> ZeroTierNetwork:
        addresses = payload.get("assignedAddresses", [])
        return ZeroTierNetwork(
            network_id=str(payload.get("nwid") or payload.get("id") or ""),
            name=str(payload.get("name", "")),
            status=str(payload.get("status", "UNKNOWN")),
            network_type=str(payload.get("type", "")),
            interface=str(payload.get("portDeviceName", "")),
            assigned_addresses=[str(address) for address in addresses] if isinstance(addresses, list) else [],
        )

    @staticmethod
    def _service_active() -> bool:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "zerotier-one.service"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0 and result.stdout.strip() == "active"
