# Deployment per SSH / Webupload (statische Files)

## Zielbild
Die Website wird auf eurem bestehenden Webspace bereitgestellt, z. B. unter:
- `https://openzirndorf.de/wahl2026/` oder
- `https://wahl2026.openzirndorf.de/`

## A) Bereitstellung per SSH (wenn Zugriff vorhanden)

1. Lokal in den Projektordner:

```bash
cd /home/fabian/openzirndorf_wahl2026
```

2. Upload auf Server (Beispiel mit `scp`):

```bash
scp -r . user@server:/var/www/wahl2026/
```

3. Falls unter Unterpfad (`/wahl2026/`) gehostet wird:
- Aktuell nutzen die Seiten Root-Pfade (`/prompt/`).
- Ich kann dir auf Wunsch eine Unterpfad-Variante bauen (`/wahl2026/prompt/`).

## B) Bereitstellung per Webupload (kein Shell-Zugang)

1. Alle Dateien/Ordner aus `openzirndorf_wahl2026` als ZIP packen.
2. Im Hosting-Panel in Zielordner entpacken.
3. Pruefen, dass `index.html` im Zielordner liegt.

## C) DNS/Weiterleitung

Wenn Subdomain genutzt werden soll:
- `wahl2026.openzirndorf.de` auf Zielhost zeigen (A/AAAA oder CNAME je Hosting).

## D) Checkliste nach Upload

- Startseite erreichbar
- Unterseiten erreichbar (`/prompt/`, `/ergebnisse/`, `/disclaimer/`)
- HTTPS aktiv
- Impressum/Datenschutz finalisiert
