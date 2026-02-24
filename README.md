# KI-Wahlanalyse Zirndorf 2026

Transparente, vergleichende Auswertung der Bürgermeisterkandidaten zur Kommunalwahl in Zirndorf (08.03.2026) auf Basis mehrerer KI-Modelle mit einheitlichem Prompt.

## Ziel
Diese Seite macht Unterschiede und Gemeinsamkeiten zwischen Modellantworten sichtbar:
- identische Prompt-Basis
- strukturierte Aufbereitung je Kandidat
- verlinkte 1:1-Originalausgaben
- klarer Disclaimer zu Grenzen und Datenlage

## Projektstruktur
- `docs/` – veröffentlichte statische Website (für Pages)
- `docs/prompt/` – verwendeter Prompt
- `docs/ergebnisse/` – Ergebnisse je KI/Modell
- `docs/ergebnisse/gesamtvergleich/` – KI-übergreifende Zusammenfassung
- `docs/disclaimer/`, `docs/impressum/`, `docs/datenschutz/`

## Lokal testen
Einfach statisch starten, z. B.:
```bash
cd docs
python3 -m http.server 8080
```
Dann im Browser: http://localhost:8080

## Deployment (GitLab Pages über Branch)
Wenn ihr „Deploy from branch“ nutzt:

* Branch: main
* Folder: /docs
Danach publiziert GitLab Pages direkt den Inhalt aus docs/.

## Hinweise
Die Inhalte sind eine Unterstützung zur Einordnung, keine Wahlempfehlung.
Für belastbare Bewertung immer Originalquellen prüfen.


entwickelt mit ❤️  in Zirndorf
