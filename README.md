# IHS PBX

A modern, multi-tenant PBX management system built on FreeSWITCH — developed by **Infotech Houston Solutions**.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.13.12 · Django 6.0 + Django REST Framework 3.17 |
| Auth | JWT (simplejwt) · Role-based access (Superuser / Admin / User) |
| Real-time | Django Channels 4 + Redis (WebSocket) |
| Task Queue | Celery 5 + django-celery-beat + Redis |
| FreeSWITCH | greenswitch (ESL) · XML cURL |
| Database | PostgreSQL 15+ |
| Frontend | React 18 + Vite + Tailwind CSS + shadcn/ui |
| Web Server | Gunicorn (ASGI/Uvicorn worker) |
| Email | SMTP — queued delivery via `v_email_queue` |

---

## Features

- **Multi-tenant** — isolated dialplan contexts and resources per tenant/domain
- **XML cURL** — serves dialplan, directory, and configuration XML to FreeSWITCH on demand
- **Extensions** — per-extension bypass/proxy media, codec preferences, voicemail mailboxes
- **Voicemail** — auto-provisioned mailboxes, PostgreSQL storage, email notifications
- **CDR** — call detail records with A/B leg grouping, infinite scroll, call flow timeline
- **Fax** — fax destination routing, quick-send, file management
- **IVR Menus** — multi-level IVR with DTMF routing
- **Ring Groups** — simultaneous/sequential ring with fallback destinations
- **Working Hours** — time-based routing with holiday support
- **Destinations (DIDs)** — inbound DID routing with time conditions
- **Recordings** — media file management + dial-to-record
- **Call Center** — queues, agents, and callback support
- **Operator Panel** — real-time WebSocket operator panel
- **Live Monitoring** — active calls, SIP registrations, conferences via WebSocket
- **Firewall** — fail2ban + iptables management
- **User Management** — full user lifecycle with email invitations, forced password change on first login, self-service forgot password
- **Email Queue** — all outgoing emails queued to DB and delivered via Celery worker
- **REST API** — full DRF API with Swagger/ReDoc documentation

---

## Quick Start (Development)

```bash
# 1. Clone
git clone <repo-url>
cd ihspbx-django

# 2. Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp ../.env.example ../.env
# Edit .env — set DB, Redis, FreeSWITCH, SMTP, and all required vars

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Start backend
python manage.py runserver 0.0.0.0:8000

# 7. Start Celery worker (separate terminal)
celery -A config worker -l info

# 8. Start Celery beat scheduler (separate terminal)
celery -A config beat -l info

# 9. Start frontend (separate terminal)
cd ../frontend
npm install
npm run dev
# Frontend: http://localhost:5173  (proxied to backend at :8000)
```

---

## Production Deploy (Linux)

### Fresh Install

```bash
bash deploy/install.sh
```

### Update Existing Server

```bash
cd /opt/ihspbx-django && git pull
source venv/bin/activate
pip install -r backend/requirements.txt
python backend/manage.py migrate
systemctl restart ihspbx ihspbx-celery ihspbx-celerybeat
```

### Required Directory Permissions

These directories must exist and be owned by the service user (`ihspbx` or `ihspbx`):

```bash
mkdir -p /var/log/ihspbx /var/run/ihspbx /var/run/ihspbx
chown -R ihspbx:ihspbx /var/log/ihspbx /var/run/ihspbx /var/run/ihspbx
```

> **Note:** `ALLOWED_HOSTS` must contain plain hostnames/IPs only — no `http://` prefix or port numbers.
> Example: `ALLOWED_HOSTS=localhost,127.0.0.1,10.0.0.1,myserver.com`

### Services

```bash
systemctl status ihspbx ihspbx-celery ihspbx-celerybeat
journalctl -u ihspbx -f
tail -f /var/log/ihspbx/error.log
```

---

## Project Structure

