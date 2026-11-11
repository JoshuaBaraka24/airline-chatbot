#!/usr/bin/env bash
# Starts the whole system inside the Space container (see deploy/Dockerfile).
# The database is rebuilt from the seed data on every start, so each restart
# gives a fresh demo, just like running database/init_db.py locally.
set -euo pipefail
cd /home/user/app

# The seed data has a known default admin password; never publish it
: "${DEMO_ADMIN_PASSWORD:?Set DEMO_ADMIN_PASSWORD as a Space secret}"

export DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=airline_db DB_USER=user DB_PASSWORD=""
export RASA_URL=http://127.0.0.1:5005
export COOKIE_SECURE=true

# PostgreSQL, reachable only from inside the container
PGBIN=$(ls -d /usr/lib/postgresql/*/bin | head -n 1)
PGDATA=/home/user/pgdata
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    "$PGBIN/initdb" -D "$PGDATA" -U user --auth=trust > /dev/null
fi
"$PGBIN/pg_ctl" -D "$PGDATA" -l /home/user/postgres.log -w \
    -o "-c listen_addresses=127.0.0.1 -k /tmp" start
"$PGBIN/createdb" -h 127.0.0.1 -U user airline_db 2> /dev/null || true
python database/init_db.py

# Logs whether the email server's port is open from this host
python deploy/check_smtp.py || true

rasa run actions --port 5055 &
rasa run --enable-api --interface 127.0.0.1 --port 5005 --model models &
uvicorn backend.main:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips '*' &

# If any server stops, stop the container so the Space restarts it
wait -n
exit 1
