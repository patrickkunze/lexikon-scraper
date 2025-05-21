import requests
import mwparserfromhell
import os
import json
import time

BASE_URL = "https://www.lexikon-betreuungsrecht.de/api.php"
OUTPUT_PATH = "artikel"
os.makedirs(OUTPUT_PATH, exist_ok=True)

def get_all_titles():
    """Lädt alle Artikeltitel der Wiki-Seite."""
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
            time.sleep(0.5)  # API-Freundlichkeit
        else:
            break
    return titles

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

def save_article(titel, inhalt, verwandte):
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
    return artikel_id, titel

def main():
    print("🔍 Lade alle Artikeltitel...")
    alle_titel = get_all_titles()
    index = {"artikel": []}
    print(f"➡️ {len(alle_titel)} Titel gefunden.\n")

    for i, titel in enumerate(alle_titel):
        print(f"📄 ({i+1}/{len(alle_titel)}) Verarbeite: {titel}")
        wikitext = lade_wikitext(titel)
        if not wikitext:
            print("⚠️ Kein Inhalt gefunden.")
            continue
        inhalt, verwandte = extrahiere_links_und_inhalt(wikitext)
        artikel_id, artikel_titel = save_article(titel, inhalt, verwandte)
        index["artikel"].append({"id": artikel_id, "titel": artikel_titel})
        time.sleep(0.3)  # schonend zur API

    with open(os.path.join(OUTPUT_PATH, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print("\n✅ Alle Artikel gespeichert.")

if __name__ == "__main__":
    main()
