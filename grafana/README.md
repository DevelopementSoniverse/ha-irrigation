# Grafana (Triesdorf / Community Addon)

Addon: `a0d7b954_grafana` (v12.1.0, Ingress, started).  
InfluxDB: `http://a0d7b954-influxdb:8086`, DB `homeassistant`, User `homeassistant`.

## Zugang

| Weg | Details |
|---|---|
| Ingress | HA → Grafana; Auto-Login als `admin` (`grafana_ingress_user`, Default) |
| HTTP-API im Addon-Netz | `http://a0d7b954-grafana:3000` (von SSH-Addon erreichbar) |
| Default Admin | User `admin`, Passwort `hassio` (in Addon-`grafana.ini` fest; `GF_SECURITY_ADMIN_PASSWORD` überschreibt das **nicht**) |
| Port 80/tcp | aktuell nicht gemappt (`null`) → kein Host-Port, nur Ingress / internes Netz |
| `/addon_configs/a0d7b954_grafana` | **existiert nicht**; Addon mappt nur `homeassistant_config`, `share`, `ssl` |

## Provisioning

### Empfohlen: HTTP-API

```bash
./grafana/scripts/provision_via_api.sh
```

Liest Influx-Passwort aus `/tmp/ha-influx-secrets/influxdb_password` (nicht committen).

Manuell (auf HA, im SSH-Addon):

```bash
curl -u admin:hassio -H 'Content-Type: application/json' \
  -X POST http://a0d7b954-grafana:3000/api/datasources \
  -d @datasource.json

curl -u admin:hassio -H 'Content-Type: application/json' \
  -X POST http://a0d7b954-grafana:3000/api/dashboards/db \
  -d '{"dashboard": {...}, "overwrite": true}'
```

### Optional: File Provisioning

Vorlagen unter `grafana/provisioning/`. Das Community-Addon hat keinen dedizierten Provisioning-Mount unter `/addon_configs`. Theoretisch über `/share/grafana/...` + `env_vars` (`GF_PATHS_PROVISIONING`), dann Addon-Neustart. Primärweg bleibt die API.

## Verifikations-Dashboard

UID: `irrigation-verification`  
Panels nutzen InfluxQL mit Object-IDs (ohne Domain):

| Panel | Measurement | `entity_id` |
|---|---|---|
| Bodenfeuchte | `%` | `gw3000a_soil_moisture_1`, `gw3000a_soil_moisture_2` |
| Leistung | `W` | `randreihe_leistung`, `irrigation_2_leistung` |
| Strahlung | `W/m²` | `gw3000a_solar_radiation` |

Weitere nützliche Object-IDs: `randreihe_luftfeuchtigkeit` (Ø Feuchte), `randreihe_2` (Strahlung seit letzter Bewässerung), `randreihe_4` (Läufe 24h).
