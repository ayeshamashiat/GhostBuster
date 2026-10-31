"""Step 1c: combine real + ghosts into data/dataset.jsonl with splits.

Splits
  writer, book : 70% train / 30% test (train used only for fine-tuning)
  film         : test only (held-out TYPE, never seen in training)
Kinds
  real     : a real entity, gold answer from Wikidata
  ghost    : invented, no gold
  variant  : a real test entity with its name spelled differently (gold = original's gold)
Each test item is asked in phrasing A (seen in training) or B (never seen).
"""
import json
import random
import re

from petnihunter.common import question

random.seed(11)
real = [json.loads(l) for l in open("data/raw/real.jsonl", encoding="utf-8")]
ghosts = [g for f in ("data/raw/ghosts.jsonl", "data/raw/ghosts_recomb.jsonl")
          for g in (json.loads(l) for l in open(f, encoding="utf-8"))
          if not re.search(r"[A-Za-z0-9]", g["bn"])]  # Bangla-only ghosts, two sources
real_names = {r["bn"] for r in real}

# per-type popularity bucket for real entities (tertiles of sitelink count)
for typ in ("writer", "book", "film"):
    rs = sorted([r for r in real if r["type"] == typ], key=lambda r: r["pop"])
    n = len(rs)
    for i, r in enumerate(rs):
        r["bucket"] = "obscure" if i < n / 3 else ("mid" if i < 2 * n / 3 else "famous")

# spelling variants that real Bangla writers genuinely use
SWAPS = [("ী", "ি"), ("ি", "ী"), ("ূ", "ু"), ("ু", "ূ"), ("শ", "স"), ("স", "শ"), ("ষ", "শ"), ("ন", "ণ"), ("ণ", "ন"),
         ("য়", "য"), ("ে", "ি")]


def variant(name):
    opts = [(a, b) for a, b in SWAPS if a in name]
    random.shuffle(opts)
    for a, b in opts:
        v = name.replace(a, b, 1)
        if v != name and v not in real_names:
            return v
    return None


rows, uid = [], 0


def add(kind, typ, name, split, **extra):
    global uid
    uid += 1
    phr = random.choice("AB") if split == "test" else "A"
    rows.append({"id": uid, "kind": kind, "type": typ, "bn": name, "split": split, "phrasing": phr,
                 "question": question(typ, name, phr), **extra})


for typ in ("writer", "book", "film"):
    rs = [r for r in real if r["type"] == typ]
    random.shuffle(rs)
    gs = [g for g in ghosts if g["type"] == typ]
    random.shuffle(gs)
    if typ == "film":
        rs, gs = rs[:500], gs[:500]
        cut_r = cut_g = 0           # all test
    else:
        cut_r, cut_g = int(len(rs) * 0.3), int(len(gs) * 0.3)
    for i, r in enumerate(rs):
        sp = "test" if i < max(cut_r, 1) or typ == "film" else "train"
        add("real", typ, r["bn"], sp, gold=r["gold"], qid=r["qid"], pop=r["pop"], bucket=r["bucket"])
        if sp == "test" and typ != "film" and len([x for x in rows if x["kind"] == "variant" and x["type"] == typ]) < 200:
            v = variant(r["bn"])
            if v:
                add("variant", typ, v, "test", gold=r["gold"], qid=r["qid"], original=r["bn"], bucket=r["bucket"])
    for i, g in enumerate(gs):
        sp = "test" if (i < cut_g or typ == "film") else "train"
        add("ghost", typ, g["bn"], sp, source=g["source"])

with open("data/dataset.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

import collections
c = collections.Counter((r["split"], r["kind"], r["type"]) for r in rows)
for k in sorted(c):
    print(k, c[k])
