"""Build video/petnihunter.mp4: silent, English-captioned, from REAL recorded outputs.

scenes (HTML) -> PNG via headless Chrome -> per-scene mp4 with fades -> concat.
Demo cases come from results/c0.jsonl + results/guard.jsonl; numbers from results/summary.md.
Bangla->English for raw model answers is machine translation (cached in data/translations.json).
"""
import html
import json
import os
import random
import re
import subprocess
import sys

random.seed(8)
from petnihunter.guard import bn_to_en
W, H = 1920, 1080
OUT = "video"
os.makedirs(f"{OUT}/scenes", exist_ok=True)

# ---------- recorded data ----------
load = lambda p: {r["id"]: r for r in map(json.loads, open(p, encoding="utf-8"))}
c0 = load("results/c0.jsonl")
guard = load("results/guard.jsonl" if os.path.exists("results/guard.jsonl") else "results/guard_v1.jsonl")
TR_PATH = "data/translations.json"
TR = json.load(open(TR_PATH, encoding="utf-8")) if os.path.exists(TR_PATH) else {}


def en(text):
    """machine-translate Bangla->English with Qwen (cached)"""
    if text not in TR:
        from petnihunter.llm import translate
        try:
            TR[text] = translate(text)
        except Exception:
            TR[text] = ""
        json.dump(TR, open(TR_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return TR[text]


def pick(pred):
    pool = [i for i in guard if i in c0 and pred(guard[i], c0[i])]
    random.shuffle(pool)
    return pool[0]


CASES = [
    ("An invented book", pick(lambda g, c: g["kind"] == "ghost" and g["type"] == "book" and g["action"] == "refuse" and c["verdict"] == "wrong" and len(c["output"]) < 260)),
    ("A typo of a real name", pick(lambda g, c: g["kind"] == "variant" and g["action"] == "redirect" and g["verdict"] == "correct" and len(c["output"]) < 260)),
    ("A real writer the model gets wrong", pick(lambda g, c: g["kind"] == "real" and g["type"] == "writer" and g["action"] == "rescue" and g["verdict"] == "correct" and c["verdict"] == "wrong" and len(c["output"]) < 260)),
]

# ---------- html helpers ----------
CSS = """
:root{--bg:#0b0a12;--card:#161424;--line:#2b2745;--fg:#e9e6f5;--mut:#9a95b5;--glow:#7cf5c8;--bad:#ff6b8b;--warn:#ffd36b}
*{box-sizing:border-box}html,body{margin:0;width:1920px;height:1080px}
body{background:radial-gradient(circle at 50% -10%,#2b1f4a,#0b0a12 62%);color:var(--fg);font-family:'Noto Sans Bengali','Noto Sans',sans-serif;display:flex;flex-direction:column;justify-content:center;padding:50px 130px 130px}
h1{font-family:Creepster,'Noto Sans',cursive;font-size:190px;margin:0;color:var(--glow);text-shadow:0 0 40px #7cf5c866;letter-spacing:6px;text-align:center}
h2{font-size:64px;margin:0 0 34px;color:var(--warn)}
.sub{font-size:44px;color:var(--mut);text-align:center;margin-top:20px}.big{font-size:52px;line-height:1.45}
.cap{position:absolute;left:0;right:0;bottom:46px;text-align:center;font-size:36px;color:var(--mut)}
.card{background:var(--card);border:2px solid var(--line);border-radius:24px;padding:30px 38px;margin:14px 0}
.bn{font-size:44px;line-height:1.5}.e{font-size:32px;color:var(--mut);font-style:italic;margin-top:8px}
.bad{border-color:#ff6b8b99}.good{border-color:#7cf5c8aa}.warn{border-color:#ffd36b99}
.lab{font-size:28px;letter-spacing:.08em;margin-bottom:10px;font-weight:700}.bad .lab{color:var(--bad)}.good .lab{color:var(--glow)}.warn .lab{color:var(--warn)}
table{border-collapse:collapse;width:100%;font-size:36px}td,th{padding:16px 20px;border-bottom:2px solid var(--line);text-align:left}th{color:var(--mut);font-size:28px}
.hl{color:var(--glow);font-weight:700}.red{color:var(--bad)}pre{background:#0f0d1b;border:2px solid var(--line);border-radius:18px;padding:26px;font-size:27px;line-height:1.42;color:#cfe;overflow:hidden;font-family:'DejaVu Sans Mono',monospace}
.flow{display:flex;align-items:stretch;gap:18px;margin:20px 0}.box{flex:1;background:var(--card);border:2px solid var(--line);border-radius:20px;padding:22px;font-size:34px;text-align:center}
.arrow{align-self:center;font-size:56px;color:var(--glow)}
"""


def page(body, caption=""):
    cap = f'<div class="cap">{html.escape(caption)}</div>' if caption else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>@import url('https://fonts.googleapis.com/css2?family=Creepster&family=Noto+Sans+Bengali:wght@400;700&display=swap');{CSS}</style></head><body>{body}{cap}</body></html>"""


E = html.escape


def bnen(bn, e_text, cls="", label=""):
    return f'<div class="card {cls}"><div class="lab">{label}</div><div class="bn">{E(bn.replace("**", "")).replace(chr(10), "<br>")}</div><div class="e">{E(e_text)}</div></div>'


scenes = []  # (name, html, seconds)

# 1 title
scenes.append(("01_title", page('<h1>PetniHunter</h1><div class="sub">পেত্নী শিকারি · Hunting ghost entities in Bangla AI</div><div class="sub" style="font-size:36px">A model invents a book. We catch it, and act.</div>'), 4))

# 2 problem
c = c0[CASES[0][1]]
scenes.append(("02_problem", page(
    "<h2>The problem</h2>" + bnen(c["question"], en(c["question"]), "warn", "I ASKED ABOUT A BOOK THAT DOES NOT EXIST") +
    bnen(c["output"], en(c["output"]), "bad", "🤖 QWEN3.5-4B ANSWERS, CONFIDENTLY (machine translation below)"),
    "No hint of doubt. This kind of made-up answer is called a hallucination."), 9))

# 3 numbers
scenes.append(("03_scale", page(
    "<h2>How often?</h2><div class='big'>We invented <span class='hl'>929</span> fake Bangla writers, books and films.<br>The plain model answered <span class='red'>96%</span> of them as if they were real.</div>"
    "<div class='sub' style='text-align:left;margin-top:30px'>Same failure rate as Mistral-7B on English (94.7%, HalluLens).</div>",
    "Metric: False Acceptance Rate (HalluLens NonExistentRefusal)"), 8))

# 4 naive fixes fail
scenes.append(("04_fixes", page(
    "<h2>The obvious fixes don't work</h2><table><tr><th>Fix</th><th>Fake names answered</th><th>Real names refused</th></tr>"
    "<tr><td>Prompt: “say if unsure”</td><td>18.2%</td><td class='red'>79.3%</td></tr>"
    "<tr><td>Fine-tune it to say “I don't know”</td><td>0.0%</td><td class='red'>100%</td></tr></table>"
    "<div class='big' style='margin-top:30px'>The 4B model knows almost nothing about real obscure Bangla names, so it learns to refuse everything.</div>",
    "A model that never answers has no hallucinations, and no use."), 9))

# 5 three actions
scenes.append(("05_actions", page(
    "<h2>PetniHunter doesn't just detect. It acts.</h2><div class='flow'>"
    "<div class='box'>🛑<br><b>REFUSE</b><br>nothing like it exists:<br>“I won't guess.”</div>"
    "<div class='box'>❓<br><b>REDIRECT</b><br>close to a real one:<br>“Did you mean…?”</div>"
    "<div class='box'>✅<br><b>RESCUE</b><br>it exists: answer from<br>Wikidata, with a source</div></div>",
    "It never silently answers about a different entity."), 7))

# 6 pipeline
scenes.append(("06_pipeline", page(
    "<h2>How it works</h2><div class='flow'><div class='box'>1. Read the question<br><small>Qwen extracts name + what's asked</small></div><div class='arrow'>→</div>"
    "<div class='box'>2. Search<br><small>Bangla Wikipedia, spelling-tolerant</small></div><div class='arrow'>→</div>"
    "<div class='box'>3. Check<br><small>title match + right kind of entity (Wikidata)</small></div><div class='arrow'>→</div>"
    "<div class='box'>4. Act<br><small>refuse · redirect · rescue</small></div></div>"
    "<div class='big'>Open source end to end: Qwen3.5-4B on Tinker, Bangla Wikipedia, Wikidata.</div>",
    "No retraining needed to add the guard to any Bangla chatbot."), 8))

# 7 code
src = open("petnihunter/guard.py", encoding="utf-8").read()
m = re.search(r"def decide\(name, typ\):.*?(?=\n\ndef answer)", src, re.S)
code = "\n".join(m.group(0).splitlines()[:16]) if m else "# see petnihunter/guard.py"
scenes.append(("07_code", page(f"<h2>Implementation</h2><pre>{E(code)}</pre><div class='sub' style='font-size:36px'>from petnihunter import answer · one function, Python or web</div>",
                               "Excerpt: petnihunter/guard.py"), 9))

# 8–10 demo cases, 3 frames each (question -> raw -> action)
for n, (label, cid) in enumerate(CASES[:3], 1):
    g, c = guard[cid], c0[cid]
    q = bnen(g["question"], en(g["question"]), "warn", "❓ QUESTION")
    raw = bnen(c["output"], en(c["output"]), "bad", "🤖 RAW MODEL (machine translation below)")
    chk = (f'<div class="card warn"><div class="lab">👻 PETNI CHECK</div><div class="bn">closest Wikipedia page: {E(g.get("resolved") or "none")}</div>'
           f'<div class="e">match score {g.get("score")}</div></div>')
    verb = {"refuse": "🛑 REFUSED", "redirect": "❓ REDIRECTED", "rescue": "✅ RESCUED"}[g["action"]]
    act = bnen(g["output"], bn_to_en(g["output"]) or "", "good", "⚔️ ACTION: " + verb)
    head = f"<h2>Live example {n}: {E(label)}</h2>"
    scenes.append((f"08_{n}a", page(head + q), 2.5))
    scenes.append((f"08_{n}b", page(head + q + raw), 4))
    scenes.append((f"08_{n}c", page(head + q + chk + act, "Recorded output from the test set, not hand-written."), 5))

# 11 results (from results/tables.md: all 929 ghosts and 1,108 real entities, same numbers as the post)
rows = [l for l in open("results/tables.md", encoding="utf-8").read().splitlines()[2:6]][::-1]  # guard last


def cell(l, i):
    return [x.strip() for x in l.strip("|").split("|")][i]


tbl = "".join(f"<tr><td>{E(cell(l,0))}</td><td>{E(cell(l,1).split(' [')[0])}</td><td>{E(cell(l,2).split(' [')[0])}</td><td class='hl'>{E(cell(l,5).replace('*',''))}</td></tr>" for l in rows)
scenes.append(("11_results", page(
    "<h2>Results (2,367 test items)</h2><table><tr><th>System</th><th>Fake names answered as real ↓</th><th>Real names answered right ↑</th><th>F-score ↑</th></tr>" + tbl + "</table>",
    "Metrics: HalluLens false acceptance rate · SimpleQA correct / F-score. Guard scores are ceilings."), 9))

# 12 honest limits
scenes.append(("12_limits", page(
    "<h2>Honest limits</h2><div class='big'>• The guard's answers and its test data both come from Wikipedia/Wikidata, so scores are <b>ceilings</b>.<br>"
    "• Writers, books and films only; needs internet.<br>• Fine-tuning alone failed, and I'm reporting that.<br>• Common names (homonyms) are the hard case, so it asks instead of guessing.</div>",
    "Everything reproducible from the repo."), 9))

# 13 outro
scenes.append(("13_outro", page('<h1 style="font-size:150px">PetniHunter</h1><div class="sub">Built for the Hacktoberfest “Ghost in the Machine” challenge</div><div class="sub" style="font-size:36px">Qwen3.5-4B · Tinker · Bangla Wikipedia · Wikidata · open source</div>'), 4))

# ---------- render ----------
CHROME = "google-chrome"
clips = []
only = sys.argv[1:]  # optionally render only some scene names
for name, doc, secs in scenes:
    hp, pp, vp = f"{OUT}/scenes/{name}.html", f"{OUT}/scenes/{name}.png", f"{OUT}/scenes/{name}.mp4"
    open(hp, "w", encoding="utf-8").write(doc)
    if not only or name in only:
        subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--hide-scrollbars", f"--window-size={W},{H}",
                        "--virtual-time-budget=6000", f"--screenshot={os.path.abspath(pp)}", "file://" + os.path.abspath(hp)],
                       check=True, capture_output=True)
        fade = min(0.35, secs / 4)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", pp, "-t", str(secs), "-vf",
                        f"fade=t=in:st=0:d={fade},fade=t=out:st={secs-fade}:d={fade},format=yuv420p", "-r", "30", "-c:v", "libx264", "-preset", "fast", vp], check=True)
    clips.append(vp)

with open(f"{OUT}/list.txt", "w") as f:
    for c in clips:
        f.write(f"file '{os.path.abspath(c)}'\n")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", f"{OUT}/list.txt", "-c", "copy", f"{OUT}/petnihunter.mp4"], check=True)
tot = sum(s for _, _, s in scenes)
print(f"video/petnihunter.mp4  ~{tot:.0f}s, {len(scenes)} scenes")
