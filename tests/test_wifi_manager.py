from app.services.wifi_manager import WifiManager


def test_wifi_scan_parses_escaped_ssids(monkeypatch):
    manager = WifiManager()
    output = "\n".join(
        [
            "*:Home\\:TV:92:WPA2",
            ":Guest:31:",
            ":Home\\:TV:80:WPA2",
        ]
    )
    monkeypatch.setattr(manager, "_run", lambda args: output)

    networks = manager.scan()

    assert [network.ssid for network in networks] == ["Home:TV", "Guest"]
    assert networks[0].connected is True
    assert networks[0].signal == 92
    assert networks[1].security == "Open"


def test_wifi_status_parses_connection(monkeypatch):
    manager = WifiManager()
    monkeypatch.setattr(manager, "_run", lambda args: "GENERAL.STATE:100 (connected)\nGENERAL.CONNECTION:Home\\:TV\n")

    status = manager.status()

    assert status.state == "100 (connected)"
    assert status.connection == "Home:TV"
