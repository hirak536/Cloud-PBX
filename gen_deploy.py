#!/usr/bin/env python3
"""
gen_deploy.py - Write Linux deployment files
"""
import os, textwrap

ROOT = os.path.dirname(__file__)
DEPLOY = os.path.join(ROOT, 'deploy')
os.makedirs(DEPLOY, exist_ok=True)

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(textwrap.dedent(content).lstrip('\n'))
    print(f'  WROTE {os.path.relpath(path, ROOT)}')

# ── nginx.conf ───────────────────────────────────────────────────────────────
write(os.path.join(DEPLOY, 'nginx.conf'), r"""
    ##############################################################################
    # Nginx configuration for ihspbx Django
    # Place at: /etc/nginx/sites-available/ihspbx
    # Enable:   ln -s /etc/nginx/sites-available/ihspbx /etc/nginx/sites-enabled/
    ##############################################################################

    upstream django_backend {
        server 127.0.0.1:8000 fail_timeout=0;
    }

    # Redirect HTTP -> HTTPS
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;   # <- change this

        # SSL - obtain via: certbot --nginx -d your-domain.com
        ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
        ssl_session_cache   shared:SSL:10m;
        ssl_session_timeout 10m;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        client_max_body_size 50M;

        # Static / Media
        location /static/ {
            alias /opt/ihspbx-django/backend/staticfiles/;
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
        location /media/ {
            alias /opt/ihspbx-django/backend/media/;
            expires 7d;
        }

        # Frontend SPA (built)
        location / {
            root /opt/ihspbx-django/frontend/dist;
            try_files $uri $uri/ /index.html;
            expires 1h;
        }

        # API, admin, XML-cURL, provision
        location ~ ^/(api|admin|xml-curl|provision)/ {
            proxy_pass         http://django_backend;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header   X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
        }

        # WebSocket (Django Channels)
        location /ws/ {
            proxy_pass         http://django_backend;
            proxy_http_version 1.1;
            proxy_set_header   Upgrade $http_upgrade;
            proxy_set_header   Connection "upgrade";
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_read_timeout 86400s;
        }

        location /health/ {
            access_log off;
            return 200 'OK';
            add_header Content-Type text/plain;
        }
    }
""")

# ── systemd: gunicorn / uvicorn ──────────────────────────────────────────────
write(os.path.join(DEPLOY, 'ihspbx-django.service'), """
    [Unit]
    Description=ihspbx Django (Gunicorn/Uvicorn ASGI)
    After=network.target postgresql.service redis.service
    Requires=postgresql.service redis.service

    [Service]
    Type=notify
    User=ihspbx
    Group=ihspbx
    WorkingDirectory=/opt/ihspbx-django/backend
    EnvironmentFile=/opt/ihspbx-django/.env
    Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
    ExecStart=/opt/ihspbx-django/venv/bin/gunicorn config.asgi:application \\
        --bind 127.0.0.1:8000 \\
        --workers 4 \\
        --worker-class uvicorn.workers.UvicornWorker \\
        --timeout 300 \\
        --keep-alive 5 \\
        --max-requests 1000 \\
        --max-requests-jitter 100 \\
        --log-level info \\
        --access-logfile /var/log/ihspbx/access.log \\
        --error-logfile /var/log/ihspbx/error.log
    ExecReload=/bin/kill -s HUP $MAINPID
    KillMode=mixed
    TimeoutStopSec=5
    PrivateTmp=true
    Restart=on-failure
    RestartSec=5

    [Install]
    WantedBy=multi-user.target
""")

