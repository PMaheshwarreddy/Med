#!/usr/bin/env bash
# Starts the local Postgres (pgvector) container and the Medora API on :8100.
# Port 8000 is left alone because another service on this machine uses it.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  echo "backend/.env is missing. Copy .env.example to .env and fill it in." >&2
  exit 1
fi
set -a; source .env; set +a

# Phones open the QR pages from THIS server (port 8100), which serves the
# built web app (frontend/build/web). Rebuild it when the app's code changed
# since the last build, so phones always get the current screens. Skipped
# with MEDORA_SKIP_WEB_BUILD=1 or when Flutter is not installed.
web=../frontend
if [ "${MEDORA_SKIP_WEB_BUILD:-0}" != 1 ] && command -v flutter >/dev/null; then
  built=$web/build/web/main.dart.js
  if [ ! -f "$built" ] || [ -n "$(find $web/lib $web/web $web/assets $web/pubspec.yaml -newer "$built" -print -quit 2>/dev/null)" ]; then
    echo "Building the web app for phones (about a minute; only when the app changed)..."
    (cd $web && flutter build web --release --no-web-resources-cdn) || echo "Web build failed: QR pages will use the kiosk's own address." >&2
  fi
elif [ ! -f "$web/build/web/index.html" ]; then
  echo "No web build: run 'flutter build web --release --no-web-resources-cdn' in frontend/ so QR codes work." >&2
fi

# The local container is only needed when the database URL points at this
# machine; a hosted database (for example Supabase) is used as-is.
db_host="$(python3 -c 'import os,urllib.parse as u; print(u.urlparse(os.environ["MEDORA_DATABASE_URL"]).hostname)')"
if [ "$db_host" != "localhost" ] && [ "$db_host" != "127.0.0.1" ]; then
  # 0.0.0.0: patients' phones on the same network reach the API (phone intake);
  # MEDORA_HOST=127.0.0.1 keeps it to this machine.
  exec uv run uvicorn app.main:app --host "${MEDORA_HOST:-0.0.0.0}" --port 8100 "$@"
fi

# The password is taken from MEDORA_DATABASE_URL so there is one source of truth.
db_password="$(python3 -c 'import os,urllib.parse as u; print(u.urlparse(os.environ["MEDORA_DATABASE_URL"]).password)')"

if ! docker ps -a --format '{{.Names}}' | grep -qx medora-db; then
  docker run -d --name medora-db \
    -e POSTGRES_USER=medora -e POSTGRES_PASSWORD="$db_password" -e POSTGRES_DB=medora \
    -p 127.0.0.1:5432:5432 -v medora_pgdata:/var/lib/postgresql/data \
    pgvector/pgvector:pg16 >/dev/null
else
  docker start medora-db >/dev/null
fi

until docker exec medora-db pg_isready -U medora -q; do sleep 0.5; done

# 0.0.0.0: patients' phones on the same network reach the API (phone intake);
  # MEDORA_HOST=127.0.0.1 keeps it to this machine.
  exec uv run uvicorn app.main:app --host "${MEDORA_HOST:-0.0.0.0}" --port 8100 "$@"
