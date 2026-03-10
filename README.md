# AirScopeGuardian

AirScopeGuardian is a Django-based WiFi/Kismet tracking and mapping project intended to run on a Raspberry Pi.

## Features
- Kismet log and pcap ingestion
- Map visualization and services dashboard
- Simple admin and charts

## Installation (Raspberry Pi)

These steps assume you're running on a Raspberry Pi and have sudo access.

1) Clone and enter the project

```bash
git clone <repo-url> && cd AirscopeGuardian
```

2) Create and activate a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3) Set up the Django database

```bash
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
```

4) Install systemd service files (copy repo `systemd/` files to system)

Copy the service files to the system systemd folder and reload systemd:

```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
```

Then enable/start the services you need, for example:

```bash
sudo systemctl enable --now waveshare.service
sudo systemctl enable --now kismet@wlan0.service
```

5) Run Kismet and imports

- The `kismet/root-shell/run_kismet.sh` and `kismet/root-shell/import_kismet.sh` scripts are used by the `kismet@.service` unit. The unit will call the import script after Kismet stops to import `.kismet` files into the Django DB.
- Ensure the interface name used for `kismet@.service` matches your Wi‑Fi interface (e.g. `wlan0` or `wlan1`).

6) Useful commands

```bash
# Tail the waveshare service logs
sudo journalctl -u waveshare.service -f

# Import a kismet file manually
source venv/bin/activate
python manage.py import_kismet kismet/logs/<file>.kismet
```

Security note: if you need a non-root user to run the repo's helper scripts without a password, restrict sudoers to only the exact scripts (use `sudo visudo` and add a NOPASSWD entry pointing to the absolute script paths). Avoid making scripts world-writable.

Troubleshooting
- If a service fails to start, check `sudo journalctl -u <service> -n 200 --no-pager` for tracebacks.
- For the Waveshare e-ink service, systemd must call the project virtualenv python directly (the repo already includes a fixed `systemd/waveshare.service`).

If you'd like, I can enable and start the services for you and push a commit with this README update.
