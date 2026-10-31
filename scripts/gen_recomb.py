"""Shape-matched ghosts: splice parts of two different real names. Verified absent from bn Wikipedia."""
import json, random, re, time
from difflib import SequenceMatcher
import requests

random.seed(21)
real = [json.loads(l) for l in open("data/raw/real.jsonl", encoding="utf-8")]
names = {t: [r["bn"] for r in real if r["type"] == t] for t in ("writer", "book", "film")}
allreal = {r["bn"] for r in real}
S = requests.Session(); S.headers["User-Agent"] = "PetniHunter/0.1 (hackathon; mrittikajahan@iut-dhaka.edu)"

def exists(n):
    for _ in range(3):
        try:
            hits = S.get("https://bn.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": n, "srlimit": 3, "format": "json"}, timeout=20).json()["query"]["search"]
            return any(SequenceMatcher(None, n, h["title"]).ratio() >= 0.85 for h in hits)
        except Exception:
            time.sleep(2)
    return True

def splice(typ):
    a, b = random.sample(names[typ], 2)
    wa, wb = a.split(), b.split()
    if typ == "writer":
        if len(wa) < 2 or len(wb) < 2: return None
        return " ".join(wa[:-1] + wb[-1:])
    if len(wa) < 2 or len(wb) < 2: return None
    return " ".join(wa[: max(1, len(wa) // 2)] + wb[len(wb) // 2:])

WANT = {"writer": 300, "book": 200, "film": 250}
out = open("data/raw/ghosts_recomb.jsonl", "w", encoding="utf-8")
for typ, want in WANT.items():
    seen, kept, tries = set(), 0, 0
    while kept < want and tries < want * 15:
        tries += 1
        n = splice(typ)
        if not n or n in seen or n in allreal or re.search(r"[A-Za-z0-9]", n): continue
        seen.add(n)
        if exists(n): continue
        out.write(json.dumps({"type": typ, "bn": n, "source": "recombined"}, ensure_ascii=False) + "\n"); kept += 1
    print(typ, kept)
