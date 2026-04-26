# Alarme, Fehler und Warnungen

Diese Seite listet alle Laufzeit-Zustände auf, die die Irrigation-Computer-
Integration melden kann – was sie auslöst und welche sichtbaren Folgen sie
für den Nutzer haben.

*English version: [`ALERTS.md`](ALERTS.md).*

## Wie Alarme ausgeliefert werden

Jeder Alarm wird an **zwei** Stellen gemeldet (die zweite ist optional):

1. **Persistente Benachrichtigung** in Home Assistant
   (Einstellungen → Benachrichtigungen). Die Notification-ID folgt dem
   Muster `irrigation_computer_<suffix>_<zone_id>` (bzw.
   `irrigation_computer_<suffix>` bei Controller-weiten Alarmen), damit
   dieselbe Bedingung die bestehende Karte aktualisiert statt eine neue
   anzulegen.
2. **Push-Nachricht** auf die konfigurierten Mobile-App-Geräte, sofern
   *„Custom-Component-Alerts als Push senden"* in den Optionen der
   Integration aktiviert ist und mindestens ein Smartphone ausgewählt wurde.

Alarme werden **dedupliziert**: Solange ein Alarm aktiv ist, wird er nicht
erneut gepostet. Beim Start eines neuen Zonenlaufs werden alle zonenspezifischen
Alarme dieser Zone automatisch zurückgesetzt, damit ein erneuter Fehler wieder
melden kann.

Zonen-Alarme setzen zusätzlich den zugehörigen Sensor
`sensor.<zone>_relay_error` (maschinenlesbarer Fehlercode) und erscheinen auf
der Dashboard-Karte der Zone unter *Alerts & Sicherheit*.

> **Hinweis zu Entity-IDs:** Entity-Namen laufen über das
> Home-Assistant-Übersetzungssystem. Bei **Neuinstallationen** leitet Home
> Assistant die `entity_id` aus dem übersetzten Namen in der aktiven Sprache
> ab – auf einer deutschen HA-Installation heißt die Entity also z. B.
> `sensor.<zone>_relaisfehler` statt `sensor.<zone>_relay_error`. Bestehende
> `entity_id`s bleiben unverändert; bei Bedarf lassen sie sich in
> *Einstellungen → Geräte & Dienste* umbenennen.

## Zonen-bezogene Alarme

Jede Zeile unten ist ein Alarm, der für **eine einzelne Zone** ausgelöst wird.
Die Spalte **Fehlercode** entspricht dem Wert von
`sensor.<zone>_relay_error` nach dem Vorfall.

| Fehlercode | Auslöser | Auswirkung auf den aktuellen Lauf | Benachrichtigung |
|---|---|---|---|
| `relay_unavailable` | Relay-Entity existiert nicht oder ist im Zustand `unavailable` / `unknown`, wenn ein Lauf starten soll | Lauf wird **abgebrochen, bevor das Relais geschaltet wird** | Persistent + Push |
| `turn_on_failed_<id>` <br> (`turn_on failed: …`) | Der Service-Aufruf `switch.turn_on` hat eine Exception ausgelöst | Lauf wird **abgebrochen**, Zone bleibt im Stop-Zustand | Persistent + Push |
| `turn_off_failed_<id>` <br> (`turn_off failed: …`) | `switch.turn_off` hat am Ende des Laufs eine Exception ausgelöst | Lauf endet regulär; ein **Watchdog** startet und versucht `turn_off` bis zu 3× erneut | Persistent + Push |
| `watchdog_turn_off_failed` | Alle Watchdog-Versuche haben das Relais nicht ausgeschaltet | Relais ist möglicherweise noch an – **manueller Eingriff nötig** | Persistent + Push |
| `manual_turn_off_failed` | Nutzer stoppt manuell, aber `switch.turn_off` schlägt fehl | Zone wird als gestoppt markiert; Relais-Zustand unbekannt | Persistent + Push |
| `power_sensor_unavailable` | Der konfigurierte Leistungssensor liefert im Startfenster (`POWER_WAIT_SECONDS = 30 s`) keinen numerischen Wert | Lauf läuft weiter; Leistungs-Checks entfallen | Persistent + Push |
| `power_no_consumption` | Leistungssensor meldet während des gesamten Startfensters `≤ 0 W` | Lauf läuft weiter; deutet darauf hin, dass der Motor nicht anläuft oder der falsche Sensor verknüpft ist | Persistent + Push |
| `power_low` | Gemessene Anlaufleistung lag `≤ zone.power_min` (Unterstrom-Schwellwert) | Lauf läuft weiter; Hinweis auf schwache Pumpe / Trockenlauf | Persistent + Push |
| `power_high` | Gemessene Anlaufleistung lag `≥ zone.power_max` (Überstrom-Schwellwert) | Lauf läuft weiter; Hinweis auf blockierten oder überlasteten Motor | Persistent + Push |
| `power_after_off` | Leistungssensor meldet zwei Sekunden nach Run-Ende noch `> 0 W` | Lauf ist bereits beendet, **aber das Relais versorgt den Motor möglicherweise weiter** | Persistent + Push |
| `power_sensor_unavailable_after_off` | Leistungssensor ist während der Nachlauf-Prüfung nicht verfügbar | Der Motor-Stopp kann nicht verifiziert werden | Persistent + Push |
| `power_sensor_invalid_after_off` | Leistungssensor liefert nach dem Stopp einen nicht als Zahl interpretierbaren Wert | Der Motor-Stopp kann nicht verifiziert werden | Persistent + Push |
| `run_timeout` | Zone ist nach `watering_duration + 5 s` immer noch als laufend markiert | Lauf wird **nicht zwangsgestoppt**; weist auf möglicherweise hängenden Task hin | Persistent + Push |
| `too_many_runs_24h` | Anzahl Läufe in den letzten 24 h überschreitet den konfigurierten *„Alarm-Grenzwert Läufe in 24 h"* (`0` = deaktiviert) | **Nur informativ** – weder der laufende noch zukünftige Läufe werden blockiert | Persistent + Push |
| `soil_moisture_sensors_unavailable` | Bodenfeuchte-Trigger ist aktiv, aber keiner der konfigurierten Sensoren liefert aktuell einen gültigen Zahlenwert | Trigger kann nicht ausgewertet werden; der Haltezeit-Zähler (`moisture_below_since`) bleibt **absichtlich unverändert**, damit ein kurzer Sensor-Ausfall die Bewässerung nicht unnötig verzögert. Alarm wird automatisch gelöscht, sobald mindestens ein Sensor wieder einen Wert liefert | Persistent + Push |

