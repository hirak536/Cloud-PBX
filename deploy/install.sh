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
systemctl daemon-reload
systemctl enable ihspbx ihspbx-celery ihspbx-celerybeat
systemctl start ihspbx ihspbx-celery ihspbx-celerybeat

echo "==> Installing FreeSWITCH Lua scripts..."
mkdir -p /usr/share/freeswitch/scripts
cp ${INSTALL_DIR}/backend/freeswitch_scripts/*.lua /usr/share/freeswitch/scripts/
# Substitute DB password placeholder in deployed Lua scripts
PG_PASS=$(grep '^DB_PASSWORD=' ${INSTALL_DIR}/.env | cut -d'=' -f2- | tr -d '"')
sed -i "s/__PG_PASSWORD__/${PG_PASS}/g" /usr/share/freeswitch/scripts/*.lua
chown freeswitch:freeswitch /usr/share/freeswitch/scripts/*.lua
chmod 644 /usr/share/freeswitch/scripts/*.lua

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
echo ""
echo "  Services: systemctl status ihspbx ihspbx-celery ihspbx-celerybeat"
echo "  Logs:     journalctl -u ihspbx -f"
echo "            tail -f /var/log/ihspbx/error.log"
echo ""
echo "  Fail2ban: fail2ban-client status"
echo "            fail2ban-client status freeswitch-udp"
echo "            fail2ban-client status ihspbx"
echo "            fail2ban-client unban <IP>"
