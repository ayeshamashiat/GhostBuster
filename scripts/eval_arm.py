"""Run one arm on the test split and save raw outputs to results/<arm>.jsonl.

usage: python scripts/eval_arm.py c0|c1|c2 [tinker_checkpoint_path]
  c0 = base model, plain question
  c1 = base model + 'say you don't know if unsure' instruction
  c2 = fine-tuned model (needs a sampler checkpoint path as 2nd arg)
"""
import asyncio
import json
import os
import sys

import tinker
from dotenv import load_dotenv

from petnihunter.common import MODEL, chat_prompt, classify, sample_many

load_dotenv()
arm = sys.argv[1]
ckpt = sys.argv[2] if len(sys.argv) > 2 else None

C1_PREFIX = ("যদি তুমি নামটি সম্পর্কে নিশ্চিত না হও বা নামটি চেনো না, তাহলে স্পষ্ট বলো যে তুমি জানো না। "
             "অনুমান করে উত্তর দিয়ো না।\n\n")

rows = [json.loads(l) for l in open("data/dataset.jsonl", encoding="utf-8")]
test = [r for r in rows if r["split"] == "test"]


async def main():
    sc = tinker.ServiceClient(display_name=f"petnihunter-{arm}")
    if arm == "c2":
        client = await sc.create_sampling_client_async(model_path=ckpt)
    else:
        client = await sc.create_sampling_client_async(base_model=MODEL)
    prefix = C1_PREFIX if arm == "c1" else ""
    prompts = [chat_prompt(prefix + r["question"]) for r in test]
    outs = await sample_many(client, prompts)
    os.makedirs("results", exist_ok=True)
    with open(f"results/{arm}.jsonl", "w", encoding="utf-8") as f:
        for r, o in zip(test, outs):
            verdict = classify(r["kind"], r["type"], r.get("gold", ""), o)
            f.write(json.dumps({**r, "arm": arm, "output": o, "verdict": verdict}, ensure_ascii=False) + "\n")
    print("done", arm, len(test))


asyncio.run(main())
