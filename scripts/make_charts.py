"""Charts + tables from the saved results (no hard-coded numbers). Outputs docs/img/*.png and results/tables.md.

Palette: blue/orange/aqua/violet, validated (light surface, all-pairs CVD + normal-vision pass; aqua contrast WARN
is covered by direct labels on every mark). Colour follows the system, in every chart.
"""
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

OUT = "docs/img"
os.makedirs(OUT, exist_ok=True)
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SYS = [("guard", "PetniHunter guard", "#2a78d6"), ("c0", "Plain model", "#eb6834"),
       ("c1", "“Say if unsure” prompt", "#1baf7a"), ("c2", "Fine-tuned (R-Tuning)", "#4a3aa7")]
COL = {k: c for k, _, c in SYS}
NAME = {k: n for k, n, _ in SYS}

plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
                     "text.color": INK, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.edgecolor": GRID, "font.size": 13, "axes.spines.top": False, "axes.spines.right": False})


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


_p = lambda k: f"results/{k}.jsonl" if os.path.exists(f"results/{k}.jsonl") else f"results/{k}_v1.jsonl"
R = {k: [json.loads(l) for l in open(_p(k), encoding="utf-8")] for k, _, _ in SYS}


def stats(k):
    rows = R[k]
    g = [r for r in rows if r["kind"] == "ghost"]
    re_ = [r for r in rows if r["kind"] == "real"]
    far = sum(r["verdict"] != "abstain" for r in g)
    cor = sum(r["verdict"] == "correct" for r in re_)
    inc = sum(r["verdict"] == "wrong" for r in re_)
    oc = cor / len(re_)
    cga = cor / (cor + inc) if cor + inc else 0.0
    F = 2 * oc * cga / (oc + cga) if oc + cga else 0.0
    return dict(far=far, ng=len(g), cor=cor, nr=len(re_), inc=inc, F=F)


S = {k: stats(k) for k, _, _ in SYS}

# ---- 1. hero: the trade-off ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9.6, 6.4), dpi=200)
for k, n, c in SYS:
    s = S[k]
    x, y = 100 * s["far"] / s["ng"], 100 * s["cor"] / s["nr"]
    xl, xh = (100 * v for v in wilson(s["far"], s["ng"]))
    yl, yh = (100 * v for v in wilson(s["cor"], s["nr"]))
    ax.errorbar(x, y, xerr=[[x - xl], [xh - x]], yerr=[[y - yl], [yh - y]], fmt="none", ecolor=c, elinewidth=1.6, capsize=0, alpha=.8)
    ax.scatter(x, y, s=170, color=c, edgecolor=SURFACE, linewidth=2.5, zorder=3)
    dx, dy, ha = {"guard": (16, -4, "left"), "c0": (-12, 14, "right"), "c1": (16, 26, "left"), "c2": (16, 78, "left")}[k]
    ax.annotate(f"{n}\n{x:.0f}% fake answered · {y:.0f}% real right", (x, y), xytext=(dx, dy), textcoords="offset points",
                ha=ha, va="bottom", fontsize=12, color=INK, linespacing=1.3,
                arrowprops=dict(arrowstyle="-", color=c, lw=1.2, shrinkA=0, shrinkB=7) if k in ("c1", "c2") else None)
ax.set_xlim(-6, 104)
ax.set_ylim(-8, 106)
ax.set_xlabel("Fake Bangla names the system answered as if real  (lower is better)")
ax.set_ylabel("Real names answered correctly  (higher is better)")
ax.grid(color=GRID, linewidth=.8)
ax.set_axisbelow(True)
ax.text(-4.5, 104.5, "↖ ideal corner", fontsize=11, color=MUTED, va="top")
ax.set_title("Only the guard avoids both failures", loc="left", fontsize=17, fontweight="bold", pad=14)
fig.text(.01, .008, f"n = {S['guard']['ng']} fake entities and {S['guard']['nr']} real entities (Bangla writers, books, films). Bars = 95% Wilson intervals.\n"
         "Guard scores are ceilings: its lookup source (Wikipedia/Wikidata) is also where the gold answers come from.", fontsize=9.5, color=MUTED, linespacing=1.4)
fig.tight_layout(rect=(0, .06, 1, 1))
fig.savefig(f"{OUT}/01_tradeoff.png")
plt.close(fig)

# ---- 2. F-score bars ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9.6, 4.6), dpi=200)
labels = [NAME[k] for k, _, _ in SYS]
vals = [100 * S[k]["F"] for k, _, _ in SYS]
bars = ax.barh(range(len(SYS)), vals, color=[COL[k] for k, _, _ in SYS], height=.56)
for i, v in enumerate(vals):
    ax.text(v + 1.2, i, f"{v:.1f}", va="center", fontsize=14, fontweight="bold", color=INK)
ax.set_yticks(range(len(SYS)), labels, fontsize=13, color=INK)
ax.invert_yaxis()
ax.set_xlim(0, 108)
ax.set_xlabel("SimpleQA-style F-score on real entities  (higher is better)")
ax.grid(axis="x", color=GRID, linewidth=.8)
ax.set_axisbelow(True)
ax.spines["left"].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.set_title("A model that never answers scores zero", loc="left", fontsize=17, fontweight="bold", pad=12)
fig.text(.01, .01, "F = harmonic mean of overall-correct and correct-given-attempted (Wei et al., SimpleQA). Not attempted counts against overall-correct.", fontsize=9.5, color=MUTED)
fig.tight_layout(rect=(0, .04, 1, 1))
fig.savefig(f"{OUT}/02_fscore.png")
plt.close(fig)

