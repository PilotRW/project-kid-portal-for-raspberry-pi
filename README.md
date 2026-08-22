# Kid Portal for Raspberry Pi

A Raspberry Pi family media kiosk focused on safe web browsing and curated YouTube access for children.

The POC boots into Chromium kiosk mode pointed at a local FastAPI app. The browser is locked down with Chromium Enterprise Policies, while YouTube is accessed through a custom frontend backed by the YouTube Data API and a configurable filtering engine.

## Current State

The current validated device is a Raspberry Pi 5 B 8 GB running Raspberry Pi OS Lite 64-bit. It boots directly into the kiosk on HDMI, serves the parent admin UI on LAN port `80`, keeps the content app on local port `8080` by default, and exposes only SSH/admin on the LAN firewall.

Raspberry Pi 4 should remain compatible with the same architecture, but should be validated before treating it as production hardware. Raspberry Pi Zero 2 W is not a recommended target for the full Chromium + YouTube kiosk experience; it may run a reduced/minimal build, but the project should not promise smooth video playback, 4K output, or comfortable admin/kiosk performance on Zero-class hardware.

## Components

- `app/main.py` - FastAPI application and API routes.
- `app/services/config_service.py` - JSON/YAML configuration loading and saving.
- `app/services/filtering_engine.py` - ALLOW/BLOCK/REQUIRE_PARENT_APPROVAL decision pipeline.
- `app/services/filter_insights.py` - bounded aggregated filter gap and parent approval counters.
- `app/services/policy_manager.py` - Chromium Enterprise Policy JSON generation.
- `app/services/usage_tracker.py` - daily viewing limit tracking based on active YouTube playback.
- `app/services/youtube_approval_log.py` - bounded parent approval audit trail.
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
- reviewing parent approval logs and aggregated unmatched/default-allow filter gaps;
- changing the separate viewing approval PIN;
- configuring daily playback limits, max video duration, and short-video handling;
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

Parent-approved YouTube videos are recorded in a bounded audit log. Local storage defaults to `config/youtube-approval-log.json`; on the Pi set `KID_PORTAL_YOUTUBE_APPROVAL_LOG=/etc/kid-portal/youtube-approval-log.json`.

Filter tuning insights are stored as a bounded, deduplicated counter map instead of an append-only event log. It records default-allow gaps and repeated viewing PIN approvals by channel/title with counts. Local storage defaults to `config/filter-insights.json`; on the Pi set `KID_PORTAL_FILTER_INSIGHTS=/etc/kid-portal/filter-insights.json`.

Daily viewing limits count active YouTube playback, not kiosk uptime. The local default storage path is `config/usage.json`; on the Pi you can set `KID_PORTAL_USAGE=/etc/kid-portal/usage.json`.

No allowlists, blocklists, PINs, or time limits are hardcoded in the app.

If the parent/admin PIN is forgotten, reset it from a trusted local shell or SSH session on the Pi:

```bash
sudo kid-portal-reset-parent-pin 1234
```

This recovery tool edits `/etc/kid-portal/config.json` directly and is not exposed to the web app or sudoers rules.

## Raspberry Pi Deployment

Start with [docs/sd-card-prep.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/sd-card-prep.md), then continue with [docs/raspberry-pi-setup.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/raspberry-pi-setup.md).

For repeatable installs and updates, use [docs/deploy-automation.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/deploy-automation.md):

```bash
./deploy/bootstrap-pi.sh 192.168.0.142 pi
./deploy/deploy-to-pi.sh 192.168.0.142 pi
./deploy/check-pi.sh 192.168.0.142 pi
```

Security posture and production checks are tracked in [docs/security.md](/Users/pilotrw/GITHUB/project-kid-portal-for-raspberry-pi/docs/security.md).

The deployment design targets Raspberry Pi OS Lite 64-bit on Raspberry Pi 5 first, with Raspberry Pi 4 compatibility intended. Raspberry Pi Zero 2 W is architecture-compatible only in the sense that the same services/scripts do not depend on Pi 5-specific APIs; it is not a validated or recommended performance target for the full kiosk.
