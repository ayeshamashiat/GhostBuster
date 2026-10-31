"""Gate 0: how many usable real entities exist per type (with a Bangla Wikipedia page and bn label)?"""
import requests

URL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "PetniHunter/0.1 (hackathon research; mrittikajahan@iut-dhaka.edu)",
           "Accept": "application/sparql-results+json"}

TYPES = {
    "writer":  ("P106", "wd:Q36180 wd:Q49757 wd:Q6625963 wd:Q214917"),  # writer, poet, novelist, playwright
    "book":    ("P31",  "wd:Q7725634 wd:Q8261 wd:Q571 wd:Q25379 wd:Q49084"),  # literary work, novel, book, play, short story
    "poem":    ("P31",  "wd:Q5185279"),
    "film":    ("P31",  "wd:Q11424"),
    "song":    ("P31",  "wd:Q7366 wd:Q134556"),
}


def count(prop, classes):
    q = f"""
    SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{
      VALUES ?c {{ {classes} }}
      ?x wdt:{prop} ?c .
      ?s schema:about ?x ; schema:isPartOf <https://bn.wikipedia.org/> .
      ?x rdfs:label ?l . FILTER(LANG(?l) = "bn")
    }}"""
    r = requests.get(URL, params={"query": q}, headers=HEADERS, timeout=70)
    r.raise_for_status()
    return int(r.json()["results"]["bindings"][0]["n"]["value"])


for name, (prop, classes) in TYPES.items():
    try:
        print(f"{name:7s} with bn label + bn Wikipedia page: {count(prop, classes)}")
    except Exception as e:
        print(f"{name:7s} query failed: {type(e).__name__}: {str(e)[:100]}")
