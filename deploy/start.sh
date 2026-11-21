#!/usr/bin/env bash
# Starts the whole system inside the container (see deploy/Dockerfile):
# PostgreSQL, the action server, the Rasa server and the FastAPI gateway.
#
# The demo data is loaded when the database is first created. Set
# RESET_DEMO_DATA=true to reload it on every start instead.
set -euo pipefail
cd /home/user/app

# The seed data has a known default admin password; never publish it
: "${DEMO_ADMIN_PASSWORD:?Set DEMO_ADMIN_PASSWORD in the .env file}"

export DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=airline_db DB_USER=user DB_PASSWORD=""
export RASA_URL=http://127.0.0.1:5005
export COOKIE_SECURE=true

# PostgreSQL, reachable only from inside the container
PGBIN=$(ls -d /usr/lib/postgresql/*/bin | head -n 1)
PGDATA=/home/user/pgdata/data
fresh=false
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    mkdir -p "$PGDATA"
    "$PGBIN/initdb" -D "$PGDATA" -U user --auth=trust > /dev/null
    fresh=true
fi
"$PGBIN/pg_ctl" -D "$PGDATA" -l /home/user/pgdata/postgres.log -w \
    -o "-c listen_addresses=127.0.0.1 -k /tmp" start
if [ "$fresh" = true ]; then
    "$PGBIN/createdb" -h 127.0.0.1 -U user airline_db
fi
if [ "$fresh" = true ] || [ "${RESET_DEMO_DATA:-false}" = true ]; then
    python database/init_db.py
fi

# Logs whether the email server's port is open from this host
python deploy/check_smtp.py || true

rasa run actions --port 5055 &
rasa run --enable-api --interface 127.0.0.1 --port 5005 --model models &
uvicorn backend.main:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips '*' &

# If any server stops, stop the container so Docker restarts it
wait -n
exit 1