```
ihspbx-django/
├── backend/
│   ├── config/               # Django settings, URLs, Celery, ASGI
│   ├── core/                 # Auth, Users, Tenants, Domains, Groups
│   ├── esl/                  # FreeSWITCH ESL + WebSocket consumers
│   ├── freeswitch_config/    # XML cURL handler (directory, dialplan, config)
│   └── apps/
│       ├── common/           # Shared utilities (email backend, HTML templates)
│       ├── email_queue/      # Outbound email queue + Celery delivery task
│       ├── xml_cdr/          # Call detail records
│       ├── extensions/       # SIP extensions
│       ├── voicemails/       # Voicemail boxes + messages
│       ├── destinations/     # Inbound DID routing
│       ├── ivr_menus/        # IVR menus
│       ├── ring_groups/      # Ring groups
│       ├── working_hours/    # Time conditions + holidays
│       ├── recordings/       # Media files + call recordings
│       ├── fax/              # Fax management
│       ├── gateways/         # SIP gateways
│       ├── dialplans/        # Manual dialplan records
│       └── ...               # 25+ additional feature apps
├── frontend/
│   └── src/
│       ├── api/              # Axios client + resource helpers
│       ├── components/       # Sidebar, TopBar, UI primitives (shadcn)
│       ├── pages/            # One page per module
│       ├── store/            # Redux (auth, tenant)
│       └── lib/              # Utilities (formatDate, formatDuration, cn)
└── deploy/
    ├── install.sh
    ├── ihspbx-django.service   # ihspbx systemd service
    ├── ihspbx-celery.service   # ihspbx-celery systemd service
    ├── ihspbx-celerybeat.service
    ├── nginx.conf                 # HTTPS (with domain)
    ├── nginx-ip.conf              # HTTP (IP only, no domain)
    └── freeswitch/                # xml_curl.conf.xml, event_socket.conf.xml
```

---

## Environment Variables

All variables are required — no defaults. Copy `.env.example` to `.env` and fill in all values.

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` / `False` |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins |
| `CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | PostgreSQL host |
| `DB_PORT` | PostgreSQL port |
| `VOICEMAIL_SQLITE_PATH` | Path to FreeSWITCH voicemail SQLite DB |
| `REDIS_URL` | Redis URL for channels (e.g. `redis://localhost:6379/0`) |
| `REDIS_CACHE_URL` | Redis URL for cache (e.g. `redis://localhost:6379/1`) |
| `CELERY_BROKER_URL` | Redis URL for Celery broker (e.g. `redis://localhost:6379/2`) |
| `JWT_ACCESS_MINUTES` | JWT access token lifetime in minutes |
| `JWT_REFRESH_DAYS` | JWT refresh token lifetime in days |
| `SESSION_COOKIE_SECURE` | `True` for HTTPS, `False` for HTTP |
| `CSRF_COOKIE_SECURE` | `True` for HTTPS, `False` for HTTP |
| `FREESWITCH_HOST` | FreeSWITCH ESL host |
| `FREESWITCH_PORT` | FreeSWITCH ESL port |
| `FREESWITCH_PASSWORD` | FreeSWITCH ESL password |
| `FREESWITCH_TIMEOUT` | ESL connection timeout (seconds) |
| `FREESWITCH_CONF_DIR` | FreeSWITCH config directory |
| `FREESWITCH_SOUNDS_DIR` | FreeSWITCH sounds directory |
| `FREESWITCH_GATEWAY_DIR` | FreeSWITCH gateway directory |
| `FREESWITCH_RECORDINGS_DIR` | FreeSWITCH recordings directory |
| `FREESWITCH_VOICEMAIL_DIR` | FreeSWITCH voicemail storage directory |
| `EMAIL_BACKEND` | Django email backend class |
| `EMAIL_HOST` | SMTP server hostname |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_USE_TLS` | `True` for STARTTLS |
| `EMAIL_USE_SSL` | `True` for SSL |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password |
| `DEFAULT_FROM_EMAIL` | Default from address |
| `FRONTEND_URL` | Public URL of the app |
| `PBX_DEFAULT_DOMAIN` | Default SIP domain |
| `TIME_ZONE` | Django timezone (e.g. `UTC`) |
| `LOG_FILE` | Application log file path |
| `MEDIA_ROOT` | Path for uploaded/recorded media files |
| `STATIC_ROOT` | Path for collected static files |

---

## API Documentation

| URL | Description |
|-----|-------------|
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/admin/` | Django Admin |

---

## FreeSWITCH Integration

1. Copy `deploy/freeswitch/xml_curl.conf.xml` → FreeSWITCH `autoload_configs/`
2. Copy `deploy/freeswitch/event_socket.conf.xml` → FreeSWITCH `autoload_configs/`
3. Set `PBX_DEFAULT_DOMAIN` and `FREESWITCH_*` vars in `.env`
4. Reload FreeSWITCH: `fs_cli -x 'reload mod_xml_curl'`

---

## WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `/ws/active-calls/` | Live call state updates |
| `/ws/active-conferences/` | Live conference updates |
| `/ws/registrations/` | SIP registration events |
| `/ws/operator-panel/` | Full operator panel feed |

---

## User Authentication Flow

1. **Create user** → temp password auto-generated → welcome email sent via queue
2. **First login** → user forced to change password before accessing the system
3. **Forgot password** → self-service email reset via `/auth/forgot-password/`
4. **Admin reset** → admin can reset any user's password from the Users page

---

© 2026 Infotech Houston Solutions. All rights reserved.
