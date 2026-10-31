"""Run the PetniHunter guard (arm P) on a split; save results/guard.jsonl (or guard_train.jsonl).
usage: python scripts/eval_guard.py [test|train]
Outcome mapping (for report.py):
  ghost  : refuse/redirect -> abstain (safe) ; rescue -> wrong ('ghost swallowed')
  real   : rescue w/ right fact -> correct ; rescue w/ wrong fact -> wrong ; refuse/redirect -> abstain
  variant: rescue/redirect landing on the ORIGINAL entity -> correct ; refuse -> abstain ; landing elsewhere -> wrong
silent_sub = guard ANSWERED (rescue) about an entity other than the one asked about.
"""
import collections
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from petnihunter.common import is_correct
from petnihunter.guard import answer

split = sys.argv[1] if len(sys.argv) > 1 else "test"
rows = [json.loads(l) for l in open("data/dataset.jsonl", encoding="utf-8")]
rows = [r for r in rows if r["split"] == split]
if split == "train":                       # train has no variants; synthesize a few for calibration
    import random
    random.seed(5)
    swaps = [("ী", "ি"), ("ূ", "ু"), ("শ", "স"), ("ষ", "শ"), ("ণ", "ন")]
    for r in [x for x in rows if x["kind"] == "real"][:300]:
        for a, b in swaps:
            if a in r["bn"]:
                rows.append({**r, "kind": "variant", "bn": r["bn"].replace(a, b, 1), "original": r["bn"]})
                from petnihunter.common import question
                rows[-1]["question"] = question(r["type"], rows[-1]["bn"], "A")
                break

def run(r):
    try:
        return answer(r["question"])
    except Exception as e:
        return {"action": "error", "text": f"{type(e).__name__}"}

with ThreadPoolExecutor(4) as ex:
    outs = list(ex.map(run, rows))

def fact_ok(r, g):
    f = g.get("fact", "")
    return is_correct(r["type"], r["gold"], f if r["type"] != "writer" else f"{f}")

tot = collections.Counter()
with open("results/guard.jsonl" if split == "test" else "results/guard_train.jsonl", "w", encoding="utf-8") as f:
    for r, g in zip(rows, outs):
        a = g["action"]
        silent = False
        if a == "error":
            verdict = "error"
        elif r["kind"] == "ghost":
            verdict = "abstain" if a in ("refuse", "redirect") else "wrong"
            silent = a == "rescue"
        elif r["kind"] == "real":
            if a == "rescue":
                silent = g.get("qid") != r["qid"]
                verdict = "correct" if (fact_ok(r, g) and not silent) else "wrong"
            else:
                verdict = "abstain"
        else:  # variant
            if a in ("rescue", "redirect") and g.get("qid") == r["qid"] and a == "rescue" or (a == "redirect" and g.get("qid") == r.get("qid")):
                verdict = "correct" if (a == "redirect" or fact_ok(r, g)) else "wrong"
            elif a == "rescue":
                verdict, silent = "wrong", True
            else:
                verdict = "abstain"
        tot[(r["kind"], a, verdict, silent)] += 1
        f.write(json.dumps({**r, "arm": "guard", "output": g["text"], "action": a, "resolved": g.get("title"),
                            "resolved_qid": g.get("qid"), "score": g.get("score"), "verdict": verdict, "silent_sub": silent},
                           ensure_ascii=False) + "\n")
for k in sorted(tot):
    print(k, tot[k])
