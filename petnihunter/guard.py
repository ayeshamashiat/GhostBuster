"""PetniHunter guard: verify the entity in a Bangla question, then ACT.

   question -> extract (entity, property) -> bn.wikipedia search -> title similarity ->
     RESCUE   : exact/variant match -> Wikidata fact + source, resolved name always disclosed
     REDIRECT : near match or spelling suggestion -> "did you mean X?" (never answers about X)
     REFUSE   : nothing close -> honest "couldn't find it", no guess

Thresholds (EXACT, NEAR) were fixed up front and sanity-checked on the TRAIN split only (never tuned on test).
"""
import re
import time
from difflib import SequenceMatcher

import requests

from petnihunter.common import fold

EXACT, NEAR = 0.92, 0.70

S = requests.Session()
S.headers["User-Agent"] = "PetniHunter/0.1 (hackathon; mrittikajahan@iut-dhaka.edu)"
WP = "https://bn.wikipedia.org/w/api.php"
WD = "https://www.wikidata.org/w/api.php"

PATTERNS = [  # fast, deterministic extraction for the standard phrasings
    ("writer", "birth_year", r"^(.+?) কোন সালে জন্মগ্রহণ করেন\?$"),
    ("writer", "birth_year", r"^(.+?)-এর জন্মসাল কত\?$"),
    ("book", "author", r"^'(.+)' বইটি কে লিখেছেন\?$"),
    ("book", "author", r"^'(.+)'-এর লেখক কে\?$"),
    ("film", "director", r"^'(.+)' চলচ্চিত্রের পরিচালক কে\?$"),
    ("film", "director", r"^'(.+)' ছবিটি কে পরিচালনা করেছেন\?$"),
]
PROP = {"birth_year": "P569", "author": "P50", "director": "P57"}


def extract(q):
    for typ, ask, pat in PATTERNS:
        m = re.match(pat, q.strip())
        if m:
            return {"entity": m.group(1).strip(), "type": typ, "ask": ask}
    return None


SUPPORTED = {("writer", "birth_year"), ("book", "author"), ("film", "director")}
EXTRACT_PROMPT = """নিচের বাংলা প্রশ্ন থেকে JSON বের করো। শুধু JSON লেখো।
"type": writer (লেখক/কবি ব্যক্তি), book (বই/উপন্যাস/কবিতা), film (চলচ্চিত্র), অথবা other।
"ask": birth_year (জন্মসাল), author (বইয়ের লেখক), director (ছবির পরিচালক), অথবা other।
"entity": প্রশ্নে উল্লেখিত নাম, হুবহু যেভাবে লেখা আছে।

প্রশ্ন: হুমায়ূন আহমেদ কবে জন্মেছিলেন?
{"entity": "হুমায়ূন আহমেদ", "type": "writer", "ask": "birth_year"}
প্রশ্ন: 'দেবদাস' উপন্যাসটা কার লেখা?
{"entity": "দেবদাস", "type": "book", "ask": "author"}
প্রশ্ন: মেঘে ঢাকা তারা ছবিটা কে বানিয়েছেন?
{"entity": "মেঘে ঢাকা তারা", "type": "film", "ask": "director"}
প্রশ্ন: আজকের আবহাওয়া কেমন?
{"entity": "", "type": "other", "ask": "other"}

প্রশ্ন: """


