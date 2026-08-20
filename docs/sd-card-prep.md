# Підготовка microSD для Raspberry Pi

Це інструкція для першої підготовки карти пам'яті під Kid Portal kiosk.

Цільова ОС: Raspberry Pi OS Lite 64-bit.

## 1. Що потрібно

- Raspberry Pi 5 рекомендовано для поточного повного кіоску.
- Raspberry Pi 4 має бути сумісною ціллю, але її треба окремо перевірити.
- Raspberry Pi Zero 2 W не варто обіцяти як повноцінну ціль для Chromium + YouTube kiosk; максимум експериментальний/minimal режим.
- microSD 16 GB або більше, краще 32 GB.
- Кардрідер.
- Комп'ютер з macOS, Windows або Linux.
- Raspberry Pi Imager.
- Wi-Fi назва мережі та пароль, якщо Pi буде без Ethernet.

## 2. Записати ОС через Raspberry Pi Imager

1. Встав microSD в комп'ютер.
2. Відкрий Raspberry Pi Imager.
3. Device: вибери свою модель Raspberry Pi.
4. OS: `Raspberry Pi OS Lite (64-bit)`.
5. Storage: вибери microSD карту.
6. Відкрий OS customization.

У customization задай:

- Hostname: `kid-portal`
- Username: `pi`
- Password: свій пароль, не залишай дефолтний.
- Configure wireless LAN: увімкнути, якщо потрібен Wi-Fi.
- Wireless SSID: назва домашньої Wi-Fi мережі.
- Wireless password: пароль Wi-Fi.
- Wireless LAN country: твоя країна.
- Set locale settings: увімкнути.
- Time zone: `Europe/Vienna` або свою.
- Keyboard layout: зручну для тебе.
- Enable SSH: увімкнути.
- SSH authentication: password або public key.

Після цього натисни Write і дочекайся завершення verify.

## 3. Перший запуск

1. Вийми microSD з комп'ютера.
2. Встав її в Raspberry Pi.
3. Підключи HDMI monitor.
4. Підключи USB/Bluetooth remote або клавіатуру для першої діагностики.
5. Увімкни живлення.
6. Почекай 1-3 хвилини на перший boot.

## 4. Знайти IP адресу Raspberry Pi

Найпростіші варіанти:

- Подивитись у router/admin panel список DHCP clients.
- Шукати hostname `kid-portal`.
- Спробувати з комп'ютера:

```bash
ssh pi@kid-portal.local
```

Якщо `.local` не працює, використай IP з router panel:

```bash
ssh pi@192.168.1.50
```

Після входу на Pi можна перевірити IP адресу так:

```bash
hostname -I
```

## 5. Оновити систему

Після першого SSH login виконай:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Після reboot зайди знову:

```bash
ssh pi@kid-portal.local
```

або:

```bash
ssh pi@192.168.1.50
```

## 6. Увімкнути автоматичний login

Для kiosk потрібен automatic login, щоб користувач не бачив login prompt.

На Pi:

```bash
sudo raspi-config
```

Далі:

```text
System Options
Boot / Auto Login
Console Autologin
```

Після зміни можна перезавантажити:

```bash
sudo reboot
```

## 7. Підготувати місце для Kid Portal

Після reboot:

```bash
sudo mkdir -p /opt/kid-portal /etc/kid-portal /etc/chromium/policies/managed
sudo chown -R pi:pi /opt/kid-portal
```

Далі переходь до основної інструкції:

[Raspberry Pi Setup](./raspberry-pi-setup.md)

## 8. Корисні перевірки

Перевірити модель:

```bash
cat /proc/device-tree/model
```

Перевірити архітектуру:

```bash
uname -m
```

Для 64-bit має бути `aarch64`.

Перевірити Wi-Fi:

```bash
iw dev wlan0 link
```

Перевірити вільне місце:

```bash
df -h
```

## 9. Якщо щось не працює

SSH не підключається:

- перевір, що SSH був увімкнений в Raspberry Pi Imager;
- перевір IP в router panel;
- спробуй підключити HDMI і клавіатуру;
- перевір, чи Pi точно підключилась до Wi-Fi.

Wi-Fi не підключився:

- перевір country code в Imager customization;
- перевір SSID/password;
- для Pi Zero 2 W використовуй 2.4 GHz Wi-Fi, якщо 5 GHz не бачиться.

Нема зображення по HDMI:

- підключи HDMI до Pi перед подачею живлення;
- перевір кабель і monitor input;
- для Pi Zero 2 W переконайся, що використовується правильний mini HDMI adapter.
