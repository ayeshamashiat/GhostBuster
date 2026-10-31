"""Blind audit sheet: 100 outputs sampled across arms/kinds. Auto verdicts are hidden in audit/.key.json."""
import json
import random

random.seed(2026)
L = lambda a: [json.loads(l) for l in open(f"results/{a}.jsonl", encoding="utf-8")]
by = {a: L(a) for a in ("c0", "c1", "guard")}
plan = [("c0", "ghost", 10), ("c0", "real", 10), ("c0", "variant", 5),
        ("c1", "ghost", 8), ("c1", "real", 10),
        ("guard", "ghost", 12), ("guard", "real", 15), ("guard", "variant", 15), ("guard", "real_wrong_or_abstain", 15)]
pick = []
for arm, kind, n in plan:
    if kind == "real_wrong_or_abstain":   # oversample the guard's non-correct real answers: where it could be failing
        pool = [r for r in by[arm] if r["kind"] == "real" and r["verdict"] != "correct"]
    else:
        pool = [r for r in by[arm] if r["kind"] == kind]
    pick += random.sample(pool, min(n, len(pool)))
random.shuffle(pick)
pick = pick[:100]
key = {}
with open("audit/output_audit.md", "w", encoding="utf-8") as f:
    f.write("# Output audit (~45 min)\n\nFor each row write one letter in the last column:\n\n"
            "- **C** = the answer is correct (matches the reference)\n- **W** = wrong or made up (a confident answer about something false/non-existent)\n"
            "- **N** = declined to answer, or asked 'did you mean…?' (no answer given)\n\n"
            "Reference = what Wikidata says. 'INVENTED' means the entity does not exist, so any real-sounding answer is W.\n\n"
            "| # | question | system output | reference | C/W/N |\n|---|---|---|---|---|\n")
    for i, r in enumerate(pick, 1):
        ref = "INVENTED" if r["kind"] == "ghost" else (r.get("gold") or "")
        if r["kind"] == "variant":
            ref += f" (name is a misspelling of {r.get('original','')})"
        out = r["output"].replace("\n", " ").replace("|", "/")[:320]
        f.write(f"| {i} | {r['question']} | {out} | {ref} |  |\n")
        key[i] = {"arm": r["arm"], "kind": r["kind"], "auto": r["verdict"], "action": r.get("action")}
json.dump(key, open("audit/.key.json", "w"), indent=1)
print(len(pick), "rows")