write(os.path.join(DEPLOY, 'ihspbx-celery.service'), """
    [Unit]
    Description=ihspbx Django Celery Worker
    After=network.target redis.service postgresql.service
    Requires=redis.service

    [Service]
    Type=forking
    User=ihspbx
    Group=ihspbx
    WorkingDirectory=/opt/ihspbx-django/backend
    EnvironmentFile=/opt/ihspbx-django/.env
    Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
    PIDFile=/var/run/ihspbx/celery.pid
    ExecStart=/opt/ihspbx-django/venv/bin/celery \\
        -A config \\
        multi start worker \\
        --pidfile=/var/run/ihspbx/celery.pid \\
        --logfile=/var/log/ihspbx/celery.log \\
        --loglevel=INFO \\
        --concurrency=4 \\
        --queues=default,esl,email
    ExecStop=/opt/ihspbx-django/venv/bin/celery \\
        -A config multi stopwait worker \\
        --pidfile=/var/run/ihspbx/celery.pid
    ExecReload=/opt/ihspbx-django/venv/bin/celery \\
        -A config multi restart worker \\
        --pidfile=/var/run/ihspbx/celery.pid \\
        --logfile=/var/log/ihspbx/celery.log \\
        --loglevel=INFO
    Restart=on-failure
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
""")

write(os.path.join(DEPLOY, 'ihspbx-celerybeat.service'), """
    [Unit]
    Description=ihspbx Django Celery Beat Scheduler
    After=network.target redis.service
    Requires=redis.service

    [Service]
    Type=simple
    User=ihspbx
    Group=ihspbx
    WorkingDirectory=/opt/ihspbx-django/backend
    EnvironmentFile=/opt/ihspbx-django/.env
    Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
    ExecStart=/opt/ihspbx-django/venv/bin/celery \\
        -A config beat \\
        --loglevel=INFO \\
        --scheduler django_celery_beat.schedulers:DatabaseScheduler \\
        --logfile=/var/log/ihspbx/celerybeat.log \\
        --pidfile=/var/run/ihspbx/celerybeat.pid
    Restart=on-failure
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
""")

# ── FreeSWITCH XML cURL config ───────────────────────────────────────────────
write(os.path.join(DEPLOY, 'freeswitch', 'xml_curl.conf.xml'), """
    <configuration name="xml_curl.conf" description="XML cURL">
      <bindings>
        <binding name="ihspbx_directory">
          <param name="gateway-url" value="http://127.0.0.1:8000/xml-curl/" bindings="directory"/>
        </binding>
        <binding name="ihspbx_dialplan">
          <param name="gateway-url" value="http://127.0.0.1:8000/xml-curl/" bindings="dialplan"/>
        </binding>
        <binding name="ihspbx_configuration">
          <param name="gateway-url" value="http://127.0.0.1:8000/xml-curl/" bindings="configuration"/>
        </binding>
      </bindings>
    </configuration>
""")

write(os.path.join(DEPLOY, 'freeswitch', 'event_socket.conf.xml'), """
    <configuration name="event_socket.conf" description="Event Socket">
      <settings>
        <param name="nat-map" value="false"/>
        <param name="listen-ip" value="127.0.0.1"/>
        <param name="listen-port" value="8021"/>
        <!-- Change this password and set in .env as FREESWITCH_PASSWORD -->
        <param name="password" value="ClueCon"/>
        <param name="apply-inbound-acl" value="loopback.auto"/>
      </settings>
    </configuration>
""")

# ── .env template ────────────────────────────────────────────────────────────
write(os.path.join(ROOT, '.env.example'), """
    # Django
    SECRET_KEY=change-me-generate-with-python-secrets-token-hex-32
    DEBUG=False
    ALLOWED_HOSTS=your-domain.com,localhost

    # Database
    DATABASE_URL=postgresql://ihspbx:password@localhost:5432/ihspbx

    # Redis
    REDIS_URL=redis://localhost:6379/0

    # Celery
    CELERY_BROKER_URL=redis://localhost:6379/1
    CELERY_RESULT_BACKEND=redis://localhost:6379/2

    # FreeSWITCH ESL
    FREESWITCH_HOST=127.0.0.1
    FREESWITCH_PORT=8021
    FREESWITCH_PASSWORD=ClueCon

    # Email (for voicemail notifications)
    EMAIL_HOST=smtp.example.com
    EMAIL_PORT=587
    EMAIL_HOST_USER=noreply@example.com
    EMAIL_HOST_PASSWORD=your-smtp-password
    EMAIL_USE_TLS=True
    DEFAULT_FROM_EMAIL=ihspbx <noreply@example.com>

    # Media / Static
    MEDIA_ROOT=/opt/ihspbx-django/backend/media
    STATIC_ROOT=/opt/ihspbx-django/backend/staticfiles
""")

