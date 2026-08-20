import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.services.config_service import ConfigService, PortalConfig
from app.services.display_manager import DisplayManager, DisplayStatus
from app.services.filtering_engine import FilteringEngine
from app.services.network_info import NetworkInfoService
from app.services.policy_manager import PolicyManager
from app.services.search_history import SearchHistoryService
from app.services.usage_tracker import UsageTrackerService
from app.services.wifi_manager import WifiConnectResult, WifiManager, WifiNetwork, WifiStatus
from app.services.youtube_api import YouTubeApiError, YouTubeApiService
from app.services.youtube_key_manager import YouTubeKeyManager, YouTubeKeyUpdateResult
from app.services.youtube_search_cache import YouTubeSearchCacheService

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

config_service = ConfigService()
youtube_service = YouTubeApiService()
search_history_service = SearchHistoryService()
youtube_search_cache_service = YouTubeSearchCacheService()
network_info_service = NetworkInfoService()
usage_tracker_service = UsageTrackerService()
wifi_manager = WifiManager()
display_manager = DisplayManager()
youtube_key_manager = YouTubeKeyManager()
THUMBNAIL_HOSTS = {"i.ytimg.com", "s.ytimg.com"}
NETWORK_ACCESS_REQUEST_PATH = Path(os.environ.get("KID_PORTAL_NETWORK_ACCESS_REQUEST", "/run/kid-portal/network-access.request"))
NETWORK_ACCESS_STATE_PATH = Path(os.environ.get("KID_PORTAL_NETWORK_ACCESS_STATE", "/run/kid-portal/network-access.state"))
ADMIN_PIN_MAX_ATTEMPTS = int(os.environ.get("KID_PORTAL_ADMIN_PIN_MAX_ATTEMPTS", "8"))
ADMIN_PIN_FINDTIME_SECONDS = int(os.environ.get("KID_PORTAL_ADMIN_PIN_FINDTIME_SECONDS", "600"))
ADMIN_PIN_LOCKOUT_SECONDS = int(os.environ.get("KID_PORTAL_ADMIN_PIN_LOCKOUT_SECONDS", "600"))
admin_pin_attempts: dict[str, dict[str, object]] = {}

