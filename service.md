Service	Purpose
cloudpbx.service	Main Django app (Gunicorn/Uvicorn ASGI on port 8000)
cloudpbx-celery.service	Celery worker — handles async background tasks (emails, processing, etc.)
cloudpbx-celerybeat.service	Celery beat — scheduler, triggers periodic/scheduled tasks
cloudpbx-esl-listener.service	FreeSWITCH ESL listener — listens to FS events (calls, hangups, etc.) and syncs to Django
redis.service	Redis — message broker for Celery, also used for caching/channels
sshd.service	SSH daemon
iptables.service	Firewall rules
ip6tables.service	Firewall rules (IPv6)
connectwisecontrol-*.service	ConnectWise remote access agent
dbus-org.freedesktop.timesync1.service	Time sync (systemd-timesyncd)
