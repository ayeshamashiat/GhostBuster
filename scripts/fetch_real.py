"""Step 1a: pull real writers / books / Bengali films from Wikidata into data/raw/real.jsonl.

Each row: type, qid, bn (Bangla label), en (English label or ""), gold (Bangla answer string),
gold_en, pop (number of Wikipedia language editions, a popularity proxy).
"""
import json
import os
import time

import requests

URL = "https://query.wikidata.org/sparql"
H = {"User-Agent": "PetniHunter/0.1 (hackathon research; mrittikajahan@iut-dhaka.edu)",
     "Accept": "application/sparql-results+json"}
BN = "<https://bn.wikipedia.org/>"

QUERIES = {
    # gold = birth year
    "writer": f"""
    SELECT ?x ?bn ?en ?gold ?pop WHERE {{
      VALUES ?c {{ wd:Q36180 wd:Q49757 wd:Q6625963 wd:Q214917 }}
      ?x wdt:P106 ?c ; wdt:P569 ?b ; wikibase:sitelinks ?pop .
      {{ ?x wdt:P1412 wd:Q9610 }} UNION {{ ?x wdt:P27 wd:Q902 }}
      ?s schema:about ?x ; schema:isPartOf {BN} .
      ?x rdfs:label ?bn . FILTER(LANG(?bn)="bn")
      OPTIONAL {{ ?x rdfs:label ?en . FILTER(LANG(?en)="en") }}
      BIND(STR(YEAR(?b)) AS ?gold)
    }}""",
    # gold = author's Bangla name
    "book": f"""
    SELECT ?x ?bn ?en (SAMPLE(?ab) AS ?gold) (SAMPLE(?ae) AS ?gold_en) (MAX(?pop0) AS ?pop) WHERE {{
      VALUES ?c {{ wd:Q7725634 wd:Q8261 wd:Q571 wd:Q25379 wd:Q49084 }}
      ?x wdt:P31 ?c ; wdt:P50 ?a ; wikibase:sitelinks ?pop0 .
      {{ ?x wdt:P407 wd:Q9610 }} UNION {{ ?a wdt:P1412 wd:Q9610 }}
      ?s schema:about ?x ; schema:isPartOf {BN} .
      ?x rdfs:label ?bn . FILTER(LANG(?bn)="bn")
      ?a rdfs:label ?ab . FILTER(LANG(?ab)="bn")
      OPTIONAL {{ ?x rdfs:label ?en . FILTER(LANG(?en)="en") }}
      OPTIONAL {{ ?a rdfs:label ?ae . FILTER(LANG(?ae)="en") }}
    }} GROUP BY ?x ?bn ?en""",
    # gold = director's Bangla name
    "film": f"""
    SELECT ?x ?bn ?en (SAMPLE(?db) AS ?gold) (SAMPLE(?de) AS ?gold_en) (MAX(?pop0) AS ?pop) WHERE {{
      ?x wdt:P31 wd:Q11424 ; wdt:P364 wd:Q9610 ; wdt:P57 ?d ; wikibase:sitelinks ?pop0 .
      ?s schema:about ?x ; schema:isPartOf {BN} .
      ?x rdfs:label ?bn . FILTER(LANG(?bn)="bn")
      ?d rdfs:label ?db . FILTER(LANG(?db)="bn")
      OPTIONAL {{ ?x rdfs:label ?en . FILTER(LANG(?en)="en") }}
      OPTIONAL {{ ?d rdfs:label ?de . FILTER(LANG(?de)="en") }}
    }} GROUP BY ?x ?bn ?en""",
}


def run(q):
    for attempt in range(4):
        try:
            r = requests.get(URL, params={"query": q}, headers=H, timeout=120)
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except Exception as e:
            print("  retry", attempt, type(e).__name__, str(e)[:80])
            time.sleep(5 * (attempt + 1))
    return []


def val(b, k):
    return b.get(k, {}).get("value", "")


os.makedirs("data/raw", exist_ok=True)
seen, rows = set(), []
for typ, q in QUERIES.items():
    got = run(q)
    n = 0
    for b in got:
        qid = val(b, "x").rsplit("/", 1)[-1]
        if (typ, qid) in seen:
            continue
        seen.add((typ, qid))
        rows.append({"type": typ, "qid": qid, "bn": val(b, "bn"), "en": val(b, "en"),
                     "gold": val(b, "gold"), "gold_en": val(b, "gold_en"),
                     "pop": int(float(val(b, "pop") or 0))})
        n += 1
    print(typ, n)

with open("data/raw/real.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("total", len(rows))
