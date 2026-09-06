# Deploy Automation

These scripts turn a freshly imaged Raspberry Pi OS Lite device into a Kid Portal kiosk without repeating manual setup.

Validated hardware today is Raspberry Pi 5 B 8 GB. Raspberry Pi 4 is expected to remain compatible with the same scripts, but needs validation on real hardware. Raspberry Pi Zero 2 W is not recommended for the full Chromium + YouTube kiosk and should be treated as experimental/minimal.

## First Device Bootstrap

Prerequisites:

- Raspberry Pi OS Lite is already flashed.
- SSH is enabled in Raspberry Pi Imager.
- The Pi is reachable from the Mac.
- The SSH user can run `sudo`.

From the project root on the Mac:

```bash
./deploy/bootstrap-pi.sh 192.168.0.142 pi
```

The script copies the repo to `/tmp/kid-portal-bootstrap`, runs the installer on the Pi, installs packages, configures services/security, and reboots.

For a different LAN subnet:

```bash
KID_PORTAL_LAN_CIDR=192.168.1.0/24 ./deploy/bootstrap-pi.sh 192.168.1.50 pi
```

## Tailscale Management Network

Kid Portal can join a private Tailscale tailnet during bootstrap. This is opt-in and intended for SSH, health checks, deploys, monitoring, and remote parent admin access. It does not expose the child-facing content service on port `8080`.

Use a one-off or tagged pre-auth key from Tailscale and pass it through the environment. Do not commit auth keys into this repo.

```bash
export KID_PORTAL_ENABLE_TAILSCALE=1
export KID_PORTAL_TAILSCALE_AUTHKEY=tskey-auth-...
export KID_PORTAL_TAILSCALE_HOSTNAME=kid-portal-home
export KID_PORTAL_TAILSCALE_TAGS=tag:kid-portal
./deploy/bootstrap-pi.sh 192.168.0.142 pi
```

Defaults:

- LAN SSH remains open: `KID_PORTAL_ALLOW_LAN_SSH=1`.
- Tailscale management CIDR is `100.64.0.0/10`.
- UFW allows ports `22` and `80` from Tailscale only on interface `tailscale0`.
- Admin stays on port `80`.
- Content port `8080` remains closed to LAN/Tailscale unless the parent explicitly enables the existing 8080 exposure switch.

After the device appears in Tailscale, update and check it through its MagicDNS name or Tailscale IP:

```bash
./deploy/deploy-to-pi.sh kid-portal-home.your-tailnet.ts.net pi
./deploy/check-pi.sh kid-portal-home.your-tailnet.ts.net pi
```

If you want to close LAN SSH later, first verify Tailscale SSH works, then run deploy with:

```bash
KID_PORTAL_ENABLE_TAILSCALE=1 KID_PORTAL_ALLOW_LAN_SSH=0 ./deploy/deploy-to-pi.sh kid-portal-home.your-tailnet.ts.net pi
```

## Fleet Inventory

For multiple family devices, keep real inventory and auth-key environment variable names in `.local/devices.json`; `.local/` is ignored by git.

Start from the example:

```bash
mkdir -p .local
cp deploy/devices.example.json .local/devices.json
```

Then edit `.local/devices.json` for real hosts and Tailscale names. The inventory should reference auth keys by environment variable name, not store auth-key values.

Fleet commands:

```bash
./deploy/fleet-list.sh
./deploy/fleet-bootstrap.sh home
./deploy/fleet-check.sh all
./deploy/fleet-deploy.sh all
```

For `bootstrap`, the fleet runner uses the device `host` field, usually the temporary LAN IP from Raspberry Pi Imager. For `deploy` and `check`, it prefers `management_host`, usually the Tailscale MagicDNS name or Tailscale IP.

## Update Existing Device

```bash
./deploy/deploy-to-pi.sh 192.168.0.142 pi
```

This skips `apt`, preserves `/etc/kid-portal/config.json`, updates app code/systemd/helpers, regenerates Chromium policy, and restarts services.

## Health Check

```bash
./deploy/check-pi.sh 192.168.0.142 pi
```

It checks:

- IP addresses;
- SSH, fail2ban, app/admin/kiosk services;
- UFW status;
- fail2ban SSH jail;
- YouTube status;
- parent admin state;
- current HDMI mode.

## What Bootstrap Installs

- Python virtualenv app under `/opt/kid-portal`;
- runtime config and history under `/etc/kid-portal`;
- Chromium Enterprise Policy under `/etc/chromium/policies/managed`;
- systemd services for backend, admin, X, Chromium kiosk, and 8080 exposure helper;
- fail2ban SSH jail;
- SSH hardening drop-in;
- UFW rules for LAN-only SSH/admin;
- keyd input hardening;
- narrow sudoers helpers for Wi-Fi, YouTube API key management, and system software updates.

## Raspberry Pi Software Updates

Open admin, then use:

```text
Debug -> Raspberry Pi Software -> Update software
```

This starts `apt-get update`, `apt-get -y full-upgrade`, and `apt-get -y autoremove` in the background on the Pi. Output is written to:

```text
/var/log/kid-portal-software-update.log
```

## YouTube API Key

Do not bake API keys into the repo. After bootstrap, open admin:

```text
http://<pi-ip>/
```

Then use:

```text
YouTube -> YouTube API Key
```

The key is stored at `/etc/kid-portal/youtube-api-key.txt` and is not returned by admin APIs.