# ---- 3. guard outcome breakdown ----------------------------------------------------------------
G = R["guard"]
g = [r for r in G if r["kind"] == "ghost"]
re_ = [r for r in G if r["kind"] == "real"]
v = [r for r in G if r["kind"] == "variant"]
cnt = lambda rows, f: sum(1 for r in rows if f(r))
groups = [
    ("Fake names\n(n=%d)" % len(g), [
        ("Refused", cnt(g, lambda r: r["action"] == "refuse"), "#2a78d6"),
        ("Asked “did you mean…?”", cnt(g, lambda r: r["action"] == "redirect"), "#8fb7ea"),
        ("Answered (swallowed)", cnt(g, lambda r: r["action"] == "rescue"), "#e34948")]),
    ("Real names\n(n=%d)" % len(re_), [
        ("Answered correctly + source", cnt(re_, lambda r: r["verdict"] == "correct"), "#2a78d6"),
        ("Declined / asked", cnt(re_, lambda r: r["verdict"] == "abstain"), "#b9b8b2"),
        ("Answered wrongly", cnt(re_, lambda r: r["verdict"] == "wrong"), "#e34948")]),
    ("Misspelled real names\n(n=%d)" % len(v), [
        ("Resolved, disclosed", cnt(v, lambda r: r["action"] == "rescue" and r["verdict"] == "correct"), "#2a78d6"),
        ("“Did you mean” → right one", cnt(v, lambda r: r["action"] == "redirect" and r["verdict"] == "correct"), "#8fb7ea"),
        ("Missed", cnt(v, lambda r: r["verdict"] == "abstain"), "#b9b8b2"),
        ("Wrong entity", cnt(v, lambda r: r["verdict"] == "wrong"), "#e34948")])]
fig, ax = plt.subplots(figsize=(11, 5.4), dpi=200)
for gi, (gl, segs) in enumerate(groups):
    tot = sum(c for _, c, _ in segs)
    left, small = 0, 0
    for lab, c, col in segs:
        w = 100 * c / tot
        if w > 0:
            ax.barh(gi, w, left=left, color=col, height=.5, edgecolor=SURFACE, linewidth=2)
            on_dark = col in ("#2a78d6", "#e34948")
            if w >= 16:   # fits inside: percentage + short label
                ax.text(left + w / 2, gi, f"{w:.0f}%", ha="center", va="bottom", fontsize=14, fontweight="bold", color="#fff" if on_dark else INK)
                ax.text(left + w / 2, gi + .03, lab, ha="center", va="top", fontsize=10, color="#fff" if on_dark else INK)
            else:         # too narrow: label above the bar, staggered so neighbours never collide
                y = gi - .30 - .2 * (small % 2)
                ax.text(left + w / 2, y, f"{w:.1f}% {lab}" if w < 5 else f"{w:.0f}% {lab}", ha="right" if left + w / 2 > 88 else "center",
                        va="bottom", fontsize=10, color=INK)
                small += 1
        left += w
ax.set_yticks(range(len(groups)), [gl for gl, _ in groups], fontsize=12.5, color=INK)
ax.invert_yaxis()
ax.set_xlim(0, 100)
ax.set_xlabel("share of test items (%)")
ax.spines["left"].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.set_title("What the guard actually does", loc="left", fontsize=17, fontweight="bold", pad=12)
fig.tight_layout()
fig.savefig(f"{OUT}/03_guard_outcomes.png")
plt.close(fig)

# ---- tables --------------------------------------------------------------------------------------
def pc(k, n):
    lo, hi = wilson(k, n)
    return f"{100*k/n:.1f}% [{100*lo:.1f}–{100*hi:.1f}]"


lines = ["| System | Fake names answered as real ↓ (HalluLens FAR) | Real names correct ↑ | Real names wrong ↓ | Not attempted | F-score ↑ |", "|---|---|---|---|---|---|"]
for k, n, _ in SYS:
    s = S[k]
    lines.append(f"| {n} | {pc(s['far'], s['ng'])} | {pc(s['cor'], s['nr'])} | {pc(s['inc'], s['nr'])} | {pc(s['nr']-s['cor']-s['inc'], s['nr'])} | **{100*s['F']:.1f}** |")
lines += ["", "By entity type (guard, real entities answered correctly):", "", "| Type | n | Correct |", "|---|---|---|"]
for t in ("writer", "book", "film"):
    rr = [r for r in re_ if r["type"] == t]
    lines.append(f"| {t} | {len(rr)} | {pc(sum(r['verdict']=='correct' for r in rr), len(rr))} |")
lines += ["", "Silent substitution (guard answered about a different entity than asked): "
          f"{sum(r['silent_sub'] for r in G)} of {len(G)} items = {100*sum(r['silent_sub'] for r in G)/len(G):.2f}%"]
open("results/tables.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
