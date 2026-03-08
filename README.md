# AirScopeGuardian

AirScopeGuardian is a Django-based WiFi/Kismet tracking and mapping project intended to run on a Raspberry Pi.

## Features
- Kismet log and pcap ingestion
- Map visualization and services dashboard
- Simple admin and charts

## Quick start (local)
1. Create a virtual environment and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run migrations and start the dev server:

```bash
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

3. Open the app in your browser at `http://<pi-ip>:8000`.
