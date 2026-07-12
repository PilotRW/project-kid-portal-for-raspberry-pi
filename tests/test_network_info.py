from app.services.network_info import NetworkInfoService


def test_network_info_builds_urls_from_addresses(monkeypatch):
    service = NetworkInfoService(port=8080)

    monkeypatch.setattr(service, "_local_ipv4_addresses", lambda hostname: {"192.168.1.44"})

    info = service.get_info()
    assert info.addresses[0].address == "192.168.1.44"
    assert info.addresses[0].portal_url == "http://192.168.1.44:8080"
    assert info.addresses[0].ssh_target == "ssh pi@192.168.1.44"
