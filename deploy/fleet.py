#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = REPO_ROOT / ".local" / "devices.json"


def load_inventory(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing inventory: {path}\nCopy deploy/devices.example.json to .local/devices.json first.")
    return json.loads(path.read_text(encoding="utf-8"))


def merged_device(inventory: dict[str, Any], name: str) -> dict[str, Any]:
    devices = inventory.get("devices", {})
    if name not in devices:
        available = ", ".join(sorted(devices)) or "none"
        raise SystemExit(f"Unknown device '{name}'. Available: {available}")
    merged = dict(inventory.get("defaults", {}))
    merged.update(devices[name])
    merged["name"] = name
    return merged


def selected_devices(inventory: dict[str, Any], selector: str) -> list[dict[str, Any]]:
    if selector == "all":
        return [merged_device(inventory, name) for name in sorted(inventory.get("devices", {}))]
    return [merged_device(inventory, selector)]


def truthy(value: Any) -> str:
    return "1" if bool(value) else "0"


def host_for(device: dict[str, Any], action: str) -> str:
    if action == "bootstrap":
        return device.get("host") or device.get("management_host")
    return device.get("management_host") or device.get("host")


def env_for(device: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env["KID_PORTAL_LAN_CIDR"] = str(device.get("lan_cidr", "192.168.0.0/24"))
    env["KID_PORTAL_MANAGEMENT_CIDR"] = str(device.get("management_cidr", ""))
    env["KID_PORTAL_ALLOW_LAN_SSH"] = truthy(device.get("allow_lan_ssh", True))
    env["KID_PORTAL_ENABLE_ZEROTIER"] = truthy(device.get("enable_zerotier", False))

    network_id = device.get("zerotier_network_id")
    if network_id:
        env["KID_PORTAL_ZEROTIER_NETWORK_ID"] = str(network_id)
    return env


def run_device(action: str, device: dict[str, Any]) -> int:
    host = host_for(device, action)
    if not host:
        print(f"{device['name']}: no host configured for {action}", file=sys.stderr)
        return 2
    user = str(device.get("user", "pi"))
    script = {
        "bootstrap": REPO_ROOT / "deploy" / "bootstrap-pi.sh",
        "deploy": REPO_ROOT / "deploy" / "deploy-to-pi.sh",
        "check": REPO_ROOT / "deploy" / "check-pi.sh",
    }[action]
    print(f"== {action}: {device['name']} ({user}@{host}) ==")
    return subprocess.call([str(script), str(host), user], cwd=REPO_ROOT, env=env_for(device))


def list_devices(inventory: dict[str, Any]) -> int:
    for name in sorted(inventory.get("devices", {})):
        device = merged_device(inventory, name)
        print(
            f"{name}\tuser={device.get('user', 'pi')}\t"
            f"host={device.get('host', '-')}\tmanagement={device.get('management_host', '-')}\t"
            f"zerotier={truthy(device.get('enable_zerotier', False))}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Kid Portal Raspberry Pi fleet deployments.")
    parser.add_argument("action", choices=["list", "bootstrap", "deploy", "check"])
    parser.add_argument("device", nargs="?", default="all", help="Device name from inventory, or 'all'.")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    args = parser.parse_args()

    inventory = load_inventory(args.inventory)
    if args.action == "list":
        return list_devices(inventory)

    failures = 0
    for device in selected_devices(inventory, args.device):
        result = run_device(args.action, device)
        if result != 0:
            failures += 1
            print(f"{device['name']}: {args.action} failed with exit {result}", file=sys.stderr)
            if args.device != "all":
                return result
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
