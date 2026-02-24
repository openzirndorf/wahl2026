# OpenZirndorf Wahlanalyse 2026

Statische, responsive Website mit:
- Landingpage
- Genutztem Prompt
- Ergebnissen pro KI/Modell
- Disclaimer
- Impressum/Datenschutz

## Lokal testen

```bash
cd /home/fabian/openzirndorf_wahl2026
python3 -m http.server 8080
```

Dann im Browser: `http://localhost:8080`

## Struktur

- `index.html`
- `prompt/`
- `ergebnisse/`
- `ergebnisse/openai-gpt-5/`
- `ergebnisse/anthropic-claude-3-7/`
- `ergebnisse/google-gemini-2-5/`
- `disclaimer/`
- `impressum/`, `datenschutz/`
- `assets/styles.css`, `assets/app.js`, `assets/logo.svg`

Deployment-Anleitungen liegen in `docs/`.