# ── install.sh ───────────────────────────────────────────────────────────────
write(os.path.join(DEPLOY, 'install.sh'), r"""
    #!/usr/bin/env bash
    ##############################################################################
    # ihspbx Django - Ubuntu/Debian Install Script
    # Run as root: bash install.sh
    ##############################################################################
    set -euo pipefail

    INSTALL_DIR=/opt/ihspbx-django
    APP_USER=ihspbx
    DB_NAME=ihspbx
    DB_USER=ihspbx
    DB_PASS=$(openssl rand -hex 16)
    PYTHON_VERSION=3.11

    echo "==> Installing system packages..."
    apt-get update -qq
    apt-get install -y --no-install-recommends \
        python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev \
        postgresql postgresql-contrib \
        redis-server \
        nginx \
        certbot python3-certbot-nginx \
        nodejs npm \
        git curl wget build-essential libpq-dev \
        supervisor

    echo "==> Creating system user..."
    id -u ${APP_USER} &>/dev/null || useradd -r -s /bin/bash -m -d /home/${APP_USER} ${APP_USER}

    echo "==> Setting up PostgreSQL..."
    systemctl start postgresql
    systemctl enable postgresql
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"

    echo "==> Cloning/copying application..."
    mkdir -p ${INSTALL_DIR}
    cp -r . ${INSTALL_DIR}/
    chown -R ${APP_USER}:${APP_USER} ${INSTALL_DIR}

    echo "==> Creating Python virtual environment..."
    sudo -u ${APP_USER} python${PYTHON_VERSION} -m venv ${INSTALL_DIR}/venv
    sudo -u ${APP_USER} ${INSTALL_DIR}/venv/bin/pip install --upgrade pip wheel
    sudo -u ${APP_USER} ${INSTALL_DIR}/venv/bin/pip install -r ${INSTALL_DIR}/backend/requirements.txt

    echo "==> Setting up environment file..."
    if [ ! -f ${INSTALL_DIR}/.env ]; then
        cp ${INSTALL_DIR}/.env.example ${INSTALL_DIR}/.env
        SECRET_KEY=$(${INSTALL_DIR}/venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
        sed -i "s/change-me-generate-with-python-secrets-token-hex-32/${SECRET_KEY}/" ${INSTALL_DIR}/.env
        sed -i "s/postgresql:\/\/ihspbx:password/postgresql:\/\/${DB_USER}:${DB_PASS}/" ${INSTALL_DIR}/.env
        echo ""
        echo ">>> .env created. Edit ${INSTALL_DIR}/.env to set ALLOWED_HOSTS, EMAIL, FreeSWITCH settings."
        echo ">>> DB Password: ${DB_PASS}"
    fi

    echo "==> Running Django migrations..."
    cd ${INSTALL_DIR}/backend
    sudo -u ${APP_USER} DJANGO_SETTINGS_MODULE=config.settings.prod \
        ${INSTALL_DIR}/venv/bin/python manage.py migrate --noinput

    echo "==> Collecting static files..."
    sudo -u ${APP_USER} DJANGO_SETTINGS_MODULE=config.settings.prod \
        ${INSTALL_DIR}/venv/bin/python manage.py collectstatic --noinput

    echo "==> Building frontend..."
    cd ${INSTALL_DIR}/frontend
    sudo -u ${APP_USER} npm install
    sudo -u ${APP_USER} npm run build

    echo "==> Creating log/run directories..."
    mkdir -p /var/log/ihspbx /var/run/ihspbx
    chown -R ${APP_USER}:${APP_USER} /var/log/ihspbx /var/run/ihspbx

    echo "==> Installing systemd services..."
    cp ${INSTALL_DIR}/deploy/ihspbx-django.service /etc/systemd/system/
    cp ${INSTALL_DIR}/deploy/ihspbx-celery.service /etc/systemd/system/
    cp ${INSTALL_DIR}/deploy/ihspbx-celerybeat.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable ihspbx-django ihspbx-celery ihspbx-celerybeat
    systemctl start ihspbx-django ihspbx-celery ihspbx-celerybeat

    echo "==> Configuring Nginx..."
    cp ${INSTALL_DIR}/deploy/nginx.conf /etc/nginx/sites-available/ihspbx
    ln -sf /etc/nginx/sites-available/ihspbx /etc/nginx/sites-enabled/ihspbx
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl reload nginx

    echo "==> Installing Redis..."
    systemctl start redis-server
    systemctl enable redis-server

    echo ""
    echo "=========================================="
    echo "ihspbx Django installed successfully!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Edit /opt/ihspbx-django/.env (set domain, email, FreeSWITCH)"
    echo "  2. Update /etc/nginx/sites-available/ihspbx with your domain"
    echo "  3. Get SSL cert: certbot --nginx -d your-domain.com"
    echo "  4. Create admin user:"
    echo "       cd /opt/ihspbx-django/backend"
    echo "       sudo -u ihspbx DJANGO_SETTINGS_MODULE=config.settings.prod \\"
    echo "         /opt/ihspbx-django/venv/bin/python manage.py createsuperuser"
    echo "  5. Configure FreeSWITCH:"
    echo "       Copy deploy/freeswitch/xml_curl.conf.xml to FreeSWITCH conf/autoload_configs/"
    echo "       Copy deploy/freeswitch/event_socket.conf.xml to FreeSWITCH conf/autoload_configs/"
    echo "       fs_cli -x 'reload mod_xml_curl'"
    echo ""
    echo "  Services: systemctl status ihspbx-django ihspbx-celery ihspbx-celerybeat"
    echo "  Logs:     journalctl -u ihspbx-django -f"
    echo "            tail -f /var/log/ihspbx/error.log"
""")

