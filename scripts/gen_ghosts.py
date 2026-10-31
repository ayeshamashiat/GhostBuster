"""Step 1b: invent ghost writers/books/films with Qwen, then drop any that match a real Bangla Wikipedia page.

Output: data/raw/ghosts.jsonl  (type, bn, source="invented")
"""
import asyncio
import json
import os
import random
import re
import time
from difflib import SequenceMatcher

import requests
import tinker
from dotenv import load_dotenv

load_dotenv()
random.seed(7)
real = [json.loads(l) for l in open("data/raw/real.jsonl", encoding="utf-8")]
real_names = {r["bn"] for r in real}
by_type = {t: [r["bn"] for r in real if r["type"] == t] for t in ("writer", "book", "film")}

KIND = {"writer": "a Bengali writer's full name", "book": "the title of a Bengali novel or book",
        "film": "the title of a Bengali-language film"}
WANT = {"writer": 700, "book": 300, "film": 500}  # after filtering we keep what survives
OVERGEN = 2.2


def prompt_for(typ):
    ex = random.sample(by_type[typ], 6)
    lines = "\n".join(f"- {e}" for e in ex)
    return (f"<|im_start|>user\nHere are real examples of {KIND[typ]} (in Bangla):\n{lines}\n\n"
            f"Invent ONE new {KIND[typ]} in Bangla that sounds realistic but does NOT exist. "
            f"Reply with only the Bangla name, nothing else.<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n\n</think>\n\n")


def clean(s):
    s = s.replace("<|im_end|>", "").strip().split("\n")[0]
    s = re.sub(r"^[-*\d.\s]+", "", s).strip(" '\"“”‘’*।")
    return s


async def generate():
    sc = tinker.ServiceClient(display_name="petnihunter-ghosts")
    client = await sc.create_sampling_client_async(base_model="Qwen/Qwen3.5-4B")
    tok = client.get_tokenizer()
    out = {t: [] for t in KIND}
    for typ in KIND:
        n = int(WANT[typ] * OVERGEN)
        tasks = []
        for _ in range(n):
            ids = tok.encode(prompt_for(typ))
            tasks.append(client.sample_async(
                prompt=tinker.types.ModelInput.from_ints(ids), num_samples=1,
                sampling_params=tinker.types.SamplingParams(max_tokens=30, temperature=1.0, stop=["<|im_end|>"])))
        res = await asyncio.gather(*tasks)
        for r in res:
            out[typ].append(clean(tok.decode(r.sequences[0].tokens)))
        print(typ, "generated", len(out[typ]))
    return out


S = requests.Session()
S.headers["User-Agent"] = "PetniHunter/0.1 (hackathon; mrittikajahan@iut-dhaka.edu)"


def exists_on_wikipedia(name):
    """True if a top-3 Bangla Wikipedia search hit has a near-identical title."""
    for attempt in range(3):
        try:
            r = S.get("https://bn.wikipedia.org/w/api.php", params={
                "action": "query", "list": "search", "srsearch": name, "srlimit": 3,
                "format": "json"}, timeout=20)
            hits = r.json()["query"]["search"]
            return any(SequenceMatcher(None, name, h["title"]).ratio() >= 0.85 for h in hits)
        except Exception:
            time.sleep(2)
    return True  # be conservative: if we can't check, drop it


cands = asyncio.run(generate())
os.makedirs("data/raw", exist_ok=True)
kept_total = 0
with open("data/raw/ghosts.jsonl", "w", encoding="utf-8") as f:
    for typ, names in cands.items():
        seen, kept = set(), 0
        for n in names:
            if kept >= WANT[typ]:
                break
            if not (3 <= len(n) <= 60) or not re.search(r"[ঀ-৿]", n) or n in seen or n in real_names:
                continue
            seen.add(n)
            if exists_on_wikipedia(n):
                continue
            f.write(json.dumps({"type": typ, "bn": n, "source": "invented"}, ensure_ascii=False) + "\n")
            kept += 1
        print(typ, "kept", kept, "of", len(names))
        kept_total += kept
print("total ghosts", kept_total)
