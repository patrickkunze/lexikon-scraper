import mwparserfromhell
import requests
import os
import json

# Konfiguration
BASE_URL = "https://www.lexikon-betreuungsrecht.de/api.php"
ARTIKEL = ["Betreuung", "Einwilligungsvorbehalt", "Vorsorgevollmacht"]
OUTPUT_PATH = "artikel"
os.makedirs(OUTPUT_PATH, exist_ok=True)

def lade_wikitext(titel):
    """Lädt den Wikitext eines Artikels über die MediaWiki API"""
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
    """Parst den Wikitext, extrahiert verlinkte Artikel und ersetzt sie durch Markdown-Links"""
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

index = {"artikel": []}

for titel in ARTIKEL:
    wikitext = lade_wikitext(titel)
    if not wikitext:
        print(f"❌ Kein Inhalt für: {titel}")
        continue
    inhalt, verwandte = extrahiere_links_und_inhalt(wikitext)
    artikel_id = titel.lower().replace(" ", "-")
    artikel = {
        "id": artikel_id,
        "titel": titel,
        "inhalt": inhalt,
        "zusammenfassung": inhalt[:300] + "...",
        "verwandteArtikel": verwandte
    }
    with open(os.path.join(OUTPUT_PATH, f"{artikel_id}.json"), "w", encoding="utf-8") as f:
        json.dump(artikel, f, ensure_ascii=False, indent=2)
    index["artikel"].append({"id": artikel_id, "titel": titel})

with open(os.path.join(OUTPUT_PATH, "index.json"), "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

print("✅ Alle Artikel verarbeitet und gespeichert.")