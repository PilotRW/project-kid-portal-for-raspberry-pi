# Kid Portal for Raspberry Pi

A Raspberry Pi family media kiosk focused on safe web browsing and curated YouTube access for children.

The POC boots into Chromium kiosk mode pointed at a local FastAPI app. The browser is locked down with Chromium Enterprise Policies, while YouTube is accessed through a custom frontend backed by the YouTube Data API and a configurable filtering engine.

## Components

- `app/main.py` - FastAPI application and API routes.
- `app/services/config_service.py` - JSON/YAML configuration loading and saving.
- `app/services/filtering_engine.py` - ALLOW/BLOCK/REQUIRE_PARENT_APPROVAL decision pipeline.
- `app/services/policy_manager.py` - Chromium Enterprise Policy JSON generation.
- `app/services/youtube_api.py` - YouTube Data API adapter.
- `app/static/` - TV-friendly kiosk UI controlled by arrow keys, OK, and Back/Escape.
- `deploy/systemd/` - systemd units for kiosk app and Chromium launcher.
- `deploy/chromium/` - Chromium policy template.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`.

On the Pi, the systemd service listens on `0.0.0.0:8080`, so Settings can show LAN URLs such as `http://192.168.1.50:8080` and SSH hints such as `ssh pi@192.168.1.50`.

## Remote Admin

Open `http://127.0.0.1:8080/admin` locally, or use the LAN address shown in Settings, for example `http://192.168.1.50:8080/admin`.

The admin page is PIN protected and supports:

- viewing LAN portal URLs and SSH targets;
- checking YouTube live/demo status;
- viewing and clearing YouTube search history;
- editing allowed websites;
- editing allowed/blocked keywords and channels.

The YouTube API key is never shown in the admin page.

## Configuration

Default config lives in [config/kid-portal.json](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/config/kid-portal.json).

On the Pi, set:

```bash
export KID_PORTAL_CONFIG=/etc/kid-portal/config.json
export YOUTUBE_API_KEY=your_api_key
```

For local testing without restarting the app, put the key in `config/youtube-api-key.txt`. This file is ignored by git.

If `YOUTUBE_API_KEY` is missing, the YouTube search screen runs in demo mode and shows a warning in the UI instead of pretending that live YouTube search is active.

YouTube search history is stored as JSON. By default it uses `config/search-history.json` locally; on the Pi you can set `KID_PORTAL_SEARCH_HISTORY=/etc/kid-portal/search-history.json`.

No allowlists, blocklists, PINs, or time limits are hardcoded in the app.

## Raspberry Pi Deployment

Start with [docs/sd-card-prep.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/sd-card-prep.md), then continue with [docs/raspberry-pi-setup.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/raspberry-pi-setup.md).

The deployment design targets Raspberry Pi OS Lite 64-bit, Raspberry Pi Zero 2 W, and remains compatible with Raspberry Pi 4/5.
