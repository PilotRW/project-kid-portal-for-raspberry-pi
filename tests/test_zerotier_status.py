import json
from subprocess import CompletedProcess

from app.services.zerotier_status import ZeroTierStatusService


def test_zerotier_status_parses_node_network_and_addresses(monkeypatch, tmp_path):
    helper = tmp_path / "kid-portal-zerotier-status"
    helper.touch()
    payload = {
        "info": {"address": "abcdef1234", "online": True, "version": "1.14.2"},
        "networks": [
            {
                "nwid": "0123456789abcdef",
                "name": "Kids Kiosk",
                "status": "OK",
                "type": "PRIVATE",
                "portDeviceName": "ztabc123",
                "assignedAddresses": ["10.147.0.42/16"],
            }
        ],
    }

    def fake_run(command, **kwargs):
        if command[:2] == ["systemctl", "is-active"]:
            return CompletedProcess(command, 0, stdout="active\n", stderr="")
        return CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("app.services.zerotier_status.subprocess.run", fake_run)

    status = ZeroTierStatusService(str(helper)).get_status()

    assert status.installed is True
    assert status.service_active is True
    assert status.online is True
    assert status.node_id == "abcdef1234"
    assert status.networks[0].interface == "ztabc123"
    assert status.networks[0].assigned_addresses == ["10.147.0.42/16"]


def test_zerotier_status_is_graceful_when_not_installed(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.zerotier_status.shutil.which", lambda _command: None)
    monkeypatch.setattr(ZeroTierStatusService, "_service_active", staticmethod(lambda: False))

    status = ZeroTierStatusService(str(tmp_path / "missing-helper")).get_status()

    assert status.installed is False
    assert status.service_active is False
    assert status.online is False
    assert status.networks == []
