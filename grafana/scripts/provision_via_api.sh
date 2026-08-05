#!/usr/bin/env bash
# Provisioniert InfluxDB-Datasource + Irrigation-Verification-Dashboard
# auf Triesdorf HA Grafana (Addon a0d7b954_grafana) per HTTP-API.
#
# Voraussetzung: SSH-Alias triesdorfHomeAssistant, Influx-Passwort lokal unter
#   /tmp/ha-influx-secrets/influxdb_password
#
# Nutzung:
#   ./grafana/scripts/provision_via_api.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PASS_FILE="${INFLUXDB_PASSWORD_FILE:-/tmp/ha-influx-secrets/influxdb_password}"
GRAFANA_URL="${GRAFANA_URL:-http://a0d7b954-grafana:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-hassio}"
SSH_HOST="${SSH_HOST:-triesdorfHomeAssistant}"

if [[ ! -f "$PASS_FILE" ]]; then
  echo "Missing Influx password file: $PASS_FILE" >&2
  exit 1
fi

DS_TMP="$(mktemp)"
DASH_TMP="$(mktemp)"
trap 'rm -f "$DS_TMP" "$DASH_TMP"' EXIT

python3 - "$PASS_FILE" "$ROOT" "$DS_TMP" "$DASH_TMP" <<'PY'
import json, pathlib, sys
pw = pathlib.Path(sys.argv[1]).read_text().strip()
root = pathlib.Path(sys.argv[2])
ds = json.loads((root / "grafana/api/datasource.json").read_text())
ds["secureJsonData"]["password"] = pw
pathlib.Path(sys.argv[3]).write_text(json.dumps(ds))
dash = json.loads((root / "grafana/dashboards/irrigation-verification.json").read_text())
payload = {
    "dashboard": dash,
    "overwrite": True,
    "message": "provision irrigation verification",
}
pathlib.Path(sys.argv[4]).write_text(json.dumps(payload))
PY

echo "Provisioning datasource via ${SSH_HOST} -> ${GRAFANA_URL} ..."
scp -q "$DS_TMP" "${SSH_HOST}:/tmp/grafana-datasource.json"
scp -q "$DASH_TMP" "${SSH_HOST}:/tmp/grafana-dashboard.json"

ssh "$SSH_HOST" bash -s -- "$GRAFANA_URL" "$GRAFANA_USER" "$GRAFANA_PASS" <<'REMOTE'
set -euo pipefail
URL="$1"
USER="$2"
PASS="$3"
AUTH=(-u "${USER}:${PASS}")

EXISTING="$(curl -sS "${AUTH[@]}" "${URL}/api/datasources/uid/influxdb_ha" || true)"
if echo "$EXISTING" | jq -e '.id' >/dev/null 2>&1; then
  ID="$(echo "$EXISTING" | jq -r '.id')"
  echo "Updating datasource id=${ID}"
  curl -sS "${AUTH[@]}" -H 'Content-Type: application/json' \
    -X PUT "${URL}/api/datasources/${ID}" \
    --data-binary @/tmp/grafana-datasource.json | jq '{id,uid,name,database,url}'
else
  echo "Creating datasource"
  curl -sS "${AUTH[@]}" -H 'Content-Type: application/json' \
    -X POST "${URL}/api/datasources" \
    --data-binary @/tmp/grafana-datasource.json | jq '{id,name,message}'
fi

DS_ID="$(curl -sS "${AUTH[@]}" "${URL}/api/datasources/uid/influxdb_ha" | jq -r '.id')"
echo "Proxy test (SHOW MEASUREMENTS)..."
curl -sS "${AUTH[@]}" \
  "${URL}/api/datasources/proxy/${DS_ID}/query?db=homeassistant&q=SHOW%20MEASUREMENTS" | head -c 400
echo

echo "Importing dashboard..."
curl -sS "${AUTH[@]}" -H 'Content-Type: application/json' \
  -X POST "${URL}/api/dashboards/db" \
  --data-binary @/tmp/grafana-dashboard.json | jq .

rm -f /tmp/grafana-datasource.json /tmp/grafana-dashboard.json
echo "Done."
REMOTE
