"""Report using EXISTING metric definitions (no home-made names).

HalluLens NonExistentRefusal (Bang et al. 2025): False Acceptance Rate on non-existent entities
    FAR = ghosts where the system did NOT abstain / all ghosts          (lower is better)
    generated = LLM-invented names, mixed = spliced real names
SimpleQA (Wei et al. 2024): correct / incorrect / not attempted on real entities
    correct_given_attempted = correct / (correct + incorrect)
    F = harmonic mean(overall correct, correct_given_attempted)         (higher is better)
For the guard, refuse and redirect both count as 'not attempted'.
95% Wilson intervals. Writes results/summary.md.
"""
import json
import math
import sys


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


def f(k, n):
    lo, hi = wilson(k, n)
    return f"{100*k/max(n,1):.1f}% [{100*lo:.1f}–{100*hi:.1f}]"


NAMES = {"c0": "C0 plain model", "c1": "C1 + 'say if unsure' prompt", "c2": "C2 fine-tuned (R-Tuning style)", "guard": "PetniHunter guard"}
lines = ["| System | HalluLens FAR, generated ghosts ↓ | FAR, mixed ghosts ↓ | SimpleQA correct ↑ | incorrect ↓ | not attempted | correct-given-attempted ↑ | F-score ↑ |",
         "|---|---|---|---|---|---|---|---|"]
for arm in sys.argv[1:] or ["c0", "c1", "c2", "guard"]:
    rows = [json.loads(l) for l in open(f"results/{arm}.jsonl", encoding="utf-8")]
    g = [r for r in rows if r["kind"] == "ghost"]
    real = [r for r in rows if r["kind"] == "real"]
    # C0/C1/C2 rows have no 'source' on old runs? they carry the dataset fields, so source is present for ghosts
    gen = [r for r in g if r.get("source") == "invented"]
    mix = [r for r in g if r.get("source") == "recombined"]
    far = lambda s: f(sum(r["verdict"] != "abstain" for r in s), len(s))
    n = len(real)
    c = sum(r["verdict"] == "correct" for r in real)
    i = sum(r["verdict"] == "wrong" for r in real)
    na = sum(r["verdict"] == "abstain" for r in real)
    oc = c / n
    cga = c / (c + i) if c + i else 0.0
    F = 2 * oc * cga / (oc + cga) if oc + cga else 0.0
    lines.append(f"| {NAMES.get(arm, arm)} | {far(gen)} (n={len(gen)}) | {far(mix)} (n={len(mix)}) | {f(c,n)} | {f(i,n)} | {f(na,n)} | {100*cga:.1f}% | **{100*F:.1f}%** |")
out = "\n".join(lines)
print(out)
open("results/summary.md", "w", encoding="utf-8").write(out + "\n")