def extract_llm(q):
    """Free-form extraction with the base model. Returns None if the question is not about a supported thing."""
    import json
    from petnihunter.llm import complete
    raw = complete(EXTRACT_PROMPT + q.strip() + "\n", max_tokens=80)
    m = re.search(r"\{.*?\}", raw, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    ent = str(d.get("entity", "")).strip(" '\"“”‘’")
    if not ent or (d.get("type"), d.get("ask")) not in SUPPORTED:
        return None
    return {"entity": ent, "type": d["type"], "ask": d["ask"], "via_llm": True}


class LookupError_(Exception):
    """Network/API failure. Never treated as 'entity does not exist'."""


_CACHE = {}


def _get(url, params):
    key = (url, tuple(sorted(params.items())))
    if key in _CACHE:
        return _CACHE[key]
    for a in range(5):
        try:
            r = S.get(url, params={**params, "format": "json"}, timeout=25)
            r.raise_for_status()
            d = r.json()
            if "error" in d:
                raise ValueError(d["error"])
            _CACHE[key] = d  # only successful responses are cached
            return d
        except Exception:
            time.sleep(1.5 * (a + 1))
    raise LookupError_(f"lookup failed: {url}")


def sim(a, b):
    return SequenceMatcher(None, fold(a), fold(b)).ratio()


def wp_search(name):
    d = _get(WP, {"action": "query", "list": "search", "srsearch": name, "srlimit": 5, "srinfo": "suggestion", "srprop": ""})
    q = d.get("query", {})
    return [h["title"] for h in q.get("search", [])], q.get("searchinfo", {}).get("suggestion")


def wp_qid(title):
    d = _get(WP, {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "titles": title, "redirects": 1})
    for p in d.get("query", {}).get("pages", {}).values():
        return p.get("pageprops", {}).get("wikibase_item")
    return None


TYPE_OK = {  # Wikidata class / occupation ids that count as the asked kind of entity
    "writer": ("P106", {"Q36180", "Q49757", "Q6625963", "Q214917"}),
    "book": ("P31", {"Q7725634", "Q8261", "Q571", "Q25379", "Q49084"}),
    "film": ("P31", {"Q11424"}),
}


def wd_claims(qid):
    d = _get(WD, {"action": "wbgetentities", "ids": qid, "props": "claims"})
    return d.get("entities", {}).get(qid, {}).get("claims", {})


def is_type(qid, typ):
    prop, ok = TYPE_OK[typ]
    got = {c["mainsnak"]["datavalue"]["value"]["id"] for c in wd_claims(qid).get(prop, []) if "datavalue" in c.get("mainsnak", {})}
    return bool(got & ok)


def wd_fact(qid, ask):
    """Wikidata value for the asked property (Bangla label for people), or None."""
    claims = wd_claims(qid).get(PROP[ask], [])
    if not claims:
        return None
    if ask == "birth_year":
        t = claims[0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time")
        return t[1:5].lstrip("0") if t else None
    ids = [c["mainsnak"]["datavalue"]["value"]["id"] for c in claims if "datavalue" in c.get("mainsnak", {})][:3]
    if not ids:
        return None
    lab = _get(WD, {"action": "wbgetentities", "ids": "|".join(ids), "props": "labels", "languages": "bn|en"})
    out = []
    for i in ids:
        L = lab.get("entities", {}).get(i, {}).get("labels", {})
        out.append((L.get("bn") or L.get("en") or {}).get("value", i))
    return ", ".join(out)


def tsim(name, title):
    """similarity ignoring a trailing '(disambiguation)' qualifier"""
    return max(sim(name, title), sim(name, re.sub(r"\s*\([^)]*\)\s*$", "", title)))


def _typed(titles, typ):
    """first title whose Wikipedia page is the right KIND of entity (writer/book/film) per Wikidata"""
    for t in titles:
        q = wp_qid(t)
        if q and is_type(q, typ):
            return t
    return None


def decide(name, typ):
    """-> (action, [titles], score, via). action in rescue|redirect|refuse"""
    titles, sugg = wp_search(name)
    ranked = sorted(((tsim(name, t), t) for t in titles), reverse=True)
    exact = [t for sc, t in ranked if sc >= EXACT]
    if exact:
        return "rescue", exact, ranked[0][0], "search"
    if sugg:
        t2, _ = wp_search(sugg)
        r2 = sorted(((tsim(sugg, t), t) for t in t2), reverse=True)
        cand = _typed([t for sc, t in r2 if sc >= EXACT and tsim(name, t) >= NEAR], typ)
        if cand:
            return "redirect", [cand], tsim(name, cand), "suggestion"
    cand = _typed([t for sc, t in ranked if sc >= NEAR], typ)
    if cand:
        return "redirect", [cand], tsim(name, cand), "search"
    return "refuse", [], ranked[0][0] if ranked else 0.0, "none"


def answer(q):
    try:
        return _answer(q)
    except (LookupError_, TimeoutError):
        return {"action": "error", "text": "যাচাই করতে পারিনি (নেটওয়ার্ক সমস্যা)।",
                "text_en": "Could not verify (network problem)."}


def _answer(q):
    ex = extract(q) or extract_llm(q)
    if not ex:
        return {"action": "unsupported",
                "text": "এই প্রশ্নটি আমি বুঝতে পারিনি। আমি এখন শুধু লেখকের জন্মসাল, বইয়ের লেখক আর চলচ্চিত্রের পরিচালক যাচাই করতে পারি।",
                "text_en": "I did not understand this question. For now I can only verify a writer's birth year, a book's author, or a film's director."}
    name = ex["entity"]
    action, titles, score, via = decide(name, ex["type"])
    res = {"action": action, "entity": name, "type": ex["type"], "ask": ex["ask"], "title": titles[0] if titles else None,
           "score": round(score, 3), "via": via}
    if action == "refuse":
        res["text"] = f"'{name}' নামে বাংলা উইকিপিডিয়ায় নির্ভরযোগ্য কিছু খুঁজে পাইনি, তাই অনুমান করে উত্তর দিচ্ছি না।"
        res["text_en"] = f"I found nothing reliable named '{name}' on Bangla Wikipedia, so I will not guess."
        return res
    if action == "redirect":
        res["text"] = f"'{name}' নামে হুবহু কিছু খুঁজে পাইনি। আপনি কি '{titles[0]}' বোঝাতে চেয়েছেন?"
        res["text_en"] = f"I found nothing named exactly '{name}'. Did you mean '{titles[0]}'?"
        res["qid"] = wp_qid(titles[0])
        return res
    cands = []                                # every matching page that is the right KIND of entity and has the fact
    for title in titles:
        qid = wp_qid(title)
        if qid and is_type(qid, ex["type"]):
            fact = wd_fact(qid, ex["ask"])
            if fact and qid not in [c[1] for c in cands]:
                cands.append((title, qid, fact))
    if len(cands) > 1:                        # homonyms: ask, don't pick
        opts = " / ".join(f"'{t}'" for t, _, _ in cands[:3])
        res.update(action="redirect", title=cands[0][0], qid=None, ambiguous=True,
                   text=f"'{name}' নামে একাধিক {opts} পাওয়া গেছে। কোনটি জানতে চান?",
                   text_en=f"More than one match for '{name}': {opts}. Which one do you mean?")
        return res
    if cands:
        title, qid, fact = cands[0]
        verb = {"birth_year": f"{fact} সালে জন্মগ্রহণ করেন", "author": f"লেখক: {fact}", "director": f"পরিচালক: {fact}"}[ex["ask"]]
        disclose = "" if title == name else f" ('{name}' বলতে '{title}' ধরে নিয়েছি)"
        verb_en = {"birth_year": f"born in {fact}", "author": f"author: {fact}", "director": f"director: {fact}"}[ex["ask"]]
        disclose_en = "" if title == name else f" (I read '{name}' as '{title}')"
        res.update(title=title, qid=qid, fact=fact, text=f"{title}{disclose}: {verb}। [সূত্র: Wikidata {qid}]",
                   text_en=f"{title}{disclose_en}: {verb_en}. [source: Wikidata {qid}]")
        return res
    res["action"] = "redirect"
    res["qid"] = wp_qid(titles[0])
    res["action"] = "refuse"
    res["text"] = f"'{name}' নামে '{titles[0]}' পাওয়া গেছে, কিন্তু এটি প্রশ্নের ধরনের (লেখক/বই/চলচ্চিত্র) সাথে মেলে না বা যাচাই করা তথ্য নেই। তাই অনুমান করছি না।"
    res["text_en"] = f"'{titles[0]}' exists for '{name}', but it is not the kind of entity asked about (writer/book/film) or has no verified fact, so I will not guess."
    return res


# --- exact Bangla -> English for the guard's own (templated) messages. Never machine-translate these:
# --- a mistranslated negation ("will not guess" -> "will guess") would invert the meaning.
_EN_RULES = [
    (r"^'(.+)' নামে বাংলা উইকিপিডিয়ায় নির্ভরযোগ্য কিছু খুঁজে পাইনি, তাই অনুমান করে উত্তর দিচ্ছি না।$",
     lambda m: f"I found nothing reliable named '{m[1]}' on Bangla Wikipedia, so I will not guess."),
    (r"^'(.+)' নামে হুবহু কিছু খুঁজে পাইনি। আপনি কি '(.+)' বোঝাতে চেয়েছেন\?$",
     lambda m: f"I found nothing named exactly '{m[1]}'. Did you mean '{m[2]}'?"),
    (r"^'(.+)' নামে একাধিক (.+) পাওয়া গেছে। কোনটি জানতে চান\?$",
     lambda m: f"More than one match for '{m[1]}': {m[2]}. Which one do you mean?"),
    (r"^'(.+)' নামে '(.+)' পাওয়া গেছে, কিন্তু এটি প্রশ্নের ধরনের .*তাই অনুমান করছি না।$",
     lambda m: f"'{m[2]}' exists for '{m[1]}', but it is not the kind of entity asked about (writer/book/film) or has no verified fact, so I will not guess."),
    (r"^(.+?)(?: \('(.+)' বলতে '(.+)' ধরে নিয়েছি\))?: (.+)। \[সূত্র: Wikidata (Q\d+)\]$",
     lambda m: f"{m[1]}" + (f" (I read '{m[2]}' as '{m[3]}')" if m[2] else "") + ": " +
               (f"born in {m[4].split(' ')[0]}" if m[4].endswith("সালে জন্মগ্রহণ করেন") else
                "author: " + m[4].split(": ", 1)[1] if m[4].startswith("লেখক: ") else
                "director: " + m[4].split(": ", 1)[1] if m[4].startswith("পরিচালক: ") else m[4]) + f". [source: Wikidata {m[5]}]"),
]


def bn_to_en(text):
    """English for a guard message, or None if it matches no known template (never guesses)."""
    for pat, fn in _EN_RULES:
        m = re.match(pat, text.strip())
        if m:
            return fn(m)
    return None