app = FastAPI(title="Kid Portal", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ParentConfigUpdate(BaseModel):
    pin: str
    config: PortalConfig
    view_pin: str | None = None


class ParentPinRequest(BaseModel):
    pin: str


class ViewPinRequest(BaseModel):
    pin: str
    video_id: str


class PlaybackStartRequest(BaseModel):
    video_id: str


class PlaybackHeartbeatRequest(BaseModel):
    session_id: str
    state: str = "paused"


class PlaybackStopRequest(BaseModel):
    session_id: str


class StorageInfo(BaseModel):
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float


class ProcessInfo(BaseModel):
    pid: int
    user: str
    cpu_percent: float
    memory_percent: float
    command: str
    args: str


class SystemMonitoring(BaseModel):
    top_processes: list[ProcessInfo]
    hottest_process: ProcessInfo | None
    temperature_c: float | None = None
    throttled_state: str | None = None


class SystemActionResult(BaseModel):
    status: str


class NetworkAccessState(BaseModel):
    content_port: int = 8080
    content_lan_enabled: bool
    admin_port: int = 80


class NetworkAccessUpdate(ParentPinRequest):
    enabled: bool


class DisplayModeUpdate(ParentPinRequest):
    mode: str


class YouTubeKeyUpdate(ParentPinRequest):
    api_key: str


class WifiConnectRequest(ParentPinRequest):
    ssid: str
    password: str | None = None


ADMIN_SURFACE_ALLOWED_PATHS = {
    "/",
    "/admin",
    "/api/admin/state",
    "/api/admin/youtube/history/clear",
    "/api/parent/youtube/key",
    "/api/parent/config",
    "/api/parent/network-access",
    "/api/parent/display",
    "/api/parent/storage",
    "/api/parent/monitoring",
    "/api/parent/terminal/start",
    "/api/parent/kiosk/start",
}
ADMIN_SURFACE_ALLOWED_PREFIXES = ("/static/admin.",)


def is_admin_surface() -> bool:
    return os.environ.get("KID_PORTAL_SURFACE") == "admin"


def is_admin_surface_path_allowed(path: str) -> bool:
    return path in ADMIN_SURFACE_ALLOWED_PATHS or path.startswith(ADMIN_SURFACE_ALLOWED_PREFIXES)


@app.middleware("http")
async def restrict_admin_surface(request: Request, call_next):
    if is_admin_surface() and request.method != "OPTIONS" and not is_admin_surface_path_allowed(request.url.path):
        return Response(status_code=404)
    return await call_next(request)


def client_identifier(request: Request | None) -> str:
    if request is None or request.client is None:
        return "local"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host


def check_admin_pin_lockout(client_id: str) -> None:
    attempt = admin_pin_attempts.get(client_id)
    if not attempt:
        return
    locked_until = float(attempt.get("locked_until") or 0)
    now = time.time()
    if locked_until > now:
        retry_after = max(1, int(locked_until - now))
        raise HTTPException(
            status_code=429,
            detail=f"Too many invalid PIN attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    if locked_until:
        admin_pin_attempts.pop(client_id, None)


def record_admin_pin_failure(client_id: str) -> None:
    now = time.time()
    attempt = admin_pin_attempts.setdefault(client_id, {"failures": [], "locked_until": 0.0})
    failures = [
        float(item)
        for item in attempt.get("failures", [])
        if now - float(item) <= ADMIN_PIN_FINDTIME_SECONDS
    ]
    failures.append(now)
    attempt["failures"] = failures
    if len(failures) >= ADMIN_PIN_MAX_ATTEMPTS:
        attempt["locked_until"] = now + ADMIN_PIN_LOCKOUT_SECONDS


def reset_admin_pin_failures(client_id: str) -> None:
    admin_pin_attempts.pop(client_id, None)


def verify_parent_pin(pin: str, request: Request | None = None) -> PortalConfig:
    client_id = client_identifier(request)
    check_admin_pin_lockout(client_id)
    config = get_config()
    if not config.parent.verify_pin(pin):
        record_admin_pin_failure(client_id)
        raise HTTPException(status_code=403, detail="Invalid PIN")
    reset_admin_pin_failures(client_id)
    return config


def verify_view_pin(pin: str) -> PortalConfig:
    config = get_config()
    if not config.parent.verify_view_pin(pin):
        raise HTTPException(status_code=403, detail="Invalid viewing PIN")
    return config


def get_config() -> PortalConfig:
    return config_service.load()


def run_systemctl_sequence(commands: list[list[str]]) -> None:
    for command in commands:
        subprocess.run(command, check=True, timeout=30)


def read_storage_info() -> StorageInfo:
    usage = shutil.disk_usage("/")
    used = usage.total - usage.free
    return StorageInfo(
        path="/",
        total_bytes=usage.total,
        used_bytes=used,
        free_bytes=usage.free,
        percent_used=round((used / usage.total) * 100, 1) if usage.total else 0,
    )


def read_system_monitoring() -> SystemMonitoring:
    temperature_c = read_temperature_c()
    throttled_state = read_throttled_state()
    try:
        output = subprocess.check_output(
            ["ps", "-eo", "pid,user,pcpu,pmem,comm,args", "--sort=-pcpu"],
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return SystemMonitoring(
            top_processes=[],
            hottest_process=None,
            temperature_c=temperature_c,
            throttled_state=throttled_state,
        )
    rows = []
    for line in output.splitlines()[1:11]:
        parts = line.split(None, 5)
        if len(parts) < 6:
            continue
        pid, user, cpu, memory, command, args = parts
        rows.append(
            ProcessInfo(
                pid=int(pid),
                user=user,
                cpu_percent=float(cpu),
                memory_percent=float(memory),
                command=command,
                args=args,
            )
        )
    return SystemMonitoring(
        top_processes=rows,
        hottest_process=rows[0] if rows else None,
        temperature_c=temperature_c,
        throttled_state=throttled_state,
    )


def read_temperature_c() -> float | None:
    try:
        output = subprocess.check_output(["vcgencmd", "measure_temp"], text=True, timeout=5).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    prefix = "temp="
    suffix = "'C"
    if not output.startswith(prefix) or not output.endswith(suffix):
        return None
    try:
        return float(output.removeprefix(prefix).removesuffix(suffix))
    except ValueError:
        return None


def read_throttled_state() -> str | None:
    try:
        output = subprocess.check_output(["vcgencmd", "get_throttled"], text=True, timeout=5).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return output.split("=", 1)[1] if "=" in output else output


def read_network_access_state() -> NetworkAccessState:
    try:
        state = NETWORK_ACCESS_STATE_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return NetworkAccessState(content_lan_enabled=False)
    return NetworkAccessState(content_lan_enabled=state == "enabled")


def set_network_access_state(enabled: bool) -> NetworkAccessState:
    NETWORK_ACCESS_REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    NETWORK_ACCESS_REQUEST_PATH.write_text("enabled\n" if enabled else "disabled\n", encoding="utf-8")
    return NetworkAccessState(content_lan_enabled=enabled)


def render_watch_page(video_id: str, limit_reached: bool = False) -> str:
    iframe_src = "" if limit_reached else (
        f"https://www.youtube-nocookie.com/embed/{video_id}"
        "?autoplay=1&rel=0&modestbranding=1&playsinline=1&disablekb=1&fs=1&enablejsapi=1&origin=http://127.0.0.1:8080"
    )
    return (
        (STATIC_DIR / "watch.html")
        .read_text(encoding="utf-8")
        .replace("__VIDEO_ID__", video_id)
        .replace("__IFRAME_SRC__", iframe_src)
        .replace("__LIMIT_REACHED__", "true" if limit_reached else "false")
    )


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    if is_admin_surface():
        return (STATIC_DIR / "admin.html").read_text(encoding="utf-8")
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/admin", response_class=HTMLResponse)
async def admin() -> str:
    return (STATIC_DIR / "admin.html").read_text(encoding="utf-8")


@app.get("/api/config")
async def read_config() -> PortalConfig:
    return get_config()


@app.put("/api/config")
async def write_config(config: PortalConfig) -> dict[str, str]:
    config_service.save(config)
    return {"status": "saved"}


@app.put("/api/parent/config")
async def write_parent_config(update: ParentConfigUpdate, http_request: Request) -> dict[str, str]:
    verify_parent_pin(update.pin, http_request)
    if update.view_pin:
        view_pin = update.view_pin.strip()
        if len(view_pin) < 4 or len(view_pin) > 12 or not view_pin.isdigit():
            raise HTTPException(status_code=400, detail="Viewing PIN must be 4-12 digits")
        if update.config.parent.verify_pin(view_pin):
            raise HTTPException(status_code=400, detail="Viewing PIN must be different from parent PIN")
        update.config.parent.set_view_pin(view_pin)
    config_service.save(update.config)
    return {"status": "saved"}


@app.get("/api/sites")
async def read_sites() -> list[dict[str, str]]:
    return [site.model_dump() for site in get_config().allowed_sites]


@app.get("/api/system/network")
async def read_network_info() -> dict[str, object]:
    return network_info_service.get_info().model_dump(mode="json")


@app.get("/api/youtube/status")
async def read_youtube_status() -> dict[str, str | bool]:
    return youtube_service.status()


@app.get("/api/youtube/search")
async def search_youtube(q: str = Query(min_length=1, max_length=120)) -> dict[str, object]:
    config = get_config()
    filtering = FilteringEngine(config.filtering)
    mode = youtube_service.status()["mode"]
    raw_results = youtube_search_cache_service.get(q, config.youtube.max_results, config.youtube.safe_search)
    if raw_results is not None:
        mode = "cache"
    else:
        try:
            raw_results = await youtube_service.search(
                q,
                limit=config.youtube.max_results,
                safe_search=config.youtube.safe_search,
            )
        except YouTubeApiError as error:
            raise HTTPException(status_code=503, detail=error.detail) from error
        if mode == "live":
            youtube_search_cache_service.set(q, config.youtube.max_results, config.youtube.safe_search, raw_results)
    evaluated = [filtering.evaluate_video(item).model_dump() for item in raw_results]
    search_history_service.add(q, result_count=len(evaluated), mode=mode)
    return {
        "query": q,
        "mode": mode,
        "notice": search_notice(mode),
        "results": evaluated,
    }


def search_notice(mode: str) -> str | None:
    if mode == "demo":
        return "YOUTUBE_API_KEY is not configured. Showing demo results."
    if mode == "cache":
        return "Showing cached YouTube results."
    return None


@app.get("/api/youtube/history")
async def read_youtube_history() -> dict[str, object]:
    return {"items": [entry.model_dump(mode="json") for entry in search_history_service.list_entries()]}


@app.get("/api/youtube/thumbnail")
async def proxy_youtube_thumbnail(url: str = Query(min_length=1, max_length=500)) -> Response:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in THUMBNAIL_HOSTS:
        raise HTTPException(status_code=400, detail="Thumbnail host is not allowed")

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        response = await client.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "image/jpeg")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Thumbnail response is not an image")
    return Response(content=response.content, media_type=content_type)


@app.delete("/api/youtube/history")
async def clear_youtube_history() -> dict[str, str]:
    search_history_service.clear()
    return {"status": "cleared"}


@app.post("/api/youtube/approval/unlock")
async def unlock_youtube_approval(request: ViewPinRequest) -> dict[str, str]:
    verify_view_pin(request.pin)
    if request.video_id.startswith("demo-"):
        raise HTTPException(status_code=400, detail="Demo result cannot be played")
    return {"status": "unlocked", "watch_url": f"/youtube/watch/{request.video_id}"}


@app.get("/api/usage/status")
async def read_usage_status() -> dict[str, object]:
    config = get_config()
    return usage_tracker_service.status(config.limits.daily_minutes).model_dump(mode="json")


@app.post("/api/usage/playback/start")
async def start_playback_usage(request: PlaybackStartRequest) -> dict[str, object]:
    config = get_config()
    try:
        session = usage_tracker_service.start_session(request.video_id, config.limits.daily_minutes)
    except RuntimeError:
        raise HTTPException(status_code=429, detail="Daily viewing limit reached") from None
    return {
        "session_id": session.session_id,
        "usage": usage_tracker_service.status(config.limits.daily_minutes).model_dump(mode="json"),
    }


@app.post("/api/usage/playback/heartbeat")
async def heartbeat_playback_usage(request: PlaybackHeartbeatRequest) -> dict[str, object]:
    config = get_config()
    player_state = "playing" if request.state == "playing" else "paused"
    usage = usage_tracker_service.heartbeat(request.session_id, player_state, config.limits.daily_minutes)
    return {"usage": usage.model_dump(mode="json")}


@app.post("/api/usage/playback/stop")
async def stop_playback_usage(request: PlaybackStopRequest) -> dict[str, str]:
    usage_tracker_service.stop_session(request.session_id)
    return {"status": "stopped"}


@app.post("/api/admin/state")
async def read_admin_state(request: ParentPinRequest, http_request: Request) -> dict[str, object]:
    config = verify_parent_pin(request.pin, http_request)
    return {
        "config": config.model_dump(mode="json"),
        "network": network_info_service.get_info().model_dump(mode="json"),
        "network_access": read_network_access_state().model_dump(mode="json"),
        "storage": read_storage_info().model_dump(mode="json"),
        "monitoring": read_system_monitoring().model_dump(mode="json"),
        "youtube": youtube_service.status(),
        "usage": usage_tracker_service.status(config.limits.daily_minutes).model_dump(mode="json"),
        "history": [entry.model_dump(mode="json") for entry in search_history_service.list_entries()],
    }


@app.post("/api/admin/youtube/history/clear")
async def clear_admin_youtube_history(request: ParentPinRequest, http_request: Request) -> dict[str, str]:
    verify_parent_pin(request.pin, http_request)
    search_history_service.clear()
    return {"status": "cleared"}


@app.put("/api/parent/youtube/key")
async def update_youtube_key(request: YouTubeKeyUpdate, http_request: Request) -> dict[str, object]:
    verify_parent_pin(request.pin, http_request)
    try:
        result = youtube_key_manager.set_key(request.api_key)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    youtube_search_cache_service.clear()
    return {"key": result.model_dump(mode="json"), "youtube": youtube_service.status()}


@app.delete("/api/parent/youtube/key")
async def clear_youtube_key(request: ParentPinRequest, http_request: Request) -> dict[str, object]:
    verify_parent_pin(request.pin, http_request)
    try:
        result = youtube_key_manager.clear_key()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    youtube_search_cache_service.clear()
    return {"key": result.model_dump(mode="json"), "youtube": youtube_service.status()}


@app.post("/api/parent/network-access")
async def update_parent_network_access(request: NetworkAccessUpdate, http_request: Request) -> NetworkAccessState:
    verify_parent_pin(request.pin, http_request)
    try:
        return set_network_access_state(request.enabled)
    except OSError:
        raise HTTPException(status_code=500, detail="Network access update failed") from None


@app.post("/api/parent/display")
async def update_parent_display(request: DisplayModeUpdate, http_request: Request) -> DisplayStatus:
    config = verify_parent_pin(request.pin, http_request)
    if request.mode not in {"1080p", "4k"}:
        raise HTTPException(status_code=400, detail="Unsupported display mode")
    config.display.mode = request.mode
    config_service.save(config)
    try:
        return display_manager.apply(request.mode)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/parent/storage")
async def read_parent_storage(request: ParentPinRequest, http_request: Request) -> StorageInfo:
    verify_parent_pin(request.pin, http_request)
    return read_storage_info()


@app.post("/api/parent/monitoring")
async def read_parent_monitoring(request: ParentPinRequest, http_request: Request) -> SystemMonitoring:
    verify_parent_pin(request.pin, http_request)
    return read_system_monitoring()


@app.post("/api/parent/wifi/status")
async def read_parent_wifi_status(request: ParentPinRequest, http_request: Request) -> WifiStatus:
    verify_parent_pin(request.pin, http_request)
    try:
        return wifi_manager.status()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/parent/wifi/scan")
async def scan_parent_wifi(request: ParentPinRequest, http_request: Request) -> dict[str, list[WifiNetwork]]:
    verify_parent_pin(request.pin, http_request)
    try:
        return {"networks": wifi_manager.scan()}
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/parent/wifi/connect")
async def connect_parent_wifi(request: WifiConnectRequest, http_request: Request) -> WifiConnectResult:
    verify_parent_pin(request.pin, http_request)
    try:
        return wifi_manager.connect(request.ssid, request.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/parent/terminal/start")
async def start_debug_terminal(request: ParentPinRequest, http_request: Request, background_tasks: BackgroundTasks) -> SystemActionResult:
    verify_parent_pin(request.pin, http_request)
    background_tasks.add_task(
        run_systemctl_sequence,
        [
            ["sudo", "-n", "systemctl", "stop", "kid-portal-kiosk.service"],
            ["sudo", "-n", "systemctl", "stop", "kid-portal-x.service"],
            ["sudo", "-n", "systemctl", "unmask", "getty@tty1.service"],
            ["sudo", "-n", "systemctl", "reset-failed", "getty@tty1.service"],
            ["sudo", "-n", "systemctl", "start", "getty@tty1.service"],
        ],
    )
    return SystemActionResult(status="terminal_starting")


@app.post("/api/parent/kiosk/start")
async def return_to_kiosk(request: ParentPinRequest, http_request: Request, background_tasks: BackgroundTasks) -> SystemActionResult:
    verify_parent_pin(request.pin, http_request)
    background_tasks.add_task(
        run_systemctl_sequence,
        [
            ["sudo", "-n", "systemctl", "stop", "getty@tty1.service"],
            ["sudo", "-n", "systemctl", "mask", "getty@tty1.service"],
            ["sudo", "-n", "systemctl", "reset-failed", "getty@tty1.service", "kid-portal-x.service", "kid-portal-kiosk.service"],
            ["sudo", "-n", "systemctl", "start", "kid-portal-x.service"],
            ["sudo", "-n", "systemctl", "start", "kid-portal-kiosk.service"],
        ],
    )
    return SystemActionResult(status="kiosk_starting")


@app.get("/youtube/watch/{video_id}", response_class=HTMLResponse)
async def watch_youtube(video_id: str) -> str:
    config = get_config()
    if usage_tracker_service.status(config.limits.daily_minutes).limit_reached:
        return render_watch_page(video_id, limit_reached=True)
    return render_watch_page(video_id)


@app.get("/api/policies/chromium")
async def chromium_policy() -> dict[str, object]:
    return PolicyManager(get_config()).build_policy()


@app.post("/api/parent/unrestricted/start")
async def start_unrestricted_mode(request: Request) -> dict[str, object]:
    body = await request.json()
    pin = str(body.get("pin", ""))
    config = verify_parent_pin(pin, request)
    minutes = int(body.get("minutes") or config.parent.default_unrestricted_minutes)
    return {"status": "enabled", "minutes": minutes}


@app.post("/api/parent/unlock")
async def unlock_parent_settings(request: Request) -> dict[str, str]:
    body = await request.json()
    pin = str(body.get("pin", ""))
    config = verify_parent_pin(pin, request)
    return {"status": "unlocked"}
