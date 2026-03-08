#!/bin/sh
set -e

if [ ! -f /var/lib/conduit/.initialized ]; then
  echo "Running first-time DB bootstrap (migrations + seed)..."
  alembic upgrade head
  python data/synthetic/generate_all.py
  touch /var/lib/conduit/.initialized
else
  echo "Bootstrap already completed, starting services..."
fi

exec supervisord -c /etc/supervisor/conf.d/conduit.conf
