#!/usr/bin/env python3
"""
Berechnet GeoJSON-Polygone für jeden Stimmbezirk (Zirndorf 2026).

1. Overpass API: alle Straßen-Wege im Stadtgebiet per Bounding Box
2. Straßennamen normalisieren (volle OSM-Namen → normalisiert)
3. Wege den Stimmbezirken zuordnen
4. Pro Stimmbezirk concave hull (Shapely) berechnen
5. An Zirndorf-Gemeindegrenze clippen
6. Als GeoJSON exportieren → docs/analyse/bezirk_polygons.geojson
"""
import json, math, os, sys, time
from collections import defaultdict
import requests
from shapely.geometry import MultiPoint, shape, mapping
from shapely.ops import unary_union

# Zirndorf bounding box (etwas Puffer)
BBOX = "49.395,10.865,49.475,10.975"

# ── Straße → Stimmbezirke ──────────────────────────────────────────────────────
# Normalisierungsregeln: Kleinschrift, "straße"→"str", "strasse"→"str",
# Sonderzeichen entfernen, mehrfache Leerzeichen komprimieren.
STREET_TO_BZ = {
    # SBZ 1 (Gebiet 1)
    "albrecht-durer-str":           [1],
    "am steinacker":                [1],
    "badstr":                       [1],
    "brandstatterstr":              [1],
    "carl-benz-str":                [1],
    "frauenschlagerstr":            [1],
    "heinestr":                     [1],
    "hirtenackerstr":               [1],
    "im bibertgrund":               [1],
    "jordanstr":                    [1],
    "neptunstr":                    [1],
    "nurnberger str":               [1],
    "oberasbacher str":             [1],
    "osterreicher str":             [1],
    "ostmarkstr":                   [1],
    "plauener str":                 [1],
    "rothenburger str":             [1, 19],
    "rudolf-diesel-str":            [1],
    "sandackerstr":                 [1],
    "siebenburger str":             [1],
    # SBZ 2 (Gebiet 2)
    "am sportplatz":                [2],
    "bahnhofstr":                   [2, 4],
    "carl-diem-str":                [2],
    "donauschwabenweg":             [2],
    "eichenhain":                   [2],
    "fasanenweg":                   [2],
    "felsenstr":                    [2],
    "fliederstr":                   [2],
    "fuggerstr":                    [2],
    "grillenbergerstr":             [2],
    "heimgartenstr":                [2],
    "jahnstr":                      [2],
    "lerchenstr":                   [2],
    "parkstr":                      [2],
    "rudolf-harbig-str":            [2],
    "turnstr":                      [2],
    "wallensteinstr":               [2],
    "walter-gropius-weg":           [2],
    "weidachstr":                   [2],
    "weinbergstr":                  [2],
    # SBZ 3 (Gebiet 3)
    "am amselschlag":               [3],
    "am hammerstattchen":           [3],
    "am muhlenpark":                [3],
    "anwandener str":               [3],
    "buchackerstr":                 [3],
    "fischerweg":                   [3],
    "koppler str":                  [3],
    "linder str":                   [3],
    "muhlstr":                      [3],
    "rehdorfer weg":                [3],
    "schwabacher str":              [3, 16, 17],
    "schwalbenstr":                 [3],
    "volkhardtstr":                 [3],
    "wehrstr":                      [3],
    "weinzierleiner str":           [3],
    "wintersdorfer str":            [3],
    # SBZ 4 (Gebiet 4)
    "albert-einstein-str":          [4],
    "bachwiesen":                   [4],
    "banderbacher str":             [4, 11, 15, 16],
    "gartenstr":                    [4],
    "hallstr":                      [4],
    "hauptstr":                     [4],
    "herrleinstr":                  [4],
    "jupiterweg":                   [4],
    "kirchenplatz":                 [4],
    "kirchenweg":                   [4],
    "kleinstr":                     [4],
    "koppenplatz":                  [4],
    # SBZ 5 (Gebiet 5)
    "angerzeile":                   [5],
    "austr":                        [5],
    "bachstr":                      [5],
    "baustr":                       [5],
    "bibertstr":                    [5],
    "bogenstr":                     [5],
    "brucknerstr":                  [5],
    "finkenstr":                    [5],
    "further str":                  [5, 6, 7, 8],
    "karlstr":                      [5],
    "marktplatz":                   [5],
    "max-planck-str":               [5],
    "merkurweg":                    [5],
    "mondstr":                      [5],
    "pfarrhof":                     [5],
    "rathausplatz":                 [5],
    "rotestr":                      [5],
    "saturnweg":                    [5],
    "schillerstr":                  [5],
    "schulstr":                     [5],
    "spitalstr":                    [5],
    "sternstr":                     [5],
    "vogelherdstr":                 [5],
    "ziegelstr":                    [5],
    # SBZ 6 (Gebiet 7)
    "alte veste":                   [6],
    "altfeldstr":                   [6],
    "bernhard-von-weimar-str":      [6],
    "eichenwaldstr":                [6],
    "florian-geyer-str":            [6],
    "franz-schubert-str":           [6],
    # SBZ 7 (Gebiet 8)
    "anton-emmerling-str":          [7],
    "bergstr":                      [7],
    "eichendorffstr":               [7],
    "grenzstr":                     [7],
    "gustav-adolf-str":             [7],
    "hans-sachs-str":               [7],
    "kreutleinstr":                 [7],
    "robert-koch-str":              [7],
    "sonnenstr":                    [7],
    "steinweg":                     [7, 8],
    "tillystr":                     [7],
    # SBZ 8 (Gebiet 9)
    "beethovenstr":                 [8],
    "freyjastr":                    [8, 9],
    "frobelstr":                    [8],
    "goethestr":                    [8],
    "gudrunstr":                    [8],
    "guntherstr":                   [8],
    "hauckstr":                     [8],
    "hagenstr":                     [8],
    "hermann-lons-str":             [8],
    "hinterm bahnhof":              [8],
    "homburger str":                [8],
    "kriemhildstr":                 [8],
    "lessingstr":                   [8],
    "lohengrinstr":                 [8],
    "lohest":                       [8],
    "mozartstr":                    [8],
    "nibelungenplatz":              [8],
    "nibelungenstr":                [8],
    "parsifalstr":                  [8],
    "pestalozzistr":                [8],
    "rheingoldstr":                 [8],
    "saarbruckener str":            [8],
    "saarlandstr":                  [8],
    "sauerbruchstr":                [8],
    "siegfriedstr":                 [8],
    "tannhauserstr":                [8],
    "uhlandstr":                    [8],
    "veit-stoss-str":               [8],
    "vestnerstr":                   [8],
    "virchowstr":                   [8],
    "wodanstr":                     [8],
    # SBZ 9 (Gebiet 10)
    "am achterplatzchen":           [9],
    "breslauer str":                [9],
    "danziger str":                 [9],
    "karlsbader str":               [9],
    "kneippallee":                  [9],
    "leonh -fortsch-str":           [9],
    "lichtenstadter str":           [9],
    "marie-juchacz-str":            [9, 10],
    "marienbader str":              [9],
    "sudetenstr":                   [9],
    # SBZ 10 (Gebiet 11)
    "an der weinleithe":            [10],
    "burgfarrnbacher str":          [10],
    "k -rat-zimmermann-str":        [10],
    "karl-vogler-str":              [10],
    "kolberger str":                [10],
    "richard-wagner-str":           [10],
    # SBZ 11 (Gebiet 12)
    "am grasweg":                   [11],
    "bourganeufer str":             [11],
    "feldstr":                      [11],
    "flurstr":                      [11],
    "freiheitstr":                  [11],
    "hasenstr":                     [11],
    "hochstr":                      [11],
    "kolpingweg":                   [11],
    "kornstr":                      [11],
    "martin-loos-str":              [11],
    "schwabengartenstr":            [11],
    "siedlerstr":                   [11],
    "wernher-von-braun-weg":        [11],
    # SBZ 12 (Gebiet 13)
    "ammerndorfer str":             [12],
    "amperestr":                    [12],
    "cadolzburger str":             [12],
    "egersdorfer str":              [12],
    "friedenstr":                   [12],
    "geisleithenstr":               [12],
    "grosshabersdorfer str":        [12],
    "hertzstr":                     [12],
    "langenzenner str":             [12],
    "ohmstr":                       [12],
    "siegelsdorfer str":            [12],
    # SBZ 13 (Gebiet 14)
    "ackerstr":                     [13],
    "am hugel":                     [13],
    "am schreiberholz":             [13],
    "am steinbruch":                [13],
    "am weizenfeld":                [13],
    "dinkelweg":                    [13],
    "friedrich-konig-weg":          [13],
    "gerstenweg":                   [13],
    "haferweg":                     [13],
    "hopfenweg":                    [13],
    "maisweg":                      [13],
    "rainweg":                      [13],
    "rapsweg":                      [13],
    "roggenweg":                    [13],
    "schreiberstr":                 [13],
    "sonnenhalde":                  [13],
    "steinbacher str":              [13],
    "talblick":                     [13],
    "voltastr":                     [13],
    "wachendorfer str":             [13],
    "wattstr":                      [13],
    "wilhelm-tell-platz":           [13],
    "zeisigstr":                    [13],
    # SBZ 14 (Gebiet 15)
    "gutenbergstr":                 [14, 15],
    "hegelstr":                     [14],
    "humboldtstr":                  [14],
    "joh -gottlieb-fichte-weg":     [14],
    "kantstr":                      [14],
    "leibnizweg":                   [14],
    "maximilianstr":                [14],
    "schwedenstr":                  [14],
    "sperlingstr":                  [14],
    "weiherhofer hauptstr":         [14, 15],
    "wielandstr":                   [14],
    # SBZ 15 (Gebiet 16)
    "dorfplatz":                    [15],
    "eckstr":                       [15],
    "eibenstr":                     [15],
    "fruhlingstr":                  [15],
    "haselnussweg":                 [15],
    "heideweg":                     [15],
    "herbststr":                    [15],
    "holzstr":                      [15],
    "marzenweg":                    [15],
    "schleifweg":                   [15],
    "schwanenweg":                  [15],
    "steilstr":                     [15],
    "tannenweg":                    [15],
    "weiherstr":                    [15],
    "zedernstr":                    [15],
    # SBZ 16 (Gebiet 17)
    "adlerstr":                     [16],
    "am brunnfeld":                 [16],
    "am kuhtrieb":                  [16],
    "brunnenweg":                   [16],
    "bussardweg":                   [16],
    "grundstr":                     [16],
    "hubertusstr":                  [16],
    "im stillen winkel":            [16],
    "im tal":                       [16],
    "landweg":                      [16],
    "leichendorfer str":            [16],
    "ortsstr":                      [16],
    "pleikershofer str":            [16],
    "quellenstr":                   [16],
    "rebhuhnweg":                   [16],
    "schimmelweg":                  [16],
    "waldstr":                      [16],
    "wolfengasse":                  [16],
    # SBZ 17 (Gebiet 18)
    "ahornstr":                     [17],
    "birkenstr":                    [17],
    "buchenstr":                    [17],
    "buchleiner str":               [17],
    "drosselstr":                   [17],
    "erlenstr":                     [17],
    "faber-castell-str":            [17],
    "falkenstr":                    [17],
    "fichtenstr":                   [17],
    "habichtweg":                   [17],
    "jasminstr":                    [17],
    "kiefernweg":                   [17],
    "kleiberstr":                   [17],
    "kranichweg":                   [17],
    "langgruner str":               [17],
    "lindenstr":                    [17],
    "meisenstr":                    [17],
    "narzissenstr":                 [17],
    "nelkenstr":                    [17],
    "oleanderstr":                  [17],
    "pfauenweg":                    [17],
    "rosenstr":                     [17],
    "spatzenweg":                   [17],
    "spechtstr":                    [17],
    "storchenweg":                  [17],
    "taubenweg":                    [17],
    "tulpenstr":                    [17],
    "ulmenstr":                     [17],
    "weitersdorfer str":            [17],
    "zum steig":                    [17],
    # SBZ 18 (Gebiet 19)
    "am geretsfeld":                [18],
    "asternweg":                    [18],
    "bienenweg":                    [18],
    "birkenhofweg":                 [18],
    "blutenweg":                    [18],
    "eichenstr":                    [18],
    "elsternweg":                   [18],
    "erlachstr":                    [18],
    "eschenstr":                    [18],
    "eulenweg":                     [18],
    "fohrenstr":                    [18],
    "ginsterweg":                   [18],
    "heilsbronner str":             [18],
    "holunderweg":                  [18],
    "hugelstr":                     [18],
    "jagerstr":                     [18],
    "kleestr":                      [18],
    "krokusweg":                    [18],
    "mohnstr":                      [18],
    "neuseser str":                 [18],
    "romerstr":                     [18],
    "rosstaler str":                [18],
    "rotdornstr":                   [18],
    "seeackerstr":                  [18],
    "sommerstr":                    [18],
    "sperberweg":                   [18],
    "traubenstr":                   [18],
    "uferstr":                      [18],
    "weinstr":                      [18],
    # SBZ 19 (Gebiet 21)
    "ansbacher str":                [19],
    "blumenstr":                    [19],
    "dahlienstr":                   [19],
    "frankenstr":                   [19],
    "kernstr":                      [19],
    "lilienstr":                    [19],
    "lupinenstr":                   [19],
    "markgrafenstr":                [19],
    "rangaustr":                    [19],
    "rankenstr":                    [19],
    "robert-bosch-str":             [19],
    "seewaldstr":                   [19],
    "winkelstr":                    [19],
    # SBZ 20 (Gebiet 22)
    "bertolt-brecht-weg":           [20],
    "bronnamberger weg":            [20],
    "clara-viebig-weg":             [20],
    "erich-kastner-weg":            [20],
    "franz-kafka-weg":              [20],
    "gerhart-hauptmann-str":        [20],
    "heinrich-boll-str":            [20],
    "hermann-hesse-weg":            [20],
    "im pinderpark":                [20],
    "jakob-wassermann-str":         [20],
    "luise-rinser-str":             [20],
    "thomas-mann-str":              [20],
}

