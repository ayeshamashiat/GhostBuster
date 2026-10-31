"""Re-run only the guard items that failed with a lookup error, then merge. Errors are never counted as refusals."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from petnihunter.common import is_correct
from petnihunter.guard import answer

path = "results/guard.jsonl"
rows = [json.loads(l) for l in open(path, encoding="utf-8")]
todo = [i for i, r in enumerate(rows) if r["action"] == "error"]
print("retrying", len(todo))


def run(i):
    try:
        return answer(rows[i]["question"])
    except Exception as e:
        return {"action": "error", "text": type(e).__name__}


with ThreadPoolExecutor(2) as ex:
    outs = list(ex.map(run, todo))

for i, g in zip(todo, outs):
    r, a = rows[i], g["action"]
    silent, verdict = False, "error"
    if a != "error":
        if r["kind"] == "ghost":
            verdict, silent = ("abstain" if a in ("refuse", "redirect") else "wrong"), a == "rescue"
        elif r["kind"] == "real":
            if a == "rescue":
                silent = g.get("qid") != r["qid"]
                verdict = "correct" if (is_correct(r["type"], r["gold"], g.get("fact", "")) and not silent) else "wrong"
            else:
                verdict = "abstain"
        else:
            if a in ("rescue", "redirect") and g.get("qid") == r["qid"]:
                verdict = "correct" if (a == "redirect" or is_correct(r["type"], r["gold"], g.get("fact", ""))) else "wrong"
            elif a == "rescue":
                verdict, silent = "wrong", True
            else:
                verdict = "abstain"
    rows[i].update(output=g["text"], action=a, resolved=g.get("title"), resolved_qid=g.get("qid"),
                   score=g.get("score"), verdict=verdict, silent_sub=silent)

with open(path, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("still errors:", sum(r["action"] == "error" for r in rows))
