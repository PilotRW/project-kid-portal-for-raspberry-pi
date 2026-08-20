# Raspberry Pi Setup

Target: Raspberry Pi OS Lite 64-bit on Raspberry Pi Zero 2 W, Pi 4, or Pi 5.

Before this step, prepare the microSD card and first boot:

[Підготовка microSD](./sd-card-prep.md)

## 1. Install OS Packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip chromium-browser xserver-xorg xinit openbox unclutter keyd rsync network-manager
```

## 2. Install Application

```bash
sudo mkdir -p /opt/kid-portal /etc/kid-portal /etc/chromium/policies/managed
sudo rsync -av --delete ./ /opt/kid-portal/
sudo chown -R pi:pi /opt/kid-portal
cd /opt/kid-portal
python3 -m venv .venv
.venv/bin/pip install -e .
sudo cp config/kid-portal.json /etc/kid-portal/config.json
sudo chown root:pi /etc/kid-portal/config.json
sudo chmod 664 /etc/kid-portal/config.json
sudo touch /etc/kid-portal/search-history.json
sudo chown pi:pi /etc/kid-portal/search-history.json
sudo touch /etc/kid-portal/youtube-search-cache.json
sudo chown pi:pi /etc/kid-portal/youtube-search-cache.json
sudo chmod 600 /etc/kid-portal/youtube-search-cache.json
```

Optional YouTube API key:

```bash
sudo install -m 640 -o root -g pi ./config/youtube-api-key.txt /etc/kid-portal/youtube-api-key.txt
sudo tee /etc/kid-portal/youtube.env >/dev/null <<EOF
YOUTUBE_API_KEY_FILE=/etc/kid-portal/youtube-api-key.txt
KID_PORTAL_SEARCH_HISTORY=/etc/kid-portal/search-history.json
KID_PORTAL_YOUTUBE_SEARCH_CACHE=/etc/kid-portal/youtube-search-cache.json
EOF
sudo chmod 600 /etc/kid-portal/youtube.env
```

Without `YOUTUBE_API_KEY`, the kiosk still starts, but YouTube search uses demo data and shows a demo-mode warning.

For local development only, the app also checks `config/youtube-api-key.txt` on every search. Do not commit that file.

## 3. Generate Chromium Policy

During development, inspect the active policy:

```bash
curl http://127.0.0.1:8080/api/policies/chromium
```

Install the generated policy after the backend is running, so Chromium uses the
current `/etc/kid-portal/config.json` whitelist:

```bash
curl -s http://127.0.0.1:8080/api/policies/chromium | sudo tee /etc/chromium/policies/managed/kid-portal.json >/dev/null
```

## 4. Install systemd Services

```bash
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo cp deploy/systemd/*.path /etc/systemd/system/
sudo cp deploy/tmpfiles/kid-portal.conf /etc/tmpfiles.d/kid-portal.conf
sudo systemd-tmpfiles --create /etc/tmpfiles.d/kid-portal.conf
sudo cp deploy/scripts/kid-portal-network-access.sh /usr/local/sbin/kid-portal-network-access
sudo chmod 755 /usr/local/sbin/kid-portal-network-access
sudo cp deploy/scripts/kid-portal-display-mode.sh /usr/local/sbin/kid-portal-display-mode
sudo chmod 755 /usr/local/sbin/kid-portal-display-mode
sudo cp deploy/scripts/kid-portal-wifi.sh /usr/local/sbin/kid-portal-wifi
sudo chmod 755 /usr/local/sbin/kid-portal-wifi
sudo cp deploy/scripts/kid-portal-youtube-key.sh /usr/local/sbin/kid-portal-youtube-key
sudo chmod 755 /usr/local/sbin/kid-portal-youtube-key
sudo mkdir -p /etc/sudoers.d
sudo cp deploy/sudoers/kid-portal-wifi /etc/sudoers.d/kid-portal-wifi
sudo cp deploy/sudoers/kid-portal-youtube-key /etc/sudoers.d/kid-portal-youtube-key
sudo chmod 440 /etc/sudoers.d/kid-portal-wifi
sudo chmod 440 /etc/sudoers.d/kid-portal-youtube-key
sudo mkdir -p /etc/X11/xorg.conf.d
sudo cp deploy/xorg/99-kid-portal.conf /etc/X11/xorg.conf.d/99-kid-portal.conf
sudo systemctl daemon-reload
sudo systemctl enable kid-portal.service kid-portal-admin.service kid-portal-network-access.path kid-portal-x.service kid-portal-kiosk.service
sudo ufw allow from 192.168.0.0/24 to any port 80 proto tcp
sudo ufw delete allow from 192.168.0.0/24 to any port 8080 proto tcp
sudo reboot
```

See [Security Notes](./security.md) for the expected UFW, fail2ban, admin PIN lockout, and runtime cleanup checks.

## 5. Kiosk Hardening Notes

- Configure automatic login on tty1 with `raspi-config`.
- Keep the Pi user unprivileged for day-to-day kiosk operation.
- Chromium Enterprise Policies block all URLs except localhost and configured allowlist patterns.
- Browser restart is handled by `Restart=always` in systemd.
- Keyboard shortcut suppression should be reinforced at the input layer. See `deploy/input/keyd-kid-portal.conf`.
- Physical shell access should require a separate admin path, not the child remote.

Install the example input hardening profile:

```bash
sudo cp deploy/input/keyd-kid-portal.conf /etc/keyd/default.conf
sudo systemctl enable --now keyd
```

## 6. Production Gaps After POC

- Persist and enforce real temporary unrestricted mode timeout.
- Add browsing history storage.
- Add AI classification module behind the filtering engine.
- Add input-layer shortcut blocking with `interception-tools`, `keyd`, or a remote-only input profile.
