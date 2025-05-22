import requests
import mwparserfromhell
import os
import json
import time
import re
from collections import Counter

BASE_URL = "https://www.lexikon-betreuungsrecht.de/api.php"
OUTPUT_PATH = "artikel"
os.makedirs(OUTPUT_PATH, exist_ok=True)

STOPWORTE = set([
    "der", "die", "das", "und", "ein", "eine", "ist", "im", "in", "zu", "mit",
    "auf", "für", "von", "an", "als", "werden", "nicht", "auch", "oder", "des",
    "sich", "bei", "dass", "durch", "es", "am", "sind", "dem", "den"
])

def generiere_tags(text, max_tags=5):
    wörter = re.findall(r"\b[a-zäöüß]{4,}\b", text.lower())
    gefiltert = [wort for wort in wörter if wort not in STOPWORTE]
    häufigkeit = Counter(gefiltert)
    häufigste = häufigkeit.most_common(max_tags)
    return [wort for wort, _ in häufigste]

def get_all_titles():
    titles = []
    apcontinue = ""
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "format": "json",
            "aplimit": "max"
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        res = requests.get(BASE_URL, params=params)
        data = res.json()
        titles.extend([p["title"] for p in data["query"]["allpages"]])
        if "continue" in data:
            apcontinue = data["continue"]["apcontinue"]
            time.sleep(0.5)
        else:
            break
    return titles

def lade_wikitext(titel):
    res = requests.get(BASE_URL, params={
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "rvprop": "content",
        "titles": titel
    })
    data = res.json()
    pages = data["query"]["pages"]
    for page_id, page_data in pages.items():
        if "revisions" in page_data:
            rev = page_data["revisions"][0]
            if "*" in rev:
                return rev["*"]
            elif "slots" in rev:
                return rev["slots"]["main"]["*"]
    return ""

def extrahiere_links_und_inhalt(wikitext):
    wikicode = mwparserfromhell.parse(wikitext)
    verlinkte_artikel = []
    for link in wikicode.filter_wikilinks():
        ziel = str(link.title).strip()
        if "|" in ziel:
            anzeige, linkziel = ziel.split("|", 1)
        else:
            anzeige, linkziel = ziel, ziel
        link_md = f"[{anzeige}]({linkziel.lower().replace(' ', '-')})"
        wikicode.replace(link, link_md)
        verlinkte_artikel.append(linkziel.lower().replace(" ", "-"))
    return str(wikicode.strip_code()), list(set(verlinkte_artikel))

def strukturiere_artikel(wikitext):
    wikicode = mwparserfromhell.parse(wikitext)
    abschnitte = []
    aktueller_abschnitt = {"titel": "Einleitung", "inhalt": ""}
    
    for node in wikicode.nodes:
        if isinstance(node, mwparserfromhell.nodes.Heading):
            if aktueller_abschnitt["inhalt"]:
                aktueller_abschnitt["inhalt"] = mwparserfromhell.parse(aktueller_abschnitt["inhalt"]).strip_code().strip()
                aktueller_abschnitt["tags"] = generiere_tags(aktueller_abschnitt["inhalt"])
                abschnitte.append(aktueller_abschnitt)
            aktueller_abschnitt = {
                "titel": node.title.strip_code().strip(),
                "inhalt": ""
            }
        else:
            aktueller_abschnitt["inhalt"] += str(node)

    if aktueller_abschnitt["inhalt"]:
        aktueller_abschnitt["inhalt"] = mwparserfromhell.parse(aktueller_abschnitt["inhalt"]).strip_code().strip()
        aktueller_abschnitt["tags"] = generiere_tags(aktueller_abschnitt["inhalt"])
        abschnitte.append(aktueller_abschnitt)

    return abschnitte

def verarbeite_wikitext(wikitext):
    inhalt_markdown, verlinkte = extrahiere_links_und_inhalt(wikitext)
    struktur = strukturiere_artikel(wikitext)
    return inhalt_markdown, verlinkte, struktur

def save_article(titel, inhalt, verwandte, struktur):
    artikel_id = titel.lower().replace(" ", "-")
    artikel = {
        "id": artikel_id,
        "titel": titel,
        "inhalt": inhalt,
        "struktur": struktur,
        "zusammenfassung": inhalt[:300] + "...",
        "verwandteArtikel": verwandte
    }
    with open(os.path.join(OUTPUT_PATH, f"{artikel_id}.json"), "w", encoding="utf-8") as f:
        json.dump(artikel, f, ensure_ascii=False, indent=2)
    return artikel_id, titel, struktur

def main():
    print("🔍 Lade alle Artikeltitel...")
    alle_titel = get_all_titles()
    index = {"artikel": []}
    tag_index = {}
    print(f"➡️ {len(alle_titel)} Titel gefunden.\n")

    for i, titel in enumerate(alle_titel):
        print(f"📄 ({i+1}/{len(alle_titel)}) Verarbeite: {titel}")
        wikitext = lade_wikitext(titel)
        if not wikitext:
            print("⚠️ Kein Inhalt gefunden.")
            continue
        inhalt, verwandte, struktur = verarbeite_wikitext(wikitext)
        artikel_id, artikel_titel, strukturierte_abschnitte = save_article(titel, inhalt, verwandte, struktur)
        index["artikel"].append({"id": artikel_id, "titel": artikel_titel})
        # Tags zum globalen Index hinzufügen
        for abschnitt in strukturierte_abschnitte:
            for tag in abschnitt.get("tags", []):
                tag_index.setdefault(tag, []).append(artikel_id)
        time.sleep(0.3)

    with open(os.path.join(OUTPUT_PATH, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    with open(os.path.join(OUTPUT_PATH, "tag-index.json"), "w", encoding="utf-8") as f:
        json.dump(tag_index, f, ensure_ascii=False, indent=2)

    print("\n✅ Alle Artikel und Tag-Index gespeichert.")

if __name__ == "__main__":
    main()