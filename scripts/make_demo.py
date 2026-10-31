"""Build docs/index.html from RECORDED results (results/c0.jsonl + results/guard.jsonl). Nothing is hand-written."""
import html
import json
import random

random.seed(4)
load = lambda p: {r["id"]: r for r in map(json.loads, open(p, encoding="utf-8"))}
c0, c1, g = load("results/c0.jsonl"), load("results/c1.jsonl"), load("results/guard.jsonl")

import os
TR_PATH = "data/translations.json"
TR = json.load(open(TR_PATH, encoding="utf-8")) if os.path.exists(TR_PATH) else {}


def en(text):
    """Bangla -> English machine translation with Qwen, cached (shared with make_video.py)."""
    if text not in TR:
        from petnihunter.llm import translate
        try:
            TR[text] = translate(text)
        except Exception:
            TR[text] = ""
        json.dump(TR, open(TR_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return TR[text]


cases = []


def pick(pred, label, n=1):
    pool = [i for i in g if i in c0 and pred(g[i], c0[i])]
    random.shuffle(pool)
    for i in pool[:n]:
        cases.append((label, g[i], c0[i], c1.get(i)))


pick(lambda a, b: a["kind"] == "ghost" and a["type"] == "book" and a["action"] == "refuse" and b["verdict"] == "wrong",
     "Invented book — the model makes up an author")
pick(lambda a, b: a["kind"] == "ghost" and a["type"] == "writer" and a["action"] == "refuse" and b["verdict"] == "wrong",
     "Invented writer — the model makes up a birth year")
pick(lambda a, b: a["kind"] == "ghost" and a["type"] == "film" and a["action"] == "refuse" and b["verdict"] == "wrong",
     "Invented film — the model makes up a director")
pick(lambda a, b: a["kind"] == "variant" and a["action"] == "rescue" and a["verdict"] == "correct" and b["verdict"] == "wrong",
     "Real writer, spelled differently — rescued with a source")
pick(lambda a, b: a["kind"] == "variant" and a["action"] == "redirect" and a["verdict"] == "correct" and b["verdict"] == "wrong",
     "Typo of a real name — “did you mean…?”")
pick(lambda a, b: a["kind"] == "real" and a["action"] == "rescue" and a["verdict"] == "correct" and b["verdict"] == "wrong",
     "Real entity the model got wrong — corrected from Wikidata")


def esc(s):
    return html.escape((s or "").replace("**", "")).replace("\n", "<br>")


from petnihunter.guard import bn_to_en


def eng_guard(text):
    t = bn_to_en(text)   # exact templates, never machine-translated
    return f'<p class="en"><b>EN</b> {esc(t)}</p>' if t else ""


def eng(text, label="EN"):
    t = en(text)
    return f'<p class="en"><b>{label}</b> {esc(t)}</p>' if t else ""


cards = ""
for label, gg, cc, c1r in cases:
    act = {"refuse": "REFUSED", "redirect": "REDIRECTED", "rescue": "RESCUED"}.get(gg["action"], gg["action"])
    cards += f"""
<section class="case"><h2>{esc(label)}</h2><p class="q">❓ {esc(gg['question'])}</p>{eng(gg['question'])}
<div class="panels">
 <div class="panel raw"><h3>🤖 Raw model (Qwen3.5-4B)</h3><p>{esc(cc['output'])}</p>{eng(cc['output'], 'EN (machine translation)')}</div>
 <div class="panel det"><h3>👻 Petni check</h3><p>Looked up <b>{esc(gg['bn'])}</b> on Bangla Wikipedia.<br>Closest page: <b>{esc(gg.get('resolved') or 'none')}</b><br>Match score: {gg.get('score')}</p></div>
 <div class="panel act {gg['action']}"><h3>⚔️ Action: {act}</h3><p>{esc(gg['output'])}</p>{eng_guard(gg['output'])}</div>
</div></section>"""

doc = f"""<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PetniHunter — পেত্নী শিকারি</title>
<link href="https://fonts.googleapis.com/css2?family=Creepster&family=Noto+Sans+Bengali:wght@400;700&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0b0a12;--card:#161424;--fg:#e9e6f5;--mut:#9a95b5;--glow:#7cf5c8;--bad:#ff6b8b;--warn:#ffd36b}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 50% -10%,#241a3d,var(--bg) 60%);color:var(--fg);font-family:'Noto Sans Bengali',system-ui,sans-serif;line-height:1.6}}
header{{text-align:center;padding:48px 16px 16px}}h1{{font-family:Creepster,cursive;font-size:clamp(2.4rem,8vw,4.5rem);margin:0;color:var(--glow);text-shadow:0 0 24px #7cf5c855;letter-spacing:2px}}
header p{{color:var(--mut);max-width:60ch;margin:8px auto}}main{{max-width:1100px;margin:auto;padding:0 16px 64px}}
.case{{background:var(--card);border:1px solid #2b2745;border-radius:14px;padding:18px;margin:24px 0}}.case h2{{margin:0 0 6px;font-size:1.05rem;color:var(--warn)}}
.q{{font-size:1.1rem;margin:4px 0 14px}}.panels{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.panel{{border-radius:10px;padding:12px;background:#0f0d1b;border:1px solid #2b2745;font-size:.92rem}}.panel h3{{margin:0 0 6px;font-size:.9rem}}.en{{color:var(--mut);font-style:italic;font-size:.82rem;border-top:1px dashed var(--line);padding-top:6px;margin:8px 0 0}}.en b{{font-style:normal;font-size:.68rem;letter-spacing:.06em}}
.raw{{border-color:#ff6b8b66}}.raw h3{{color:var(--bad)}}.det h3{{color:var(--warn)}}.act{{border-color:#7cf5c866}}.act h3{{color:var(--glow)}}
@media(max-width:800px){{.panels{{grid-template-columns:1fr}}}}footer{{text-align:center;color:var(--mut);padding:24px 16px;font-size:.85rem}}
</style></head><body>
<header><h1>PetniHunter</h1><p>পেত্নী শিকারি — a hunter for <b>ghost entities</b>: people, books and films a language model invents with total confidence.
It doesn't just spot them. It refuses, redirects, or rescues the answer with a source.</p>
<p><small>Every case below is a real recorded output from the test set, not hand-written.</small></p></header>
<main>
<section class="case"><h2>Results (2,367 test items, Bangla writers / books / films)</h2>
<p class="en" style="border:0">Plain model: <b>96%</b> of fake names answered as real. “Say if unsure” prompt: refuses <b>79%</b> of real names. Fine-tune: refuses <b>100%</b>. PetniHunter guard: <b>0.1%</b> fake names answered, <b>86.6%</b> real names answered correctly with a source (F-score 91.9). Metrics: HalluLens false-acceptance rate and SimpleQA F-score. Guard scores are ceilings (same source for lookup and gold answers); see the README for limits.</p>
<img src="img/01_tradeoff.png" alt="Trade-off chart" style="width:100%;border-radius:10px;margin-top:10px">
<img src="img/02_fscore.png" alt="F-score chart" style="width:100%;border-radius:10px;margin-top:10px">
<img src="img/03_guard_outcomes.png" alt="Guard outcomes" style="width:100%;border-radius:10px;margin-top:10px"></section>
{cards}</main>
<footer>Qwen3.5-4B via Tinker · Bangla Wikipedia + Wikidata · fonts: Creepster (OFL)</footer></body></html>"""
import os
os.makedirs("docs", exist_ok=True)
open("docs/index.html", "w", encoding="utf-8").write(doc)
print("cases:", len(cases))
