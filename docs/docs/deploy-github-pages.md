# Deployment auf GitHub Pages + Subdomain

## Zielbild
Die Seite soll unter z. B. `wahl2026.openzirndorf.de` laufen.

## 1) Repository vorbereiten

1. Neues Repo anlegen, z. B. `openzirndorf-wahl2026`.
2. Inhalt von `/home/fabian/openzirndorf_wahl2026` ins Repo kopieren.
3. Diese Datei im Repo-Root anlegen: `CNAME` mit einer Zeile:

```txt
wahl2026.openzirndorf.de
```

4. Leere Datei `.nojekyll` im Repo-Root anlegen.

## 2) GitHub Pages aktivieren

1. GitHub Repo -> `Settings` -> `Pages`.
2. `Build and deployment` -> `Deploy from a branch`.
3. Branch `main` und Ordner `/ (root)` waehlen.
4. Speichern.

## 3) DNS bei openzirndorf.de setzen

### Option A (empfohlen): Subdomain mit CNAME auf GitHub Pages

DNS Record:
- Typ: `CNAME`
- Name: `wahl`
- Wert: `<dein-github-user>.github.io`

Beispiel:
- `wahl2026.openzirndorf.de` -> `openzirndorf.github.io`

### Option B: A-Records auf GitHub Pages IPs

Nur nutzen, wenn CNAME nicht moeglich ist.

## 4) HTTPS aktivieren

1. Nach DNS-Propagation erneut in `Settings -> Pages`.
2. `Enforce HTTPS` aktivieren.

## 5) Funktionstest

- `https://wahl2026.openzirndorf.de/`
- `https://wahl2026.openzirndorf.de/prompt/`
- `https://wahl2026.openzirndorf.de/ergebnisse/`

## Hinweis zu Pfaden
Diese Website nutzt Root-Pfade (`/prompt/`, `/ergebnisse/`). Das passt fuer eine eigene Subdomain. Fuer ein GitHub-Projekt ohne Custom-Domain muessten Pfade auf relativ umgestellt werden.
