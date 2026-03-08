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
    raw = matches[1].strip() if len(matches) >= 2 else "Kein Eingang"
    return strip_tags(raw)


def get_row_cells(row_html: str) -> list[str]:
    """Extract text from all th and td cells in a row."""
    cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL)
    return [strip_tags(c) for c in cells]


def parse_party_name(cell_html: str) -> str:
    """Extract party short name from abbr tag or partei__name span."""
    abbr = re.search(r"<abbr[^>]*>([^<]+)</abbr>", cell_html)
    if abbr:
        return strip_tags(abbr.group(1)).strip()
    span = re.search(r'class="partei__name">\s*([^<]+)', cell_html)
    if span:
        return strip_tags(span.group(1)).strip()
    return strip_tags(cell_html).strip()


def parse_party_color(cell_html: str) -> str:
    """Extract party color from inline style."""
    m = re.search(r'partei__farbe"\s+style="color:([^"]+)"', cell_html)
    return m.group(1).strip() if m else "#888"


def parse_buergermeisterwahl(html: str) -> dict:
    status = parse_status(html)

    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
    # Table layout during counting (3 tables):
    #   0 = Auszählungsstand (progress per Gebiet)
    #   1 = Potenzielle Stichwahlteilnehmer (top 2 only)
    #   2 = Stimmenanteile tabellarisch (all candidates + tfoot with KPI)
    # Table layout after final result (2 tables):
    #   0 = Stichwahlteilnehmer
    #   1 = Stimmenanteile tabellarisch (all candidates + tfoot with KPI)
    if len(tables) >= 3:
        table = tables[2]
    elif len(tables) == 2:
        table = tables[1]
    else:
        return {
            "lastUpdated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "wahlberechtigte": 0, "waehler": 0, "wahlbeteiligung": 0.0,
            "ungueltig": 0, "gueltig": 0, "candidates": []
        }

    # "Stimmenanteile tabellarisch"

    # ── Kandidaten aus tbody ──
    candidates = []
    tbody = re.search(r"<tbody>(.*?)</tbody>", table, re.DOTALL)
    if tbody:
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody.group(1), re.DOTALL):
            # All th elements in the row
            ths = re.findall(r"<th[^>]*>(.*?)</th>", row, re.DOTALL)
            if len(ths) < 2:
                continue
            party = parse_party_name(ths[0])
            color = parse_party_color(ths[0])
            name = strip_tags(ths[1]).strip()
            if not name:
                continue
            # Stimmen and Anteil from data-sort on td elements
            td_sorts = re.findall(r'<td[^>]+data-sort="([^"]*)"', row)
            stimmen = parse_num(td_sorts[0]) if td_sorts else 0
            anteil = parse_float(td_sorts[1]) if len(td_sorts) > 1 else 0.0
            candidates.append({
                "party": party,
                "color": PARTY_COLORS.get(party, color),
                "name": name,
                "stimmen": stimmen,
                "anteil": anteil,
            })

    # ── KPI-Werte aus tfoot ──
    wahlberechtigte = waehler = ungueltig = gueltig = 0
    tfoot = re.search(r"<tfoot>(.*?)</tfoot>", table, re.DOTALL)
    if tfoot:
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tfoot.group(1), re.DOTALL):
            cells = get_row_cells(row)
            if not cells:
                continue
            label = cells[0]
            # Use data-sort for numeric value (avoid thousand-dot ambiguity)
            num_sort = re.findall(r'data-sort="(\d+)"', row)
            val = int(num_sort[0]) if num_sort else 0
            if "Wahlberechtigte" in label:
                wahlberechtigte = val
            elif "hler" in label and "berechtigte" not in label:
                waehler = val
            elif "ngiltig" in label or "ngültig" in label or "Ung" in label:
                ungueltig = val
            elif "ltige" in label and "Un" not in label:
                gueltig = val

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
        "candidates": candidates,
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
