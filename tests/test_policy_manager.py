from app.services.config_service import ParentConfig, PortalConfig, SiteConfig, YouTubeConfig
from app.services.policy_manager import PolicyManager


def test_youtube_default_result_count_is_twenty():
    assert YouTubeConfig().max_results == 20


def test_policy_blocks_by_default_and_allows_configured_sites():
    config = PortalConfig(
        allowed_sites=[SiteConfig(label="Wiki", url="https://www.wikipedia.org/", domain="wikipedia.org")],
        web_allowlist=["media.example.org"],
        parent=ParentConfig(pin_sha256="x"),
    )
    policy = PolicyManager(config).build_policy()
    assert policy["URLBlocklist"] == ["http://*", "http://*/*", "https://*", "https://*/*"]
    assert "wikipedia.org" in policy["URLAllowlist"]
    assert ".wikipedia.org" in policy["URLAllowlist"]
    assert "https://wikipedia.org/*" in policy["URLAllowlist"]
    assert "https://www.wikipedia.org/*" in policy["URLAllowlist"]
    assert "https://*.wikipedia.org/*" in policy["URLAllowlist"]
    assert "media.example.org" in policy["URLAllowlist"]
    assert "https://*.media.example.org/*" in policy["URLAllowlist"]
    assert ".youtube-nocookie.com" in policy["URLAllowlist"]
    assert ".googlevideo.com" in policy["URLAllowlist"]
    assert "apis.google.com" in policy["URLAllowlist"]
    assert "www.gstatic.com" in policy["URLAllowlist"]
    assert "https://www.youtube-nocookie.com/*" in policy["URLAllowlist"]
    assert "youtube.com" not in policy["URLAllowlist"]
    assert ".youtube.com" not in policy["URLAllowlist"]
    assert "www.youtube.com" not in policy["URLAllowlist"]
    assert "https://www.youtube.com/*" not in policy["URLAllowlist"]
    assert "https://www.youtube.com/iframe_api" in policy["URLAllowlist"]
    assert "https://www.youtube.com/s/player/*" in policy["URLAllowlist"]
    assert policy["HomepageIsNewTabPage"] is False
    assert policy["HomepageLocation"] == "http://127.0.0.1:8080/"
    assert policy["RestoreOnStartupURLs"] == ["http://127.0.0.1:8080/"]
    assert policy["DownloadRestrictions"] == 3


def test_policy_never_allows_direct_youtube_ui_from_config():
    config = PortalConfig(
        allowed_sites=[
            SiteConfig(label="YouTube", url="https://www.youtube.com/", domain="youtube.com"),
            SiteConfig(label="YouTube Mobile", url="https://m.youtube.com/", domain="m.youtube.com"),
        ],
        web_allowlist=["www.youtube.com", "music.youtube.com", "youtu.be"],
        parent=ParentConfig(pin_sha256="x"),
    )

    allowlist = PolicyManager(config).build_policy()["URLAllowlist"]

    assert "youtube.com" not in allowlist
    assert "www.youtube.com" not in allowlist
    assert "m.youtube.com" not in allowlist
    assert "youtu.be" not in allowlist
    assert "https://youtube.com/*" not in allowlist
    assert "https://www.youtube.com/*" not in allowlist
    assert "https://m.youtube.com/*" not in allowlist
    assert "https://www.youtube.com/iframe_api" in allowlist