### Verzögerter Leistungs-Check

Mit *„Stromalarm-Verzögerung (Sekunden)"* pro Zone können langsam anlaufende
Pumpen hochlaufen, bevor die erste Leistungsbewertung beginnt. Wird die Zone
während der Verzögerung gestoppt (z. B. durch den Nutzer oder einen
abgebrochenen Task), entfallen die nachfolgenden Checks stillschweigend – es
werden keine Fehlalarme ausgelöst, solange die Zone gar nicht mehr läuft.

## Controller-weite Alarme

Diese Alarme gelten nicht für eine einzelne Zone, sondern für die gesamte
Integration.

| Fehlercode | Auslöser | Auswirkung | Benachrichtigung |
|---|---|---|---|
| `radiation_source_unavailable` | Die konfigurierte Strahlungsquelle fehlt oder ist im Zustand `unavailable` / `unknown` | Die Strahlungsintegration pausiert; **strahlungsbasierte Trigger können nicht auslösen**, bis die Quelle wieder verfügbar ist | Persistent + Push |
| `radiation_source_stale` | Die Quelle meldet `> 0 W/m²`, wurde aber seit mehr als `RADIATION_STALE_SECONDS` (2 Stunden) nicht aktualisiert | Wie oben – der Sensor gilt als festgefahren, Strahlungs-Trigger pausieren effektiv | Persistent + Push |

Beide Alarme werden automatisch gelöscht, sobald die Quelle wieder einen
frischen und gültigen Wert liefert (auch `0 W/m²` nachts zählt als gültig).

## Nur-Log-Warnungen

Diese Bedingungen erzeugen **keine** Benachrichtigung, sind aber im
Home-Assistant-Log sichtbar und nützlich beim Debuggen.

| Log-Level | Meldung | Kontext |
|---|---|---|
| `WARNING` | `Zone … appears to have been running across restart – forcing relay off` | Persistenter Zustand gab eine Zone als laufend an, als Home Assistant neu gestartet wurde; der Koordinator schickt defensiv `switch.turn_off`. |
| `WARNING` | `start_zone: unknown zone_id …` | Service mit Zonen-ID aufgerufen, die im Config-Entry nicht (mehr) existiert. |
| `WARNING` | `start_zone: no controller for zone_id …` | Zonen-ID existiert, aber ihr Controller wurde entladen. |
| `WARNING` | `No mobile_app notify service found for device …; skipping push notification` | In den Optionen hinterlegte Device-ID hat keinen passenden Service `notify.mobile_app_<slug>` (Mobile-App deinstalliert oder Gerät entfernt). Die persistente Benachrichtigung wird trotzdem erzeugt. |
| `EXCEPTION` | `Relay turn_on failed for zone …` / `Relay turn_off failed for zone …` / `Force relay off failed for …` / `Manual stop relay_off failed for …` | Stacktrace zum jeweils zugehörigen Zonen-Alarm oben. |
| `EXCEPTION` | `Failed to create persistent notification` | Der Benachrichtigungsdienst von HA war nicht verfügbar; der Alarm geht verloren. |
| `EXCEPTION` | `Failed to send push notification to device … via …` | Aufruf des Mobile-App-Notify-Service schlug fehl (z. B. Gerät offline). Die persistente Benachrichtigung war bereits erfolgreich. |
| `EXCEPTION` | `Failed to persist runtime state` | Speicher-Schreibvorgang für Laufhistorie / Strahlungs-Akkumulator ist fehlgeschlagen. |
| `EXCEPTION` | `Failed to update dashboard '…'` | Rebuild des automatisch verwalteten Lovelace-Dashboards schlug fehl; keine Auswirkungen auf die Zonensteuerung. |

## Alarme manuell zurücksetzen

- Beim Starten einer Zone werden alle aktiven Zonen-Alarme dieser Zone
  zurückgesetzt (neuer `switch.<zone>_start` oder
  `irrigation_computer.start_zone`-Service-Aufruf).
- Das Verwerfen der persistenten Benachrichtigung in der Home-Assistant-UI
  blendet sie nur einmal aus – besteht die zugrunde liegende Bedingung beim
  nächsten Check weiter, wird die Benachrichtigung neu erstellt.
- Der Sensor `sensor.<zone>_relay_error` behält den letzten Fehlercode, bis
  die Zone wieder erfolgreich läuft.
