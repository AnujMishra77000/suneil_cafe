#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (use sudo)."
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: sudo bash scripts/setup_nginx_gunicorn_ubuntu.sh <domain> [www-domain]"
  echo "Example: sudo bash scripts/setup_nginx_gunicorn_ubuntu.sh example.com www.example.com"
  exit 1
fi

DOMAIN="$1"
WWW_DOMAIN="${2:-www.${DOMAIN}}"

PROJECT_DIR="${PROJECT_DIR:-/srv/thathwamasi/core}"
VENV_DIR="${VENV_DIR:-/srv/thathwamasi/venv}"
SERVICE_NAME="${SERVICE_NAME:-thathwamasi-gunicorn}"
APP_USER="${APP_USER:-www-data}"
APP_GROUP="${APP_GROUP:-www-data}"

SERVICE_TEMPLATE="${PROJECT_DIR}/deploy/systemd/thathwamasi-gunicorn.service"
NGINX_TEMPLATE="${PROJECT_DIR}/deploy/nginx/thathwamasi.conf"

if [[ ! -f "${SERVICE_TEMPLATE}" ]]; then
  echo "Missing service template: ${SERVICE_TEMPLATE}"
  exit 1
fi

if [[ ! -f "${NGINX_TEMPLATE}" ]]; then
  echo "Missing nginx template: ${NGINX_TEMPLATE}"
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Missing venv python: ${VENV_DIR}/bin/python"
  exit 1
fi

echo "Installing systemd service"
cp "${SERVICE_TEMPLATE}" "/etc/systemd/system/${SERVICE_NAME}.service"
sed -i \
  -e "s#^User=.*#User=${APP_USER}#" \
  -e "s#^Group=.*#Group=${APP_GROUP}#" \
  -e "s#^WorkingDirectory=.*#WorkingDirectory=${PROJECT_DIR}#" \
  -e "s#^EnvironmentFile=.*#EnvironmentFile=${PROJECT_DIR}/.env#" \
  -e "s#^ExecStart=.*#ExecStart=${VENV_DIR}/bin/gunicorn core.wsgi:application -c ${PROJECT_DIR}/deploy/gunicorn.conf.py#" \
  "/etc/systemd/system/${SERVICE_NAME}.service"

echo "Installing nginx site"
cp "${NGINX_TEMPLATE}" "/etc/nginx/sites-available/thathwamasi"
sed -i \
  -e "s#server_name .*#server_name ${DOMAIN} ${WWW_DOMAIN};#" \
  -e "s#/srv/thathwamasi/core/staticfiles/#${PROJECT_DIR}/staticfiles/#" \
  -e "s#/srv/thathwamasi/core/media/#${PROJECT_DIR}/media/#" \
  "/etc/nginx/sites-available/thathwamasi"

ln -sfn /etc/nginx/sites-available/thathwamasi /etc/nginx/sites-enabled/thathwamasi
rm -f /etc/nginx/sites-enabled/default

chown -R "${APP_USER}:${APP_GROUP}" "${PROJECT_DIR}"

echo "Running migrations and collectstatic"
runuser -u "${APP_USER}" -- "${VENV_DIR}/bin/python" "${PROJECT_DIR}/manage.py" migrate --noinput
runuser -u "${APP_USER}" -- "${VENV_DIR}/bin/python" "${PROJECT_DIR}/manage.py" collectstatic --noinput

echo "Reloading services"
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}"
nginx -t
systemctl restart nginx

echo
echo "Deployment setup complete"
echo "Service status: systemctl status ${SERVICE_NAME} --no-pager"
echo "Nginx status  : systemctl status nginx --no-pager"
echo "Next (TLS)    : certbot --nginx -d ${DOMAIN} -d ${WWW_DOMAIN}"