# ── Straße → Stimmbezirke 2020 (Straßenverzeichnis Stand 2018) ────────────────
STREET_TO_BZ_2020 = {
    # SBZ 1
    "albrecht-durer-str":           [1],
    "badstr":                       [1],
    "frauenschlagerstr":            [1],
    "heinestr":                     [1],
    "hirtenackerstr":               [1],
    "im bibertgrund":               [1],
    "jordanstr":                    [1],
    "neptunstr":                    [1],
    "nurnberger str":               [1, 6],
    "oberasbacher str":             [1],
    "osterreicher str":             [1],
    "ostmarkstr":                   [1],
    "plauener str":                 [1],
    "rothenburger str":             [1, 23, 25],
    "sandackerstr":                 [1],
    "siebenburgener str":           [1],
    "zwickauer str":                [1],
    # SBZ 2
    "am sportplatz":                [2],
    "carl-diem-str":                [2],
    "donauschwabenweg":             [2],
    "eichenhain":                   [2],
    "fasanenweg":                   [2],
    "felsenstr":                    [2],
    "fliederstr":                   [2],
    "fuggerstr":                    [2],
    "grillenbergerstr":             [2],
    "heimgartenstr":                [2],
    "jahnstr":                      [2],
    "lerchenstr":                   [2],
    "parkstr":                      [2],
    "rudolf-harbig-str":            [2],
    "turnstr":                      [2],
    "wallensteinstr":               [2],
    "walter-gropius-weg":           [2],
    "weidachstr":                   [2],
    "weinbergstr":                  [2],
    # SBZ 3
    "am amselschlag":               [3],
    "am hammerstattchen":           [3],
    "am muhlenpark":                [3],
    "anwandener str":               [3],
    "buchackerstr":                 [3],
    "fischerweg":                   [3],
    "koppler str":                  [3],
    "linder str":                   [3],
    "muhlstr":                      [3],
    "rehdorfer weg":                [3],
    "schwalbenstr":                 [3],
    "volkhardtstr":                 [3],
    "wehrstr":                      [3],
    "weinzierleiner str":           [3],
    "wintersdorfer str":            [3],
    # SBZ 4
    "albert-einstein-str":          [4],
    "am grasweg":                   [4],
    "banderbacher str":             [4, 5, 16, 18],
    "feldstr":                      [4],
    "geisleithenstr":               [4, 5],
    "jupiterweg":                   [4],
    "mondstr":                      [4, 5],
    "saturnweg":                    [4],
    "schwabacher str":              [4, 19, 20, 24],
    "vogelherdstr":                 [4],
    "wernher-von-braun-weg":        [4],
    # SBZ 5
    "gartenstr":                    [5],
    "hallstr":                      [5],
    "hauptstr":                     [5],
    "herrleinstr":                  [5],
    "hinterm bahnhof":              [5],
    "karl-vogler-str":              [5],
    "kirchenplatz":                 [5],
    "kirchenweg":                   [5],
    "kleinstr":                     [5],
    "koppenplatz":                  [5],
    "marktplatz":                   [5],
    "max-planck-str":               [5],
    "merkurweg":                    [5],
    "nibelungenplatz":              [5],
    "nibelungenstr":                [5],
    "rathausplatz":                 [5],
    "rotestr":                      [5],
    "schillerstr":                  [5],
    "schulstr":                     [5],
    "schutzenstr":                  [5, 6],
    "sternstr":                     [5],
    "spitalstr":                    [5],
    "steinweg":                     [5, 7],
    "ziegelstr":                    [5],
    # SBZ 6
    "angerzeile":                   [6],
    "austr":                        [6],
    "bachstr":                      [5, 6],
    "bahnhofstr":                   [6, 7],
    "baustr":                       [6],
    "bibertstr":                    [6],
    "bogenstr":                     [6],
    "brucknerstr":                  [6],
    "finkenstr":                    [6],
    "karlstr":                      [6],
    "klampferstr":                  [6],
    "kolbstr":                      [6],
    "kraftstr":                     [6],
    "olstr":                        [6],
    "querstr":                      [6],
    "sandstr":                      [6],
    "wiesenstr":                    [6],
    # SBZ 7
    "alte veste":                   [7],
    "altfeldstr":                   [7],
    "bernhard-von-weimar-str":      [7],
    "burgfarrnbacher str":          [7, 12],
    "eichenwaldstr":                [7],
    "florian-geyer-str":            [7],
    "franz-schubert-str":           [7],
    "further str":                  [5, 7, 8, 9],
    "grenzstr":                     [7],
    "gustav-adolf-str":             [7],
    "hans-sachs-str":               [7],
    "kreutleinstr":                 [7],
    "pfarrhof":                     [7],
    "robert-koch-str":              [7],
    "sonnenstr":                    [7],
    "sparkassenstr":                [7],
    "tillystr":                     [7],
    # SBZ 8
    "anton-emmerling-str":          [8],
    "bergstr":                      [8],
    "eichendorffstr":               [8],
    "goethestr":                    [8],
    "hauckstr":                     [8],
    "hermann-lons-str":             [8],
    "homburger str":                [8],
    "lessingstr":                   [8],
    "mozartstr":                    [8],
    "pestalozzistr":                [8],
    "saarbruckener str":            [8],
    "saarlandstr":                  [8],
    "uhlandstr":                    [8],
    "veit-stoss-str":               [8],
    # SBZ 9
    "beethovenstr":                 [9],
    "freyjastr":                    [9, 11],
    "frobelstr":                    [9],
    "gudrunstr":                    [9],
    "guntherstr":                   [9],
    "hagenstr":                     [9],
    "kriemhildstr":                 [9],
    "lohestr":                      [9],
    "lohengrinstr":                 [9],
    "parsifalstr":                  [9],
    "rheingoldstr":                 [9],
    "sauerbruchstr":                [9],
    "siegfriedstr":                 [9],
    "tannhauserstr":                [9],
    "vestnerstr":                   [9],
    "virchowstr":                   [9],
    "wodanstr":                     [9],
    # SBZ 10
    "am achterplatzchen":           [10],
    "k -rat-zimmermann-str":        [10, 12],
    "kneippallee":                  [10],
    "leonh -fortsch-str":           [10],
    "marienbader str":              [10],
    # SBZ 11
    "breslauer str":                [11],
    "danziger str":                 [11],
    "karlsbader str":               [11],
    "lichtenstadter str":           [11],
    "richard-wagner-str":           [11],
    "sudetenstr":                   [11],
    # SBZ 12
    "an der weinleithe":            [12],
    "marie-juchacz-str":            [12],
    "weiherhofer weg":              [12],
    # SBZ 13
    "bourganeufer str":             [13],
    "flurstr":                      [13],
    "freiheitstr":                  [13],
    "hasenstr":                     [13],
    "hochstr":                      [13],
    "kolberger str":                [13],
    "kolpingweg":                   [13],
    "kornstr":                      [13],
    "martin-loos-str":              [13],
    "schwabengartenstr":            [13],
    "siedlerstr":                   [13],
    # SBZ 14
    "ammerndorfer str":             [14],
    "amperestr":                    [14],
    "cadolzburger str":             [14],
    "egersdorfer str":              [14],
    "friedenstr":                   [14],
    "grosshabersdorfer str":        [14],
    "hertzstr":                     [14],
    "langenzenner str":             [14],
    "ohmstr":                       [14],
    "siegelsdorfer str":            [14],
    "steinbacher str":              [14],
    "voltastr":                     [14],
    "wachendorfer str":             [14],
    "wattstr":                      [14],
    # SBZ 15
    "gutenbergstr":                 [15, 16],
    "hegelstr":                     [15],
    "humboldtstr":                  [15],
    "joh -gottlieb-fichte-weg":     [15],
    "kantstr":                      [15],
    "leibnizweg":                   [15],
    "maximilianstr":                [15],
    "paul-metz-str":                [15],
    "schwedenstr":                  [15],
    "sperlingstr":                  [15],
    "weiherhofer hauptstr":         [15, 16],
    "wielandstr":                   [15],
    # SBZ 16
    "dorfplatz":                    [16],
    "eckstr":                       [16],
    "eibenstr":                     [16],
    "fruhlingstr":                  [16],
    "haselnussweg":                 [16],
    "heideweg":                     [16],
    "herbststr":                    [16],
    "holzstr":                      [16],
    "marzenweg":                    [16],
    "schleifweg":                   [16],
    "schwanenweg":                  [16],
    "steilstr":                     [16],
    "tannenweg":                    [16],
    "weiherstr":                    [16],
    "zedernstr":                    [16],
    # SBZ 17
    "ackerstr":                     [17],
    "am hugel":                     [17],
    "am schreiberholz":             [17],
    "am steinbruch":                [17],
    "am weizenfeld":                [17],
    "dinkelweg":                    [17],
    "friedrich-konig-weg":          [17],
    "gerstenweg":                   [17],
    "haferweg":                     [17],
    "hopfenweg":                    [17],
    "maisweg":                      [17],
    "rainweg":                      [17],
    "rapsweg":                      [17],
    "roggenweg":                    [17],
    "schreiberstr":                 [17],
    "sonnenhalde":                  [17],
    "talblick":                     [17],
    "wilhelm-tell-platz":           [17],
    "zeisigstr":                    [17],
    # SBZ 18
    "adlerstr":                     [18],
    "am brunnfeld":                 [18],
    "am kuhtrieb":                  [18],
    "brunnenweg":                   [18],
    "bussardweg":                   [18],
    "hubertusstr":                  [18],
    "im stillen winkel":            [18],
    "im tal":                       [18],
    "leichendorfer str":            [18],
    "pleikershofer str":            [18],
    "quellenstr":                   [18],
    "rebhuhnweg":                   [18],
    "schimmelweg":                  [18],
    "wolfengasse":                  [18],
    # SBZ 19
    "ahornstr":                     [19],
    "birkenstr":                    [19],
    "buchenstr":                    [19],
    "erlenstr":                     [19],
    "fichtenstr":                   [19],
    "jasminstr":                    [19],
    "kiefernweg":                   [19],
    "lindenstr":                    [19],
    "narzissenstr":                 [19],
    "nelkenstr":                    [19],
    "oleanderstr":                  [19],
    "rosenstr":                     [19],
    "tulpenstr":                    [19],
    "ulmenstr":                     [19],
    # SBZ 20
    "buchleiner str":               [20],
    "drosselstr":                   [20],
    "faber-castell-str":            [20],
    "falkenstr":                    [20],
    "habichtweg":                   [20],
    "kleiberstr":                   [20],
    "kranichweg":                   [20],
    "langgruner str":               [20],
    "meisenstr":                    [20],
    "pfauenweg":                    [20],
    "spatzenweg":                   [20],
    "spechtstr":                    [20],
    "storchenweg":                  [20],
    "taubenweg":                    [20],
    "weitersdorfer str":            [20],
    "zum steig":                    [20],
    # SBZ 21
    "am geretsfeld":                [21],
    "birkenhofweg":                 [21],
    "blutenweg":                    [21],
    "bronnamberger weg":            [21],
    "eichenstr":                    [21],
    "eschenstr":                    [21],
    "ginsterweg":                   [21],
    "holunderweg":                  [21],
    "hugelstr":                     [21],
    "jagerstr":                     [21],
    "kleestr":                      [21],
    "mohnstr":                      [21],
    "romerstr":                     [21],
    "rotdornstr":                   [21],
    "seeackerstr":                  [21],
    "sommerstr":                    [21],
    "weinstr":                      [21],
    # SBZ 22
    "bienenweg":                    [22],
    "elsternweg":                   [22],
    "erlachstr":                    [22],
    "eulenweg":                     [22],
    "fohrenstr":                    [22],
    "heilsbronner str":             [22],
    "neuseser str":                 [22],
    "sperberweg":                   [22],
    "traubenstr":                   [22],
    "uferstr":                      [22],
    # SBZ 23
    "am steinacker":                [23],
    "blumenstr":                    [23],
    "dahlienstr":                   [23],
    "krokusweg":                    [23],
    "lilienstr":                    [23],
    "rankenstr":                    [23],
    "rosstaler str":                [23],
    # SBZ 24
    "ansbacher str":                [24],
    "brandstatterstr":              [24],
    "carl-benz-str":                [24],
    "frankenstr":                   [24],
    "grundstr":                     [24],
    "kernstr":                      [24],
    "landweg":                      [24],
    "lupinenstr":                   [24],
    "markgrafenstr":                [24],
    "ortsstr":                      [24],
    "rangaustr":                    [24],
    "robert-bosch-str":             [24],
    "rudolf-diesel-str":            [24],
    "seewaldstr":                   [24],
    "waldstr":                      [24],
    "winkelstr":                    [24],
    # SBZ 25 (Weinzierlein-Außenbereich; kein B20-Eintrag)
    "bertolt-brecht-weg":           [25],
    "clara-viebig-weg":             [25],
    "erich-kastner-weg":            [25],
    "franz-kafka-weg":              [25],
    "gerhart-hauptmann-str":        [25],
    "heinrich-boll-str":            [25],
    "hermann-hesse-weg":            [25],
    "im pinderpark":                [25],
    "jakob-wassermann-str":         [25],
    "luise-rinser-str":             [25],
    "thomas-mann-str":              [25],
}


