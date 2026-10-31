"""Summarize results/*.jsonl: per arm, per kind (and type), with 95% Wilson intervals.

Key rates
  ghost:   hallucination = not abstain / not safe       (lower is better)
  real:    false refusal = abstain, accuracy = correct   (refusal lower, accuracy higher is better)
  variant: recovered = correct (or redirect), silent_wrong = answered about wrong thing
"""
import collections
import glob
import json
import math
import os
import sys


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{100*k/max(n,1):5.1f}% [{100*lo:4.1f}-{100*hi:4.1f}] (n={n})"


arms = sys.argv[1:] or sorted(os.path.basename(p)[:-6] for p in glob.glob("results/*.jsonl"))
for arm in arms:
    rows = [json.loads(l) for l in open(f"results/{arm}.jsonl", encoding="utf-8")]
    print(f"\n=== {arm} ===")
    for typ in ("writer", "book", "film", "ALL"):
        sub = [r for r in rows if typ == "ALL" or r["type"] == typ]
        g = [r for r in sub if r["kind"] == "ghost"]
        re_ = [r for r in sub if r["kind"] == "real"]
        v = [r for r in sub if r["kind"] == "variant"]
        if not sub:
            continue
        line = [f"{typ:6s}"]
        if g:
            line.append("GHOST hallucination " + fmt(sum(r["verdict"] != "abstain" for r in g), len(g)))
        if re_:
            line.append("| REAL false-refusal " + fmt(sum(r["verdict"] == "abstain" for r in re_), len(re_)))
            line.append("| acc " + fmt(sum(r["verdict"] == "correct" for r in re_), len(re_)))
        if v:
            line.append("| VARIANT correct " + fmt(sum(r["verdict"] == "correct" for r in v), len(v)))
        print("  ".join(line))
    fam = [r for r in rows if r["kind"] == "real" and r.get("bucket") == "famous"]
    if fam:
        print("  famous-real false-refusal " + fmt(sum(r["verdict"] == "abstain" for r in fam), len(fam)))
