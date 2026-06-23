#!/usr/bin/env bash
##############################################################################
# IHS PBX - Ubuntu/Debian Install Script
# Run as root: bash install.sh
##############################################################################
set -euo pipefail

INSTALL_DIR=/opt/ihspbx-django
APP_USER=ihspbx
DB_NAME=ihspbx
DB_USER=ihspbx
DB_PASS=$(openssl rand -hex 16)
PYTHON_VERSION=3.13   # tested with 3.13.12

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
    supervisor \
    fail2ban

echo "==> Creating system user..."
id -u ${APP_USER} &>/dev/null || useradd -r -s /bin/bash -m -d /home/${APP_USER} ${APP_USER}

echo "==> Setting up PostgreSQL..."
systemctl start postgresql
systemctl enable postgresql
sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
# Separate database for call detail records (CDRs). Routed via CdrRouter; the
# xml_cdr app's tables live here. Override the name with CDR_DB_NAME in .env.
CDR_DB_NAME=${CDR_DB_NAME:-ihspbx_cdr}
sudo -u postgres psql -c "CREATE DATABASE ${CDR_DB_NAME} OWNER ${DB_USER};" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${CDR_DB_NAME} TO ${DB_USER};"

# HOMER (SIP capture) databases — homer_config (settings) + homer_data (capture).
# Owned by a dedicated 'homer' role. heplify-server writes capture; homer-app
# owns the schema/seed. The IHS-PBX CDR viewer + /sip/search API read homer_data.
HOMER_DB_PASS=${HOMER_DB_PASS:-$(openssl rand -hex 12)}
sudo -u postgres psql -c "CREATE ROLE homer WITH LOGIN PASSWORD '${HOMER_DB_PASS}';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE homer_config OWNER homer;" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE homer_data OWNER homer;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE homer_config TO homer;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE homer_data TO homer;"

echo "==> Cloning/copying application..."
mkdir -p ${INSTALL_DIR}
if [ "$(realpath .)" != "$(realpath ${INSTALL_DIR})" ]; then
    cp -r . ${INSTALL_DIR}/
fi
chown -R ${APP_USER}:${APP_USER} ${INSTALL_DIR}

echo "==> Creating Python virtual environment..."
sudo -u ${APP_USER} python${PYTHON_VERSION} -m venv ${INSTALL_DIR}/venv
sudo -u ${APP_USER} ${INSTALL_DIR}/venv/bin/pip install --upgrade pip wheel
sudo -u ${APP_USER} ${INSTALL_DIR}/venv/bin/pip install -r ${INSTALL_DIR}/backend/requirements.txt

echo "==> Creating log/run directories..."
mkdir -p /var/log/ihspbx /var/run/ihspbx /var/run/ihspbx
chown -R ${APP_USER}:${APP_USER} /var/log/ihspbx /var/run/ihspbx /var/run/ihspbx