def norm(name: str) -> str:
    s = name.lower().strip()
    # Expand full german words
    s = s.replace("straße", "str").replace("strasse", "str")
    s = s.replace("platz", "platz")
    # Remove umlauts for matching
    for a, b in [("ä","a"),("ö","o"),("ü","u"),("ß","ss"),
                 ("Ä","a"),("Ö","o"),("Ü","u")]:
        s = s.replace(a, b)
    # Collapse punctuation/dots but keep hyphens
    import re
    s = re.sub(r'[^\w\s-]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def fetch_ways() -> list:
    print("Lade Straßen-Geometrien …", flush=True)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cache_path = os.path.join(script_dir, "zirndorf_ways_cache.json")

    # Use local cache if present (only Zirndorf streets via area filter)
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            j = json.load(f)
        print(f"  {len(j['elements'])} Wege aus Cache ({os.path.basename(cache_path)})")
        return j["elements"]

    # Fetch from Overpass: area filter → only Zirndorf
    q_area = '[out:json][timeout:60];area["admin_level"="8"]["name"="Zirndorf"]->.z;(way["highway"]["name"](area.z););out geom qt;'
    q_bbox = f'[out:json][timeout:60];(way["highway"]["name"]({BBOX}););out geom qt;'
    for attempt, (q, label) in enumerate([(q_area,"Area"),(q_area,"Area"),(q_bbox,"Bbox")]):
        try:
            r = requests.get("https://overpass-api.de/api/interpreter",
                             params={"data": q}, timeout=65)
            r.raise_for_status()
            j = r.json()
            if j["elements"]:
                print(f"  {len(j['elements'])} Wege ({label})")
                # Cache the result
                with open(cache_path, "w") as f:
                    json.dump(j, f)
                return j["elements"]
        except Exception as e:
            print(f"  Versuch {attempt+1} ({label}) fehlgeschlagen: {e}", file=sys.stderr)
            time.sleep(3)
    raise RuntimeError("Overpass nicht erreichbar")


def load_municipality_boundary(path: str):
    """Load Zirndorf GeoJSON outline."""
    with open(path) as f:
        gj = json.load(f)
    geoms = []
    for feat in gj.get("features", [gj]):
        g = feat.get("geometry") if "geometry" in feat else feat
        if g:
            geoms.append(shape(g))
    return unary_union(geoms) if geoms else None


def build_street_buffer_polygons(bz_ways: dict, municipality=None,
                                  buffer_deg: float = 0.004) -> dict:
    """
    Straßen-Puffer-Ansatz: Jeder Bezirk bekommt genau die Fläche,
    die innerhalb `buffer_deg` seiner zugewiesenen Straßen liegt.
    Kein Voronoi, kein Lückenfüllen — ehrliche Darstellung.
    buffer_deg ≈ 0.004° ≈ 400 m
    """
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    muni_valid = make_valid(municipality) if municipality else None
    result = {}

    for bz_nr, ways in bz_ways.items():
        lines = []
        for w in ways:
            pts = [(n["lon"], n["lat"]) for n in w.get("geometry", []) if "lon" in n]
            if len(pts) >= 2:
                lines.append(LineString(pts))
        if not lines:
            continue
        merged = unary_union(lines).buffer(buffer_deg)
        merged = make_valid(merged)
        if muni_valid:
            try:
                merged = merged.intersection(muni_valid)
            except Exception:
                merged = merged.intersection(muni_valid.buffer(0))
        if merged.is_empty:
            continue
        merged = merged.simplify(0.0005, preserve_topology=True)
        result[bz_nr] = merged

    # Remove overlaps: later districts subtract from earlier ones
    # (streets shared between districts keep the first assignment)
    assigned = None
    cleaned = {}
    for bz_nr in sorted(result.keys()):
        poly = result[bz_nr]
        if assigned is not None:
            try:
                poly = poly.difference(assigned)
            except Exception:
                poly = poly.difference(assigned.buffer(0))
        if not poly.is_empty:
            cleaned[bz_nr] = make_valid(poly)
            assigned = unary_union([assigned, result[bz_nr]]) if assigned else result[bz_nr]

    return cleaned


def build_voronoi_by_district(bz_centroids: dict, municipality=None) -> dict:
    """
    Voronoi-basierte Bezirkspolygone auf Basis von Weg-Mittelpunkten (1 Punkt/Weg).
    Keine dichten Straßenpunkt-Wolken → keine Rillen/Spikes.
    """
    from shapely.ops import voronoi_diagram, unary_union
    from shapely.validation import make_valid
    from shapely.geometry import MultiPoint, GeometryCollection, Point

    # bz_centroids: dict[bz_nr → list of (lon, lat) centroids]
    all_pts = []
    for bz_nr, pts in bz_centroids.items():
        for pt in pts:
            all_pts.append((pt[0], pt[1], bz_nr))

    print(f"  {len(all_pts)} Punkte total für Voronoi …", flush=True)

    coords = [(p[0], p[1]) for p in all_pts]
    mp = MultiPoint(coords)

    # Compute voronoi regions, clipped to a bbox envelope
    if municipality:
        envelope = municipality.envelope.buffer(0.01)
    else:
        from shapely.geometry import box
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        envelope = box(min(xs)-0.01, min(ys)-0.01, max(xs)+0.01, max(ys)+0.01)

    regions = voronoi_diagram(mp, envelope=envelope)

    # For each Voronoi region, find which input point is inside (or nearest)
    # Build spatial index: list of (point, bz_nr)
    point_objs = [(Point(p[0], p[1]), p[2]) for p in all_pts]

    # Assign each Voronoi region to a district
    district_geoms: dict[int, list] = {nr: [] for nr in bz_centroids.keys()}

    for region in regions.geoms:
        # Find which input point lies in this region
        # Use centroid of region to find nearest point quickly
        centroid = region.centroid
        best_nr = None
        best_dist = float('inf')
        for pt, bz_nr in point_objs:
            d = centroid.distance(pt)
            if d < best_dist:
                best_dist = d
                best_nr = bz_nr
        if best_nr is not None:
            district_geoms[best_nr].append(region)

    print(f"  Voronoi-Zellen zugeordnet, vereinige Bezirke …", flush=True)

    muni_valid = make_valid(municipality) if municipality else None

    result = {}
    for bz_nr, geoms in district_geoms.items():
        if not geoms:
            continue
        merged = unary_union(geoms)
        merged = make_valid(merged)
        if muni_valid:
            try:
                merged = merged.intersection(muni_valid)
            except Exception:
                merged = merged.intersection(muni_valid.buffer(0))
        if merged.is_empty:
            continue
        # Simplify to remove Voronoi jaggedness (≈50 m tolerance)
        merged = merged.simplify(0.0005, preserve_topology=True)
        result[bz_nr] = merged

    return result


def build_way_centroids(bz_ways: dict) -> dict:
    """Reduziere Straßengeometrien auf 1 repräsentativen Punkt je Weg."""
    centroids: dict[int, list] = defaultdict(list)
    for bz_nr, ways in bz_ways.items():
        for way in ways:
            pts = [(n["lon"], n["lat"]) for n in way.get("geometry", []) if "lon" in n]
            if len(pts) < 2:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            centroids[bz_nr].append((sum(xs) / len(xs), sum(ys) / len(ys)))
    return centroids


def smooth_district_polygons(polys: dict, municipality=None,
                             smooth_outer: float = 0.0012,
                             smooth_inner: float = 0.0010,
                             simplify_tol: float = 0.0010,
                             min_part_ratio: float = 0.08,
                             min_part_area: float = 0.00002) -> dict:
    """
    Glättet Bezirksflächen deutlich und entfernt sehr kleine Teilflächen.
    Ziel: ruhige, lesbare Flächen ohne gezackte Innenstadt-Inseln.
    """
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    muni_valid = make_valid(municipality) if municipality else None
    cleaned = {}

    for bz_nr, geom in polys.items():
        geom = make_valid(geom)
        if geom.is_empty:
            continue

        # Morphological open/close smooths Voronoi spikes without fully
        # erasing the district footprint.
        geom = geom.buffer(smooth_outer).buffer(-smooth_inner)
        geom = make_valid(geom).simplify(simplify_tol, preserve_topology=True)

        parts = []
        if isinstance(geom, Polygon):
            parts = [geom]
        elif isinstance(geom, MultiPolygon):
            parts = list(geom.geoms)
        else:
            parts = [g for g in getattr(geom, "geoms", []) if g.geom_type in {"Polygon", "MultiPolygon"}]
            flat = []
            for g in parts:
                if g.geom_type == "Polygon":
                    flat.append(g)
                elif g.geom_type == "MultiPolygon":
                    flat.extend(list(g.geoms))
            parts = flat

        if not parts:
            continue

        total_area = sum(p.area for p in parts)
        kept = [p for p in parts if p.area >= min_part_area and p.area >= total_area * min_part_ratio]
        if not kept:
            kept = [max(parts, key=lambda p: p.area)]

        merged = unary_union(kept)
        merged = make_valid(merged)

        if muni_valid:
            try:
                merged = merged.intersection(muni_valid)
            except Exception:
                merged = merged.intersection(muni_valid.buffer(0))

        if merged.is_empty:
            continue

        cleaned[bz_nr] = make_valid(merged)

    return cleaned


# B26 manual centers for a calm, stylized reading map.
# These are intentionally spread a bit more than the raw polling locations,
# especially in the dense city center.
B26_MANUAL_CENTERS = {
    1:  (10.9589, 49.4387),
    2:  (10.9616, 49.4426),
    3:  (10.9565, 49.4396),
    4:  (10.9578, 49.4410),
    5:  (10.9601, 49.4410),
    6:  (10.9589, 49.4434),
    7:  (10.9572, 49.4445),
    8:  (10.9608, 49.4452),
    9:  (10.9515, 49.4438),
    10: (10.9541, 49.4416),
    11: (10.9468, 49.4472),
    12: (10.9453, 49.4458),
    13: (10.9280, 49.4546),
    14: (10.9237, 49.4568),
    15: (10.9205, 49.4587),
    16: (10.9098, 49.4390),
    17: (10.9252, 49.4239),
    18: (10.8972, 49.4247),
    19: (10.9125, 49.4294),
    20: (10.9444, 49.4420),
}


# B20 district centers (lon, lat) for 2020 coordinate-based Voronoi
B20_CENTERS = {
    1:  (10.95650, 49.43870),
    2:  (10.96110, 49.44310),
    3:  (10.95780, 49.43960),
    4:  (10.95753, 49.44124),
    5:  (10.96190, 49.44380),
    6:  (10.96050, 49.44200),
    7:  (10.95880, 49.44430),
    8:  (10.95980, 49.44520),
    9:  (10.96080, 49.44610),
    10: (10.95700, 49.44480),
    11: (10.95830, 49.44350),
    12: (10.94720, 49.44710),
    13: (10.94570, 49.44590),
    14: (10.92678, 49.45364),
    15: (10.92280, 49.45771),
    16: (10.92175, 49.45812),
    17: (10.90978, 49.43938),
    18: (10.92637, 49.42348),
    19: (10.93001, 49.41065),
    20: (10.89640, 49.42380),
    21: (10.89770, 49.42520),
    22: (10.91200, 49.43010),
    23: (10.91350, 49.42870),
    24: (10.94790, 49.43900),
}


def build_voronoi_from_centers(centers: dict, municipality=None) -> dict:
    """Voronoi auf Bezirkszentren — für 2020 ohne Straßenzuordnung."""
    from shapely.ops import voronoi_diagram, unary_union
    from shapely.validation import make_valid
    from shapely.geometry import MultiPoint, Point

    coords = list(centers.values())  # (lon, lat)
    mp = MultiPoint(coords)

    if municipality:
        envelope = municipality.envelope.buffer(0.02)
    else:
        from shapely.geometry import box
        xs, ys = zip(*coords)
        envelope = box(min(xs)-0.02, min(ys)-0.02, max(xs)+0.02, max(ys)+0.02)

    regions = voronoi_diagram(mp, envelope=envelope)
    nr_list = list(centers.keys())
    point_objs = [(Point(lon, lat), nr) for nr, (lon, lat) in centers.items()]

    muni_valid = make_valid(municipality) if municipality else None
    result = {}
    for region in regions.geoms:
        centroid = region.centroid
        best_nr = min(point_objs, key=lambda p: centroid.distance(p[0]))[1]
        merged = make_valid(region)
        if muni_valid:
            try:
                merged = merged.intersection(muni_valid)
            except Exception:
                merged = merged.intersection(muni_valid.buffer(0))
        if merged.is_empty:
            continue
        merged = merged.simplify(0.0005, preserve_topology=True)
        result[best_nr] = merged

    return result


def keep_largest_part(geom):
    """Return the largest polygon part for a calm, stylized district footprint."""
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.validation import make_valid

    geom = make_valid(geom)
    if geom.is_empty:
        return geom
    if isinstance(geom, Polygon):
        return geom
    if isinstance(geom, MultiPolygon):
        return max(geom.geoms, key=lambda p: p.area)

    parts = []
    for g in getattr(geom, "geoms", []):
        if g.geom_type == "Polygon":
            parts.append(g)
        elif g.geom_type == "MultiPolygon":
            parts.extend(list(g.geoms))
    return max(parts, key=lambda p: p.area) if parts else geom


def build_stylized_manual_polygons(centers: dict, municipality=None) -> dict:
    """
    Build a calm, editable baseline for a manually curated district map.
    The output is intentionally stylized and should be preferred for display.
    """
    from shapely.validation import make_valid

    polys = build_voronoi_from_centers(centers, municipality)
    stylized = {}
    for bz_nr, geom in polys.items():
        geom = keep_largest_part(geom)
        geom = geom.buffer(0.0018).buffer(-0.0015)
        geom = make_valid(geom).simplify(0.0024, preserve_topology=True)
        if municipality:
            muni_valid = make_valid(municipality)
            try:
                geom = geom.intersection(muni_valid)
            except Exception:
                geom = geom.intersection(muni_valid.buffer(0))
        geom = keep_largest_part(geom)
        if not geom.is_empty:
            stylized[bz_nr] = make_valid(geom)
    return stylized


def build_municipality_boundary(ways: list) -> object:
    """
    Berechnet eine glatte Gemeindegrenze aus allen Straßengeometrien:
    - Morphologisches Schließen (buffer+ dann buffer-) füllt Lücken
    - simplify glättet den Rand
    """
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from shapely.validation import make_valid

    lines = []
    for w in ways:
        pts = [(n["lon"], n["lat"]) for n in w.get("geometry", []) if "lon" in n]
        if len(pts) >= 2:
            lines.append(LineString(pts))
    if not lines:
        return None

    # Buffer all streets → merge → erode back (morphological close)
    road_union = unary_union(lines)
    boundary = road_union.buffer(0.008)   # ~900 m Puffer nach außen
    boundary = boundary.buffer(-0.005)    # ~550 m Erosion → schließt Lücken, glättet
    boundary = boundary.simplify(0.002, preserve_topology=True)
    return make_valid(boundary)


def export_streets_geojson(bz_ways: dict, out_path: str):
    """Export matched streets as colored LineString GeoJSON for direct map display."""
    features = []
    seen = set()  # avoid duplicate ways
    for bz_nr in sorted(bz_ways.keys()):
        for way in bz_ways[bz_nr]:
            way_id = way.get("id")
            key = (way_id, bz_nr)
            if key in seen:
                continue
            seen.add(key)
            pts = [(n["lon"], n["lat"]) for n in way.get("geometry", []) if "lon" in n]
            if len(pts) < 2:
                continue
            features.append({
                "type": "Feature",
                "properties": {
                    "nr": bz_nr,
                    "name": way.get("tags", {}).get("name", "")
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": pts
                }
            })
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ {len(features)} Straßen-Features → {out_path}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    muni_path  = os.path.join(script_dir, "../docs/analyse/zirndorf.geojson")
    out_path   = os.path.join(script_dir, "../docs/analyse/bezirk_polygons.geojson")
    out20_path = os.path.join(script_dir, "../docs/analyse/bezirk_polygons_2020.geojson")
    manual26_path = os.path.join(script_dir, "../docs/analyse/bezirk_polygons_2026_manual.geojson")

    municipality = None
    if os.path.exists(muni_path):
        municipality = load_municipality_boundary(muni_path)
        print(f"Gemeindegrenze geladen: {muni_path}")

    ways = fetch_ways()

    # Map ways → Stimmbezirke; collect full way objects per district
    bz_ways: dict[int, list] = defaultdict(list)
    matched = 0
    unmatched: set[str] = set()

    for way in ways:
        raw_name = way.get("tags", {}).get("name", "")
        if not raw_name:
            continue
        key = norm(raw_name)
        bezirke = STREET_TO_BZ.get(key)

        if not bezirke:
            for k, v in STREET_TO_BZ.items():
                if key == k or (key + "asse") == k or (k + "asse") == key:
                    bezirke = v
                    break

        if not bezirke:
            unmatched.add(raw_name)
            continue

        if not way.get("geometry"):
            continue

        matched += 1
        for bz_nr in bezirke:
            bz_ways[bz_nr].append(way)

    print(f"\nZugeordnet: {matched} Wege → {len(bz_ways)} Stimmbezirke")
    missing = set(range(1, 21)) - set(bz_ways.keys())
    if missing:
        print(f"Stimmbezirke ohne Geometrie: {sorted(missing)}")

    sample_unmatched = sorted(unmatched)[:20]
    if sample_unmatched:
        print(f"Nicht zugeordnet (Auswahl): {', '.join(sample_unmatched)}")

    # Build municipality boundary from all ways (morphological close → smooth)
    print("\nBerechne Gemeindegrenze …", flush=True)
    clip_boundary = build_municipality_boundary(ways)
    if clip_boundary:
        print(f"  Grenze: {clip_boundary.geom_type}, Bounds: {[round(x,4) for x in clip_boundary.bounds]}")
    else:
        clip_boundary = municipality

    # Build polygons from street centroids, then smooth and remove small islands.
    print("\nBerechne Bezirksflächen aus Straßen-Zentren …", flush=True)
    bz_centroids = build_way_centroids(bz_ways)
    district_polys = build_voronoi_by_district(bz_centroids, clip_boundary)
    print("Glätte Bezirksflächen und entferne kleine Ausreißer …", flush=True)
    district_polys = smooth_district_polygons(district_polys, clip_boundary)

    features = []
    for bz_nr in sorted(district_polys.keys()):
        poly = district_polys[bz_nr]
        print(f"  BZ {bz_nr:2d}: {poly.geom_type}")
        feat = {
            "type": "Feature",
            "properties": {"nr": bz_nr, "stimmbezirk": bz_nr},
            "geometry": mapping(poly)
        }
        features.append(feat)

    geojson = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n✓ {len(features)} Polygone → {out_path}")

    print("\nErzeuge stilisierte 2026-Karte …", flush=True)
    manual_polys = build_stylized_manual_polygons(B26_MANUAL_CENTERS, clip_boundary)
    manual_features = []
    for bz_nr in sorted(manual_polys.keys()):
        manual_features.append({
            "type": "Feature",
            "properties": {"nr": bz_nr, "stimmbezirk": bz_nr, "source": "manual-stylized"},
            "geometry": mapping(manual_polys[bz_nr])
        })
    with open(manual26_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": manual_features},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓ {len(manual_features)} stilisierte Polygone → {manual26_path}")

    # Export streets as colored lines (more accurate than polygons)
    streets_path = os.path.join(script_dir, "../docs/analyse/bezirk_streets.geojson")
    print("\nExportiere Straßen-GeoJSON …", flush=True)
    export_streets_geojson(bz_ways, streets_path)

    # ── 2020: Straßen-GeoJSON aus Straßenverzeichnis Stand 2018 ───────────────
    print("\nZuordnung 2020 (Straßenverzeichnis Stand 2018) …", flush=True)
    bz_ways_2020: dict[int, list] = defaultdict(list)
    matched20 = 0
    for way in ways:
        raw_name = way.get("tags", {}).get("name", "")
        if not raw_name:
            continue
        key = norm(raw_name)
        bezirke20 = STREET_TO_BZ_2020.get(key)
        if not bezirke20:
            continue
        if not way.get("geometry"):
            continue
        matched20 += 1
        for bz_nr in bezirke20:
            bz_ways_2020[bz_nr].append(way)

    print(f"  Zugeordnet: {matched20} Wege → {len(bz_ways_2020)} Stimmbezirke")
    streets20_path = os.path.join(script_dir, "../docs/analyse/bezirk_streets_2020.geojson")
    export_streets_geojson(bz_ways_2020, streets20_path)

    print("\nBerechne 2020-Bezirksflächen …", flush=True)
    district_polys_2020 = build_voronoi_from_centers(B20_CENTERS, clip_boundary)
    features20 = []
    for bz_nr in sorted(district_polys_2020.keys()):
        poly = district_polys_2020[bz_nr]
        features20.append({
            "type": "Feature",
            "properties": {"nr": bz_nr, "stimmbezirk": bz_nr},
            "geometry": mapping(poly)
        })

    with open(out20_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features20},
                  f, ensure_ascii=False, separators=(",", ":"))

    print(f"✓ {len(features20)} Polygone → {out20_path}")


if __name__ == "__main__":
    main()
