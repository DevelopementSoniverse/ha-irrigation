# Scripts

## `migrate_ha_history_to_influx.py`

Einmalige Migration der Home-Assistant-SQLite-Historie
(`states` + `states_meta` + `state_attributes`) nach **InfluxDB 1.x**.

Das Mapping entspricht der HA-InfluxDB-Integration (inkl. Triesdorf-Live-Config:
`default_measurement: state`, Tag `source=HA`, `tags_attributes: friendly_name`,
`ignore_attributes`, Exclude-Domains `persistent_notification` / `update`).

### Voraussetzungen

- Konsistente DB-Kopie (nicht Live-`scp` der offenen WAL), z. B. remote via
  `sqlite3`/`Connection.backup`, dann lokal holen
- InfluxDB 1.x erreichbar (Host-Port 8086 nur temporär öffnen)
- Passwort nur über Umgebungsvariable — nie in die Shell-History schreiben

### Beispiel

```bash
export INFLUX_PASSWORD='…'   # lokal setzen, nicht committen

python3 scripts/migrate_ha_history_to_influx.py \
  --db /path/to/home-assistant_v2_backup_migrate.db \
  --url http://100.67.226.35:8086 \
  --database homeassistant \
  --username homeassistant \
  --password-env INFLUX_PASSWORD \
  --batch-size 1000 \
  --progress
```

### Nützliche Flags

| Flag | Bedeutung |
|------|-----------|
| `--dry-run` | Nur mappen/zählen; Stichproben auf stderr, kein Write |
| `--progress` | Periodischer Fortschritt |
| `--resume-from METADATA_ID:TS[:STATE_ID]` | Nach Abbruch fortsetzen (3-teilig empfohlen) |
| `--resume-metadata-id` + `--resume-ts` | Alternative Resume-Flags (`state_id=0`) |
| `--exclude-domain` | Domain ausschließen (wiederholbar) |
| `--self-check` | Offline-Mapping-Sanity-Check (`python3 … --self-check`) |

Resume-Offset wird am Ende eines Laufs geloggt (`Last successful offset`).
Erneutes Schreiben derselben Series+Timestamp merged Fields in Influx 1.x
(idempotent bei Schema-Parität).
