from app.services.config_service import PortalConfig


KIOSK_HOME_URL = "http://127.0.0.1:8080/"

LOCAL_KIOSK_ALLOWLIST = [
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8080/*",
    "http://localhost:8080",
    "http://localhost:8080/*",
    "http://[::1]:8080",
    "http://[::1]:8080/*",
]

YOUTUBE_ALLOWLIST = [
    "googlevideo.com",
    ".googlevideo.com",
    "apis.google.com",
    "gstatic.com",
    ".gstatic.com",
    "i.ytimg.com",
    "s.ytimg.com",
    "www.gstatic.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtube.com",
    ".youtube.com",
    "www.youtube-nocookie.com",
    "youtube-nocookie.com",
    ".youtube-nocookie.com",
    "ytimg.com",
    ".ytimg.com",
    "https://www.googleapis.com/*",
    "https://i.ytimg.com/*",
    "https://s.ytimg.com/*",
    "https://youtube-nocookie.com/*",
    "https://www.youtube-nocookie.com/*",
    "https://*.youtube-nocookie.com/*",
    "https://youtube.com/*",
    "https://www.youtube.com/*",
    "https://m.youtube.com/*",
    "https://www.gstatic.com/youtube/*",
    "https://apis.google.com/*",
    "https://*.googlevideo.com/*",
]


class PolicyManager:
    def __init__(self, config: PortalConfig) -> None:
        self.config = config

    def build_policy(self) -> dict[str, object]:
        allowlist = [*LOCAL_KIOSK_ALLOWLIST]
        for site in self.config.allowed_sites:
            allowlist.extend(self._domain_patterns(site.domain))
        allowlist.extend(YOUTUBE_ALLOWLIST)

        return {
            "URLBlocklist": ["http://*", "http://*/*", "https://*", "https://*/*"],
            "URLAllowlist": allowlist,
            "DefaultPopupsSetting": 2,
            "DownloadRestrictions": 3,
            "DeveloperToolsAvailability": 2,
            "BrowserAddPersonEnabled": False,
            "BrowserGuestModeEnabled": False,
            "IncognitoModeAvailability": 1,
            "HomepageIsNewTabPage": False,
            "HomepageLocation": KIOSK_HOME_URL,
            "RestoreOnStartup": 4,
            "RestoreOnStartupURLs": [KIOSK_HOME_URL],
            "SavingBrowserHistoryDisabled": False,
            "TranslateEnabled": False,
        }

    @staticmethod
    def _domain_patterns(domain: str) -> list[str]:
        normalized = domain.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
        normalized = normalized.removeprefix("www.")
        return [
            normalized,
            f"www.{normalized}",
            f".{normalized}",
            f"https://{normalized}/*",
            f"https://www.{normalized}/*",
            f"https://*.{normalized}/*",
        ]
