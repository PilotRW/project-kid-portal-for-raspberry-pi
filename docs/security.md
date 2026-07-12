# Security Notes

This project is designed as an HDMI-first kiosk. The child-facing content UI runs locally on the Raspberry Pi display, while LAN access is reserved for parent administration.

## Network Surfaces

- `127.0.0.1:8080` is the kiosk/content app used by Chromium on HDMI.
- `LAN:80` is the parent admin surface and serves Settings as the default page.
- `LAN:8080` is closed by default. It can be opened temporarily from Settings with the "Expose content on LAN" switch.
- `SSH:22` should be allowed only from the home LAN.

The `8080` exposure switch does not grant the FastAPI web process broad sudo access. The admin app writes a request file under `/run/kid-portal`, and `kid-portal-network-access.path` triggers a narrow root oneshot that only applies or removes the UFW rule for port `8080`.

## UFW

Expected default LAN rules:

```text
22/tcp ALLOW 192.168.0.0/24
80/tcp ALLOW 192.168.0.0/24
```

Port `8080` should appear only while content LAN access is intentionally enabled.

Useful checks:

```bash
sudo ufw status
cat /run/kid-portal/network-access.state
```

## fail2ban

The deployed fail2ban jail protects SSH:

```ini
[sshd]
enabled = true
backend = systemd
port = ssh
maxretry = 4
findtime = 10m
bantime = 1h
```

Useful checks:

```bash
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

## Admin PIN Attempts

The admin PIN is protected in the FastAPI app because fail2ban only sees SSH failures by default.

Defaults:

- `KID_PORTAL_ADMIN_PIN_MAX_ATTEMPTS=8`
- `KID_PORTAL_ADMIN_PIN_FINDTIME_SECONDS=600`
- `KID_PORTAL_ADMIN_PIN_LOCKOUT_SECONDS=600`

After too many invalid PIN attempts from the same client IP, admin endpoints return `429` with a `Retry-After` header. A successful PIN clears the failed-attempt counter.

## Secrets and PINs

- Do not keep default SSH passwords in production.
- Change the parent admin PIN and separate viewing approval PIN before real child use.
- Keep `YOUTUBE_API_KEY` in `/etc/kid-portal/youtube.env` or a root-owned key file, not in git.
- The admin API does not return the YouTube API key.

## Runtime Cleanup

Temporary files used during manual deployment can be removed after a successful deploy:

```bash
rm -f /tmp/main.py /tmp/admin.html /tmp/admin.js /tmp/admin.css /tmp/kid-portal-admin.service
rm -f /tmp/kid-portal-network-access.service /tmp/kid-portal-network-access.path
rm -f /tmp/kid-portal-network-access.sh /tmp/kid-portal-tmpfiles.conf
```
