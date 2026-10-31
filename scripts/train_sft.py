"""Step 5: fine-tune Qwen3.5-4B (LoRA, on Tinker) to admit ignorance — R-Tuning style.

1. Ask the BASE model every training question. Real items it answers correctly keep the true answer as the
   target; real items it gets wrong, and all ghosts, get a Bangla 'I don't know' target.
2. LoRA SFT on those targets (completion-only loss).
3. Save sampler weights; write the path to results/c2_path.txt.
Only writer + book items are used. Films are never seen (held-out type). Phrasing B is never seen.
usage: python scripts/train_sft.py [epochs] [--english-only-ablation]   (ablation is not implemented)
"""
import asyncio
import json
import os
import random
import sys

import numpy as np
import tinker
from dotenv import load_dotenv

from petnihunter.common import MODEL, REFUSALS, chat_prompt, classify, sample_many

load_dotenv()
random.seed(3)
EPOCHS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BATCH, LR = 32, 2e-4

rows = [json.loads(l) for l in open("data/dataset.jsonl", encoding="utf-8")]
train = [r for r in rows if r["split"] == "train" and r["kind"] in ("real", "ghost")]


def true_answer(r):
    if r["type"] == "writer":
        return f"{r['bn']} {r['gold']} সালে জন্মগ্রহণ করেন।"
    return f"'{r['bn']}' বইটির লেখক {r['gold']}।"


async def label_known(sc):
    path = "data/train_labeled.jsonl"
    if os.path.exists(path):
        return [json.loads(l) for l in open(path, encoding="utf-8")]
    client = await sc.create_sampling_client_async(base_model=MODEL)
    outs = await sample_many(client, [chat_prompt(r["question"]) for r in train])
    labeled = []
    for r, o in zip(train, outs):
        verdict = classify(r["kind"], r["type"], r.get("gold", ""), o)
        labeled.append({**r, "base_output": o, "base_verdict": verdict})
    with open(path, "w", encoding="utf-8") as f:
        for r in labeled:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return labeled


async def main():
    sc = tinker.ServiceClient(display_name="petnihunter-train")
    labeled = await label_known(sc)
    examples = []
    n_known = n_unknown = n_ghost = 0
    for r in labeled:
        if r["kind"] == "real" and r["base_verdict"] == "correct":
            target, n_known = true_answer(r), n_known + 1
        elif r["kind"] == "real":
            target, n_unknown = random.choice(REFUSALS), n_unknown + 1
        else:
            target, n_ghost = random.choice(REFUSALS), n_ghost + 1
        examples.append((chat_prompt(r["question"]), target))
    print(f"targets: known-real answers={n_known}, unknown-real refusals={n_unknown}, ghost refusals={n_ghost}")

    tc = await sc.create_lora_training_client_async(base_model=MODEL, rank=16)
    tok = tc.get_tokenizer()

    def to_datum(prompt, target):
        p = tok.encode(prompt)
        c = tok.encode(target + "<|im_end|>")
        toks = p + c
        w = [0.0] * len(p) + [1.0] * len(c)
        return tinker.types.Datum(
            model_input=tinker.types.ModelInput.from_ints(toks[:-1]),
            loss_fn_inputs={"target_tokens": toks[1:], "weights": w[1:]})

    data = [to_datum(p, t) for p, t in examples]
    steps = 0
    for ep in range(EPOCHS):
        random.shuffle(data)
        for i in range(0, len(data), BATCH):
            batch = data[i:i + BATCH]
            fb = await tc.forward_backward_async(batch, "cross_entropy")
            op = await tc.optim_step_async(tinker.AdamParams(learning_rate=LR))
            res = await fb.result_async()
            await op.result_async()
            steps += 1
            if steps % 10 == 0:
                lp = res.loss_fn_outputs[0]["logprobs"] if hasattr(res, "loss_fn_outputs") else None
                print(f"epoch {ep} step {steps}", flush=True)
    sampler = await tc.save_weights_for_sampler_async(name="petnihunter-c2")
    path = (await sampler.result_async()).path
    os.makedirs("results", exist_ok=True)
    open("results/c2_path.txt", "w").write(path)
    print("saved sampler weights:", path)


asyncio.run(main())
