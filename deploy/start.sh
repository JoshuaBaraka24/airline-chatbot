#!/usr/bin/env bash
# Starts the whole system inside the container (see deploy/Dockerfile):
# PostgreSQL, the action server, the Rasa server and the FastAPI gateway.
#
# The demo data is loaded when the database is first created. Set
# RESET_DEMO_DATA=true to reload it on every start instead.
set -euo pipefail
cd /home/user/app

# The default demo passwords are in the public code; never publish them
: "${DEMO_ADMIN_PASSWORD:?Set DEMO_ADMIN_PASSWORD in the .env file}"
: "${DEMO_PASSWORD:?Set DEMO_PASSWORD in the .env file}"

export DB_HOST=127.0.0.1 DB_PORT=5432 DB_NAME=airline_db DB_USER=user DB_PASSWORD=""
export RASA_URL=http://127.0.0.1:5005
export COOKIE_SECURE=true

# PostgreSQL, reachable only from inside the container
PGBIN=$(ls -d /usr/lib/postgresql/*/bin | head -n 1)
PGDATA=/home/user/pgdata/data
SEEDED=/home/user/pgdata/seeded
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    mkdir -p "$PGDATA"
    "$PGBIN/initdb" -D "$PGDATA" -U user --auth=trust > /dev/null
fi
# Left behind if the server lost power. No PostgreSQL can be running yet, and
# the old process number may now belong to something else in the new container.
rm -f "$PGDATA/postmaster.pid"

# Shut PostgreSQL down cleanly when the container stops or a server fails
trap '"$PGBIN/pg_ctl" -D "$PGDATA" -m fast -w stop || true' EXIT
trap 'exit 0' TERM INT

"$PGBIN/pg_ctl" -D "$PGDATA" -l /home/user/pgdata/postgres.log -w \
    -o "-c listen_addresses=127.0.0.1 -k /tmp" start
if [ ! -f "$SEEDED" ]; then
    "$PGBIN/createdb" -h 127.0.0.1 -U user airline_db 2> /dev/null || true
fi
# The marker is written only after loading succeeds, so a failed first start is retried
if [ ! -f "$SEEDED" ] || [ "${RESET_DEMO_DATA:-false}" = true ]; then
    python database/init_db.py
    touch "$SEEDED"
fi

# Logs whether the email server's port is open from this host
python deploy/check_smtp.py || true

rasa run actions --port 5055 &
rasa run --enable-api --endpoints deploy/endpoints.yml --interface 127.0.0.1 --port 5005 --model models &
uvicorn backend.main:app --host 0.0.0.0 --port 7860 --proxy-headers --forwarded-allow-ips '*' &

# If any server stops, stop the container so Docker restarts it
wait -n
exit 1
