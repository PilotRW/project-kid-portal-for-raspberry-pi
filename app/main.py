import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.services.config_service import ConfigService, PortalConfig
from app.services.filtering_engine import FilteringEngine
from app.services.network_info import NetworkInfoService
from app.services.policy_manager import PolicyManager
from app.services.search_history import SearchHistoryService
from app.services.youtube_api import YouTubeApiService

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

config_service = ConfigService()
youtube_service = YouTubeApiService()
search_history_service = SearchHistoryService()
network_info_service = NetworkInfoService()
THUMBNAIL_HOSTS = {"i.ytimg.com", "s.ytimg.com"}

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


class SystemActionResult(BaseModel):
    status: str


def verify_parent_pin(pin: str) -> PortalConfig:
    config = get_config()
    if not config.parent.verify_pin(pin):
        raise HTTPException(status_code=403, detail="Invalid PIN")
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


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
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
async def write_parent_config(update: ParentConfigUpdate) -> dict[str, str]:
    verify_parent_pin(update.pin)
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
    raw_results = await youtube_service.search(q, limit=config.youtube.max_results, safe_search=config.youtube.safe_search)
    evaluated = [filtering.evaluate_video(item).model_dump() for item in raw_results]
    mode = youtube_service.status()["mode"]
    search_history_service.add(q, result_count=len(evaluated), mode=mode)
    return {
        "query": q,
        "mode": mode,
        "notice": None if mode == "live" else "YOUTUBE_API_KEY is not configured. Showing demo results.",
        "results": evaluated,
    }


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


@app.post("/api/admin/state")
async def read_admin_state(request: ParentPinRequest) -> dict[str, object]:
    config = verify_parent_pin(request.pin)
    return {
        "config": config.model_dump(mode="json"),
        "network": network_info_service.get_info().model_dump(mode="json"),
        "youtube": youtube_service.status(),
        "history": [entry.model_dump(mode="json") for entry in search_history_service.list_entries()],
    }


@app.post("/api/admin/youtube/history/clear")
async def clear_admin_youtube_history(request: ParentPinRequest) -> dict[str, str]:
    verify_parent_pin(request.pin)
    search_history_service.clear()
    return {"status": "cleared"}


@app.post("/api/parent/storage")
async def read_parent_storage(request: ParentPinRequest) -> StorageInfo:
    verify_parent_pin(request.pin)
    usage = shutil.disk_usage("/")
    used = usage.total - usage.free
    return StorageInfo(
        path="/",
        total_bytes=usage.total,
        used_bytes=used,
        free_bytes=usage.free,
        percent_used=round((used / usage.total) * 100, 1) if usage.total else 0,
    )


@app.post("/api/parent/monitoring")
async def read_parent_monitoring(request: ParentPinRequest) -> SystemMonitoring:
    verify_parent_pin(request.pin)
    try:
        output = subprocess.check_output(
            ["ps", "-eo", "pid,user,pcpu,pmem,comm,args", "--sort=-pcpu"],
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return SystemMonitoring(top_processes=[], hottest_process=None)
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
    return SystemMonitoring(top_processes=rows, hottest_process=rows[0] if rows else None)


@app.post("/api/parent/terminal/start")
async def start_debug_terminal(request: ParentPinRequest, background_tasks: BackgroundTasks) -> SystemActionResult:
    verify_parent_pin(request.pin)
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
async def return_to_kiosk(request: ParentPinRequest, background_tasks: BackgroundTasks) -> SystemActionResult:
    verify_parent_pin(request.pin)
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
    return (STATIC_DIR / "watch.html").read_text(encoding="utf-8").replace("__VIDEO_ID__", video_id)


@app.get("/api/policies/chromium")
async def chromium_policy() -> dict[str, object]:
    return PolicyManager(get_config()).build_policy()


@app.post("/api/parent/unrestricted/start")
async def start_unrestricted_mode(request: Request) -> dict[str, object]:
    body = await request.json()
    pin = str(body.get("pin", ""))
    config = verify_parent_pin(pin)
    minutes = int(body.get("minutes") or config.parent.default_unrestricted_minutes)
    return {"status": "enabled", "minutes": minutes}


@app.post("/api/parent/unlock")
async def unlock_parent_settings(request: Request) -> dict[str, str]:
    body = await request.json()
    pin = str(body.get("pin", ""))
    config = verify_parent_pin(pin)
    return {"status": "unlocked"}
