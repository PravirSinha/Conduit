FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
	&& apt-get install -y --no-install-recommends curl supervisor \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
	&& pip install -r /app/requirements.txt

COPY . /app

RUN mkdir -p /var/log/supervisor /var/lib/conduit
RUN chmod +x /app/scripts/startup.sh

RUN printf '%s\n' \
	'[supervisord]' \
	'nodaemon=true' \
	'user=root' \
	'logfile=/var/log/supervisor/supervisord.log' \
	'pidfile=/var/run/supervisord.pid' \
	'' \
	'[program:fastapi]' \
	'command=uvicorn api.main:app --host 0.0.0.0 --port 8000' \
	'directory=/app' \
	'autostart=true' \
	'autorestart=true' \
	'startsecs=5' \
	'stdout_logfile=/dev/fd/1' \
	'stdout_logfile_maxbytes=0' \
	'stderr_logfile=/dev/fd/2' \
	'stderr_logfile_maxbytes=0' \
	'' \
	'[program:streamlit]' \
	'command=streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501' \
	'directory=/app' \
	'autostart=true' \
	'autorestart=true' \
	'startsecs=5' \
	'stdout_logfile=/dev/fd/1' \
	'stdout_logfile_maxbytes=0' \
	'stderr_logfile=/dev/fd/2' \
	'stderr_logfile_maxbytes=0' \
	> /etc/supervisor/conf.d/conduit.conf

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["/bin/sh", "-c", "exec supervisord -c /etc/supervisor/conf.d/conduit.conf"]