echo "==> Setting up environment file..."
if [ ! -f ${INSTALL_DIR}/.env ]; then
    cp ${INSTALL_DIR}/.env.example ${INSTALL_DIR}/.env
    SECRET_KEY=$(${INSTALL_DIR}/venv/bin/python -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change-me-generate-with-python-secrets-token-hex-32/${SECRET_KEY}/" ${INSTALL_DIR}/.env
    sed -i "s/DB_NAME=ihspbx/DB_NAME=${DB_NAME}/" ${INSTALL_DIR}/.env
    sed -i "s/DB_USER=ihspbx/DB_USER=${DB_USER}/" ${INSTALL_DIR}/.env
    sed -i "s/DB_PASSWORD=password/DB_PASSWORD=${DB_PASS}/" ${INSTALL_DIR}/.env
    echo ""
    echo ">>> .env created. Edit ${INSTALL_DIR}/.env to set ALLOWED_HOSTS, EMAIL, FreeSWITCH settings."
    echo ">>> DB Password: ${DB_PASS}"
fi

echo "==> Running Django migrations..."
cd ${INSTALL_DIR}/backend
sudo -u ${APP_USER} DJANGO_SETTINGS_MODULE=config.settings.prod \
    ${INSTALL_DIR}/venv/bin/python manage.py migrate --noinput
# The xml_cdr app is routed to the separate 'cdr' database (CdrRouter), so its
# tables must be migrated there explicitly.
sudo -u ${APP_USER} DJANGO_SETTINGS_MODULE=config.settings.prod \
    ${INSTALL_DIR}/venv/bin/python manage.py migrate xml_cdr --database=cdr --noinput

echo "==> Collecting static files..."
sudo -u ${APP_USER} DJANGO_SETTINGS_MODULE=config.settings.prod \
    ${INSTALL_DIR}/venv/bin/python manage.py collectstatic --noinput

echo "==> Building frontend..."
cd ${INSTALL_DIR}/frontend
sudo -u ${APP_USER} npm install
sudo -u ${APP_USER} npm run build

echo "==> Installing systemd services..."
cp ${INSTALL_DIR}/deploy/ihspbx-django.service /etc/systemd/system/ihspbx.service
cp ${INSTALL_DIR}/deploy/ihspbx-celery.service /etc/systemd/system/ihspbx-celery.service
cp ${INSTALL_DIR}/deploy/ihspbx-celerybeat.service /etc/systemd/system/ihspbx-celerybeat.service
# Rolling SIP capture feeding the per-leg CDR SIP/PCAP viewer (tenant-only,
# 5-min files). Slicing runs via the celerybeat sweep, not here.
cp ${INSTALL_DIR}/deploy/sip-capture.service /etc/systemd/system/sip-capture.service
chmod +x ${INSTALL_DIR}/deploy/gen-sip-capture-filter.sh
systemctl daemon-reload
systemctl enable ihspbx ihspbx-celery ihspbx-celerybeat sip-capture
systemctl start ihspbx ihspbx-celery ihspbx-celerybeat sip-capture

echo "==> Installing HOMER (SIP capture: heplify-server + homer-app)..."
# heplify-server receives HEP from FreeSWITCH (capture-server in sofia.conf) and
# writes to homer_data; homer-app serves the admin UI + REST API on 127.0.0.1:9080.
# The IHS-PBX CDR viewer and /sip/search API read homer_data (see apps/xml_cdr).
HEPLIFY_VER=${HEPLIFY_VER:-1.60.3}
HOMERAPP_VER=${HOMERAPP_VER:-1.5.14}
if ! command -v heplify-server >/dev/null 2>&1; then
    apt-get install -y luajit libluajit-5.1-2 libluajit-5.1-common
    curl -fsSL -o /tmp/heplify-server.deb \
        "https://github.com/sipcapture/heplify-server/releases/download/${HEPLIFY_VER}/heplify-server-${HEPLIFY_VER}-amd64.deb"
    dpkg -i /tmp/heplify-server.deb || apt-get -f install -y
fi
if ! command -v homer-app >/dev/null 2>&1; then
    curl -fsSL -o /tmp/homer-app.deb \
        "https://github.com/sipcapture/homer-app/releases/download/${HOMERAPP_VER}/homer-app-${HOMERAPP_VER}-amd64.deb"
    dpkg -i /tmp/homer-app.deb || apt-get -f install -y
fi

# heplify-server config: loopback HEP only, write to homer_data as role 'homer'.
sed -i "s#^HEPAddr .*#HEPAddr               = \"127.0.0.1:9060\"#"   /etc/heplify-server.toml
sed -i "s#^HEPTLSAddr .*#HEPTLSAddr            = \"\"#"              /etc/heplify-server.toml
sed -i "s#^HEPWSAddr .*#HEPWSAddr             = \"\"#"               /etc/heplify-server.toml
sed -i "s#^DBAddr .*#DBAddr                = \"127.0.0.1:5432\"#"    /etc/heplify-server.toml
sed -i "s#^DBUser .*#DBUser                = \"homer\"#"             /etc/heplify-server.toml
sed -i "s#^DBPass .*#DBPass                = \"${HOMER_DB_PASS}\"#"  /etc/heplify-server.toml

# homer-app config: point DB creds at the homer role, bind UI to loopback,
# disable unused integrations (influx/prometheus/loki/grafana), set a JWT secret.
python3 - "$HOMER_DB_PASS" <<'PYHOMER'
import json, sys, uuid
pw = sys.argv[1]
p = '/usr/local/homer/etc/webapp_config.json'
c = json.load(open(p))
c['database_data']['LocalNode'].update(user='homer', host='127.0.0.1'); c['database_data']['LocalNode']['pass'] = pw
c['database_config'].update(user='homer', host='127.0.0.1'); c['database_config']['pass'] = pw
c['http_settings']['host'] = '127.0.0.1'
for k in ('influxdb_config','prometheus_config','loki_config','grafana_config'):
    if isinstance(c.get(k), dict): c[k]['enable'] = False
c['auth_settings']['jwt_secret'] = uuid.uuid4().hex + uuid.uuid4().hex
json.dump(c, open(p, 'w'), indent=4)
PYHOMER

# Create + seed the homer schema (config tables, mapping_schema, global_settings).
# Stop the service first so the one-shot populate doesn't fight the HTTP listener.
systemctl stop homer-app 2>/dev/null || true
/usr/local/bin/homer-app -webapp-config-path /usr/local/homer/etc \
    -database-host 127.0.0.1 -database-root-user postgres \
    -create-table-db-config -populate-table-db-config || true
# Seed the default admin login (admin/sipcapture) if the users table is empty.
sudo -u postgres psql -d homer_config -tAc "select count(*) from public.users" 2>/dev/null | grep -q '^0$' && \
  HOMER_ADMIN_HASH=$(${INSTALL_DIR}/venv/bin/python -c "import bcrypt;print(bcrypt.hashpw(b'sipcapture',bcrypt.gensalt()).decode())") && \
  sudo -u postgres psql -d homer_config -c \
    "insert into public.users (username,partid,email,enabled,firstname,lastname,department,usergroup,hash,guid,created_at) \
     values ('admin',10,'admin@localhost',true,'Admin','User','Administrator','admin','${HOMER_ADMIN_HASH}','$(cat /proc/sys/kernel/random/uuid)',now());" || true

systemctl enable heplify-server homer-app
systemctl restart heplify-server homer-app
echo ">>> HOMER DB password: ${HOMER_DB_PASS}  (also set HOMER_DB_PASSWORD in .env for the CDR viewer)"

echo "==> Configuring Nginx..."
cp ${INSTALL_DIR}/deploy/nginx.conf /etc/nginx/sites-available/ihspbx
ln -sf /etc/nginx/sites-available/ihspbx /etc/nginx/sites-enabled/ihspbx
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "==> Configuring fail2ban..."
cp ${INSTALL_DIR}/deploy/fail2ban/jail.local /etc/fail2ban/jail.local
cp ${INSTALL_DIR}/deploy/fail2ban/filter.d/freeswitch.conf /etc/fail2ban/filter.d/freeswitch.conf
cp ${INSTALL_DIR}/deploy/fail2ban/filter.d/ihspbx-django.conf /etc/fail2ban/filter.d/ihspbx-django.conf
cp ${INSTALL_DIR}/deploy/fail2ban/jail.d/ihspbx.conf /etc/fail2ban/jail.d/ihspbx.conf
systemctl enable fail2ban
systemctl restart fail2ban

echo "==> Starting Redis..."
systemctl start redis-server
systemctl enable redis-server

echo ""
echo "=========================================="
echo "IHS PBX installed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit /opt/ihspbx-django/.env (set ALLOWED_HOSTS, PBX_DEFAULT_DOMAIN, EMAIL, FreeSWITCH)"
echo "  2. Update /etc/nginx/sites-available/ihspbx with your domain"
echo "  3. Get SSL cert: certbot --nginx -d your-domain.com"
echo "  4. Create admin user:"
echo "       cd /opt/ihspbx-django/backend"
echo "       sudo -u ${APP_USER} DJANGO_SETTINGS_MODULE=config.settings.prod \\"
echo "         /opt/ihspbx-django/venv/bin/python manage.py createsuperuser"
echo "  5. Configure FreeSWITCH:"
echo "       Copy deploy/freeswitch/xml_curl.conf.xml to FreeSWITCH conf/autoload_configs/"
echo "       Copy deploy/freeswitch/event_socket.conf.xml to FreeSWITCH conf/autoload_configs/"
echo "       fs_cli -x 'reload mod_xml_curl'"
echo "  6. Enable toggle/Call-Flow BLF lamps (FusionPBX 'flow+' proto):"
echo "       Copy deploy/freeswitch/scripts/blf_subscribe.lua to \\"
echo "         \$\${script_dir} (e.g. /usr/share/freeswitch/scripts/)"
echo "       In conf/autoload_configs/lua.conf.xml add under <settings>:"
echo "         <param name=\"startup-script\" value=\"blf_subscribe.lua flow\"/>"
echo "       fs_cli -x 'reloadxml'   (script auto-starts on next FreeSWITCH restart;"
echo "         or start now without a restart: fs_cli -x 'luarun blf_subscribe.lua flow')"
echo "       Then program the phone BLF key Value as:  flow+*<ext>-<TENANT>  (e.g. flow+*800-IHDT)"
echo ""
echo "  Services: systemctl status ihspbx ihspbx-celery ihspbx-celerybeat"
echo "  Logs:     journalctl -u ihspbx -f"
echo "            tail -f /var/log/ihspbx/error.log"
echo ""
echo "  Fail2ban: fail2ban-client status"
echo "            fail2ban-client status freeswitch-udp"
echo "            fail2ban-client status ihspbx"
echo "            fail2ban-client unban <IP>"
