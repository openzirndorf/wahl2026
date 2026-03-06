#!/usr/bin/env python3
"""
Scraper für die Wahlergebnisse Zirndorf 2026
Holt HTML-Seiten der OSRZ-Wahlpräsentation und erzeugt JSON-Dateien.
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

BM_URL = "https://wahlen.osrz-akdb.de/mf-p/573134/1/20260308/buergermeisterwahl_gemeinde/ergebnisse.html"
GR_URL = "https://wahlen.osrz-akdb.de/mf-p/573134/2/20260308/gemeinderatswahl_gemeinde/ergebnisse.html"

PARTY_NAMES = ["CSU", "FREIE WÄHLER", "AfD", "GRÜNE", "SPD", "Die Linke", "FDP", "Volt", "ZBG"]
PARTY_COLORS = {
    "CSU": "#005CA9",
    "FREIE WÄHLER": "#FF6600",
    "AfD": "#009DE0",
    "GRÜNE": "#1FAB2C",
    "SPD": "#E3000F",
    "Die Linke": "#BE3075",
    "FDP": "#FFED00",
    "Volt": "#562883",
    "ZBG": "#4F8F17",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&auml;", "ä", s)
    s = re.sub(r"&ouml;", "ö", s)
    s = re.sub(r"&uuml;", "ü", s)
    s = re.sub(r"&Auml;", "Ä", s)
    s = re.sub(r"&Ouml;", "Ö", s)
    s = re.sub(r"&Uuml;", "Ü", s)
    s = re.sub(r"&szlig;", "ß", s)
    s = re.sub(r"&[a-zA-Z]+;", "", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_num(s: str) -> int:
    s = s.replace(".", "").replace(",", ".").replace(" ", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return 0


def parse_float(s: str) -> float:
    s = s.replace(",", ".").replace("%", "").replace(" ", "").strip()
    try:
        return round(float(s), 1)
    except ValueError:
        return 0.0


def parse_status(html: str) -> str:
    matches = re.findall(r'class="stand"[^>]*>\s*([^<]+)</p>', html)
    return matches[1].strip() if len(matches) >= 2 else "Kein Eingang"


def get_row_cells(row_html: str) -> list[str]:
    """Extract text from all th and td cells in a row."""
    cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL)
    return [strip_tags(c) for c in cells]


def parse_buergermeisterwahl(html: str) -> dict:
    status = parse_status(html)

    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
    if not tables:
        return {"status": status, "candidates": []}

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tables[0], re.DOTALL)
    candidates = []
    wahlberechtigte = waehler = ungueltig = gueltig = 0

    skip_labels = {"Partei", "Direktkandidat", "Stimmen", "Anteil", ""}

    for row in rows:
        cells = get_row_cells(row)
        if len(cells) < 3:
            continue
        label = cells[0]
        if label in skip_labels or label == "Partei":
            continue

        if "Wahlberechtigte" in label:
            wahlberechtigte = parse_num(cells[2]) if len(cells) > 2 else 0
        elif label in ("Wähler", "Wahler"):
            waehler = parse_num(cells[2]) if len(cells) > 2 else 0
        elif "Ungültige" in label or "Ungultige" in label:
            ungueltig = parse_num(cells[2]) if len(cells) > 2 else 0
        elif "Gültige" in label or "Gultige" in label:
            gueltig = parse_num(cells[2]) if len(cells) > 2 else 0
        else:
            # Candidate row: Party | Name | Stimmen | Anteil
            if len(cells) >= 4:
                party = cells[0]
                name = cells[1]
                stimmen = parse_num(cells[2])
                anteil = parse_float(cells[3])
                candidates.append({
                    "party": party,
                    "color": PARTY_COLORS.get(party, "#888"),
                    "name": name,
                    "stimmen": stimmen,
                    "anteil": anteil
                })

    wahlbeteiligung = round(waehler / wahlberechtigte * 100, 1) if wahlberechtigte > 0 else 0.0
    candidates.sort(key=lambda x: x["stimmen"], reverse=True)

    return {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "wahlberechtigte": wahlberechtigte,
        "waehler": waehler,
        "wahlbeteiligung": wahlbeteiligung,
        "ungueltig": ungueltig,
        "gueltig": gueltig,
        "candidates": candidates
    }


def parse_gemeinderatswahl(html: str) -> dict:
    status = parse_status(html)

    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
    if not tables:
        return {"status": status, "parties": []}

    # Table 1: party overview
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tables[0], re.DOTALL)
    parties = []
    wahlberechtigte = waehler = ungueltig = gueltig = 0

    skip_labels = {"Partei", "Stimmen", "Anzahl", "Anteil", "Gewinn und Verlust in %-Punkten", ""}

    for row in rows:
        cells = get_row_cells(row)
        if len(cells) < 2:
            continue
        label = cells[0]
        if label in skip_labels:
            continue

        if "Stimmberechtigte" in label:
            wahlberechtigte = parse_num(cells[1])
        elif label in ("Wähler", "Wahler"):
            waehler = parse_num(cells[1])
        elif "Ungültige" in label:
            ungueltig = parse_num(cells[1])
        elif "Gültige" in label:
            gueltig = parse_num(cells[1])
        elif len(cells) >= 3:
            party = label
            stimmen = parse_num(cells[1])
            anteil = parse_float(cells[2])
            gv = cells[3] if len(cells) > 3 else "-"
            parties.append({
                "party": party,
                "color": PARTY_COLORS.get(party, "#888"),
                "stimmen": stimmen,
                "anteil": anteil,
                "gv": gv
            })

    wahlbeteiligung = round(waehler / wahlberechtigte * 100, 1) if wahlberechtigte > 0 else 0.0

    # Tables 2..10: candidates per party
    candidates_by_party = {}
    for i, table in enumerate(tables[1:], 0):
        if i >= len(PARTY_NAMES):
            break
        pname = PARTY_NAMES[i]
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL)
        cands = []
        for row in rows:
            cells = get_row_cells(row)
            if len(cells) < 2:
                continue
            # Skip header rows
            try:
                nr = int(cells[0])
            except ValueError:
                continue
            name = cells[1]
            stimmen = parse_num(cells[2]) if len(cells) > 2 else 0
            anteil = parse_float(cells[3]) if len(cells) > 3 else 0.0
            if name:
                cands.append({"nr": nr, "name": name, "stimmen": stimmen, "anteil": anteil})
        if cands:
            candidates_by_party[pname] = cands

    parties.sort(key=lambda x: x["stimmen"], reverse=True)

    return {
        "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "wahlberechtigte": wahlberechtigte,
        "waehler": waehler,
        "wahlbeteiligung": wahlbeteiligung,
        "ungueltig": ungueltig,
        "gueltig": gueltig,
        "parties": parties,
        "candidatesByParty": candidates_by_party
    }


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "docs/live/data"

    print("Fetching Bürgermeisterwahl...")
    bm_html = fetch(BM_URL)
    bm_data = parse_buergermeisterwahl(bm_html)
    bm_path = f"{output_dir}/buergermeister.json"
    with open(bm_path, "w", encoding="utf-8") as f:
        json.dump(bm_data, f, ensure_ascii=False, indent=2)
    print(f"  → {bm_path} | Status: {bm_data['status']} | Kandidaten: {len(bm_data['candidates'])}")

    print("Fetching Gemeinderatswahl...")
    gr_html = fetch(GR_URL)
    gr_data = parse_gemeinderatswahl(gr_html)
    gr_path = f"{output_dir}/gemeinderat.json"
    with open(gr_path, "w", encoding="utf-8") as f:
        json.dump(gr_data, f, ensure_ascii=False, indent=2)
    print(f"  → {gr_path} | Status: {gr_data['status']} | Parteien: {len(gr_data['parties'])}")

    print("Done.")


if __name__ == "__main__":
    main()
