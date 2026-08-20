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
