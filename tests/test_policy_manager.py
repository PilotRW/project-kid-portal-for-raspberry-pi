from app.services.config_service import ParentConfig, PortalConfig, SiteConfig, YouTubeConfig
from app.services.policy_manager import PolicyManager


def test_youtube_default_result_count_is_twenty():
    assert YouTubeConfig().max_results == 20


def test_policy_blocks_by_default_and_allows_configured_sites():
    config = PortalConfig(
        allowed_sites=[SiteConfig(label="Wiki", url="https://www.wikipedia.org/", domain="wikipedia.org")],
        parent=ParentConfig(pin_sha256="x"),
    )
    policy = PolicyManager(config).build_policy()
    assert policy["URLBlocklist"] == ["http://*", "http://*/*", "https://*", "https://*/*"]
    assert "wikipedia.org" in policy["URLAllowlist"]
    assert ".wikipedia.org" in policy["URLAllowlist"]
    assert "https://wikipedia.org/*" in policy["URLAllowlist"]
    assert "https://www.wikipedia.org/*" in policy["URLAllowlist"]
    assert "https://*.wikipedia.org/*" in policy["URLAllowlist"]
    assert ".youtube-nocookie.com" in policy["URLAllowlist"]
    assert ".googlevideo.com" in policy["URLAllowlist"]
    assert "apis.google.com" in policy["URLAllowlist"]
    assert "www.gstatic.com" in policy["URLAllowlist"]
    assert "https://www.youtube-nocookie.com/*" in policy["URLAllowlist"]
    assert policy["HomepageIsNewTabPage"] is False
    assert policy["HomepageLocation"] == "http://127.0.0.1:8080/"
    assert policy["RestoreOnStartupURLs"] == ["http://127.0.0.1:8080/"]
    assert policy["DownloadRestrictions"] == 3
