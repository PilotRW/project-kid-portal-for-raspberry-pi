# Kid Portal for Raspberry Pi

A Raspberry Pi family media kiosk focused on safe web browsing and curated YouTube access for children.

The POC boots into Chromium kiosk mode pointed at a local FastAPI app. The browser is locked down with Chromium Enterprise Policies, while YouTube is accessed through a custom frontend backed by the YouTube Data API and a configurable filtering engine.

## Components

- `app/main.py` - FastAPI application and API routes.
- `app/services/config_service.py` - JSON/YAML configuration loading and saving.
- `app/services/filtering_engine.py` - ALLOW/BLOCK/REQUIRE_PARENT_APPROVAL decision pipeline.
- `app/services/policy_manager.py` - Chromium Enterprise Policy JSON generation.
- `app/services/usage_tracker.py` - daily viewing limit tracking based on active YouTube playback.
- `app/services/youtube_api.py` - YouTube Data API adapter.
- `app/static/` - TV-friendly kiosk UI controlled by arrow keys, OK, and Back/Escape.
- `deploy/systemd/` - systemd units for kiosk app, LAN admin, firewall toggle helper, and Chromium launcher.
- `deploy/scripts/` - privileged helper scripts used by narrow systemd units.
- `deploy/chromium/` - Chromium policy template.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`.

On the Pi, Chromium uses `http://127.0.0.1:8080/` over HDMI. LAN access to content on port `8080` is closed by default and can be opened from Settings when needed.

## Remote Admin

Open `http://127.0.0.1:8080/admin` locally. From another device on the home network, open the Pi IP directly, for example `http://192.168.1.50/`; the LAN admin service runs on port `80` and serves Settings as its default page.

The admin page is PIN protected and split into tabs for overview, network, playback, YouTube filtering, websites, and debug controls. It supports:

- viewing LAN portal URLs and SSH targets;
- opening or closing LAN access to the kiosk content port `8080`;
- viewing storage, top CPU processes, temperature, and throttling state;
- checking YouTube live/demo status;
- viewing and clearing YouTube search history;
- changing the separate viewing approval PIN;
- configuring daily playback limits and max video duration;
- editing allowed websites;
- editing allowed/blocked keywords, channels, approval keywords, and blocked categories;
- opening a debug terminal on the HDMI display and returning to kiosk mode.

The port `8080` LAN switch is intentionally not implemented as broad `sudo` from the web process. The admin app writes a request under `/run/kid-portal`, and a narrow systemd path/oneshot applies only the firewall rule for content access.

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

YouTube API search responses are cached for 7 days by default to avoid burning the small daily `search.list` quota on repeated searches. Local cache defaults to `config/youtube-search-cache.json`; on the Pi set `KID_PORTAL_YOUTUBE_SEARCH_CACHE=/etc/kid-portal/youtube-search-cache.json`. Override the TTL with `KID_PORTAL_YOUTUBE_SEARCH_CACHE_TTL_SECONDS`.

Daily viewing limits count active YouTube playback, not kiosk uptime. The local default storage path is `config/usage.json`; on the Pi you can set `KID_PORTAL_USAGE=/etc/kid-portal/usage.json`.

No allowlists, blocklists, PINs, or time limits are hardcoded in the app.

## Raspberry Pi Deployment

Start with [docs/sd-card-prep.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/sd-card-prep.md), then continue with [docs/raspberry-pi-setup.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/raspberry-pi-setup.md).

Security posture and production checks are tracked in [docs/security.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/security.md).

The deployment design targets Raspberry Pi OS Lite 64-bit, Raspberry Pi Zero 2 W, and remains compatible with Raspberry Pi 4/5.