# ── management command: create_default_domain ────────────────────────────────
mgmt_dir = os.path.join(ROOT, 'backend', 'core', 'management', 'commands')
os.makedirs(mgmt_dir, exist_ok=True)
open(os.path.join(os.path.dirname(mgmt_dir), '__init__.py'), 'a').close()
open(os.path.join(mgmt_dir, '__init__.py'), 'a').close()
write(os.path.join(mgmt_dir, 'create_default_domain.py'), """
    from django.core.management.base import BaseCommand
    from core.models import Domain

    class Command(BaseCommand):
        help = 'Create the default domain if it does not exist'

        def add_arguments(self, parser):
            parser.add_argument('domain_name', nargs='?', default='localhost',
                                help='Domain name (default: localhost)')

        def handle(self, *args, **options):
            name = options['domain_name']
            domain, created = Domain.objects.get_or_create(
                domain_name=name,
                defaults={'domain_enabled': True, 'domain_description': 'Default domain'}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created domain: {name} ({domain.domain_uuid})'))
            else:
                self.stdout.write(f'Domain already exists: {name} ({domain.domain_uuid})')
""")

# ── README.md ─────────────────────────────────────────────────────────────────
write(os.path.join(ROOT, 'README.md'), """
    # ihspbx Django

    Full Django rewrite of ihspbx 5.5.7 — a multi-tenant PBX management system.

    ## Tech Stack

    | Layer | Tech |
    |-------|------|
    | Backend | Django 5.x + DRF |
    | Auth | JWT (simplejwt) + TOTP (django-otp) |
    | Real-time | Django Channels + Redis |
    | Tasks | Celery + Redis |
    | FreeSWITCH | greenswitch (ESL) |
    | Database | PostgreSQL 15+ |
    | Frontend | Vue 3 + Vite + PrimeVue |
    | Web server | Nginx + Gunicorn/Uvicorn |

    ## Quick Start (Development)

    ```bash
    # 1. Clone and enter project
    cd /opt/ihspbx-django

    # 2. Create and activate virtual environment
    python3 -m venv venv
    source venv/bin/activate

    # 3. Install Python dependencies
    cd backend
    pip install -r requirements.txt

    # 4. Configure environment
    cp .env.example .env
    # Edit .env with your database credentials and FreeSWITCH settings

    # 5. Run migrations
    python manage.py migrate

    # 6. Create default domain
    python manage.py create_default_domain localhost

    # 7. Create superuser
    python manage.py createsuperuser

    # 8. Collect static files
    python manage.py collectstatic

    # 9. Run backend
    python manage.py runserver 0.0.0.0:8000

    # 10. In a separate terminal, run Celery worker
    celery -A config worker -l info --concurrency=4

    # 11. In another terminal, run frontend dev server
    cd ../frontend
    npm install
    npm run dev
    # Frontend available at: http://localhost:5173
    # (proxied to backend at :8000)
    ```

    ## Production Install (Ubuntu/Debian)

    ```bash
    sudo bash deploy/install.sh
    ```

    See `deploy/install.sh` for full instructions.

    ## Project Structure

    ```
    ihspbx-django/
    ├── backend/
    │   ├── config/          # Django settings, URLs, Celery, ASGI
    │   ├── core/            # Auth, Domains, Users, Groups, Permissions
    │   ├── esl/             # FreeSWITCH ESL integration + WebSocket consumers
    │   ├── freeswitch_config/  # XML cURL handler (serves config to FreeSWITCH)
    │   └── apps/            # 30+ PBX feature apps (extensions, dialplans, etc.)
    ├── frontend/            # Vue 3 SPA
    │   └── src/
    │       ├── api/         # Axios API client + resource helpers
    │       ├── components/  # AppLayout, DomainSelector
    │       ├── stores/      # Pinia (auth, domain)
    │       ├── router/      # Vue Router
    │       └── views/       # One view per module
    └── deploy/              # Nginx, systemd, FreeSWITCH config, install.sh
    ```

    ## API Documentation

    Once running, visit:
    - Swagger UI: http://localhost:8000/api/docs/
    - ReDoc:      http://localhost:8000/api/redoc/
    - Django Admin: http://localhost:8000/admin/

    ## FreeSWITCH Integration

    1. Copy `deploy/freeswitch/xml_curl.conf.xml` to FreeSWITCH `autoload_configs/`
    2. Copy `deploy/freeswitch/event_socket.conf.xml` to FreeSWITCH `autoload_configs/`
    3. Reload FreeSWITCH: `fs_cli -x 'reload mod_xml_curl'`
    4. Set `FREESWITCH_PASSWORD` in `.env` to match `event_socket.conf.xml`

    ## WebSocket Endpoints

    | Endpoint | Description |
    |----------|-------------|
    | `/ws/active-calls/` | Live call state updates |
    | `/ws/active-conferences/` | Live conference updates |
    | `/ws/registrations/` | SIP registration events |
    | `/ws/operator-panel/` | Full operator panel feed |

    ## Apps Included

    extensions, dialplans, voicemails, gateways, sip_profiles, call_centers,
    conferences, devices, provision, xml_cdr, recordings, ring_groups, ivr_menus,
    call_flows, time_conditions, destinations, feature_codes, access_controls,
    music_on_hold, fax, email_queue, number_translations, modules_app, pin_numbers,
    vars, follow_me, call_block, call_broadcast, fifo, emergency, event_guard,
    domain_limits, sofia_global_settings, voicemail_greetings, extension_settings

    ## Environment Variables

    See `.env.example` for all required variables.
""")

print('\nDeploy files done!')
print('  deploy/nginx.conf')
print('  deploy/ihspbx-django.service')
print('  deploy/ihspbx-celery.service')
print('  deploy/ihspbx-celerybeat.service')
print('  deploy/freeswitch/xml_curl.conf.xml')
print('  deploy/freeswitch/event_socket.conf.xml')
print('  deploy/install.sh')
print('  .env.example')
print('  README.md')
print('  backend/core/management/commands/create_default_domain.py')
