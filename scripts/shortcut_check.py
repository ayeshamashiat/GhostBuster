"""Can a name-shape classifier (char n-grams only, no knowledge) separate real from ghost names?
High AUC => ghosts are detectable by style => a fine-tune could cheat. Reported honestly either way."""
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import make_pipeline

rows = [json.loads(l) for l in open("data/dataset.jsonl", encoding="utf-8")]
rows = [r for r in rows if r["kind"] in ("real", "ghost")]
mk = lambda: make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 3)), LogisticRegression(max_iter=1000))

for typ in ("writer", "book", "film"):
    for src in ("invented", "recombined"):
        sub = [r for r in rows if r["type"] == typ and (r["kind"] == "real" or r.get("source") == src)]
        X, y = [r["bn"] for r in sub], [int(r["kind"] == "ghost") for r in sub]
        p = cross_val_predict(mk(), X, y, cv=5, method="predict_proba")[:, 1]
        print(f"{typ:6s} real vs {src:10s} 5-fold AUC (name shape only): {roc_auc_score(y, p):.3f}  n={len(sub)}")

tr = [r for r in rows if r["type"] in ("writer", "book")]
te = [r for r in rows if r["type"] == "film"]
m = mk().fit([r["bn"] for r in tr], [int(r["kind"] == "ghost") for r in tr])
print("train writer+book -> test film AUC: %.3f" % roc_auc_score([int(r["kind"] == "ghost") for r in te], m.predict_proba([r["bn"] for r in te])[:, 1]))
# length baseline
import statistics as st
for typ in ("writer", "book", "film"):
    for k in ("real", "ghost"):
        L = [len(r["bn"]) for r in rows if r["type"] == typ and r["kind"] == k]
        print(f"  {typ} {k} mean name length {st.mean(L):.1f}")
