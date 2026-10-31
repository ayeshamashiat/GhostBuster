"""Gate 0: does Qwen3.5-4B (via Tinker) read and write Bangla, and what does it do with ghosts?

Asks the base model a handful of Bangla questions: some real, some invented.
Prints answers so a human can eyeball them. No metrics here, this is a smoke test.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()
if not os.environ.get("TINKER_API_KEY"):
    sys.exit("TINKER_API_KEY not set (put it in .env)")

import tinker  # noqa: E402

MODEL = "Qwen/Qwen3.5-4B"

QUESTIONS = [
    ("real", "রবীন্দ্রনাথ ঠাকুর কোন সালে নোবেল পুরস্কার পেয়েছিলেন?"),
    ("real", "'পথের পাঁচালী' উপন্যাসটি কে লিখেছেন?"),
    ("real", "কাজী নজরুল ইসলাম কোন দেশের জাতীয় কবি?"),
    ("ghost", "'নিশিগন্ধার দিনলিপি' উপন্যাসটি কে লিখেছেন?"),
    ("ghost", "ড. আনিসুজ্জামান কবিরাজ কোন সালে জন্মগ্রহণ করেন?"),
    ("ghost", "'ধূসর নদীর ওপারে' চলচ্চিত্রের পরিচালক কে?"),
]


def build_prompt(tokenizer, question: str) -> str:
    # Qwen chat format, thinking switched off with an empty think block.
    return (
        "<|im_start|>user\n" + question + "<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


async def main():
    sc = tinker.ServiceClient(display_name="petnihunter-gate0")
    client = await sc.create_sampling_client_async(base_model=MODEL)
    tok = client.get_tokenizer()
    params = tinker.types.SamplingParams(max_tokens=200, temperature=0.0)
    for kind, q in QUESTIONS:
        ids = tok.encode(build_prompt(tok, q))
        res = await client.sample_async(
            prompt=tinker.types.ModelInput.from_ints(ids),
            num_samples=1,
            sampling_params=params,
        )
        print(f"[{kind}] {q}\n  -> {tok.decode(res.sequences[0].tokens).strip()}\n")


asyncio.run(main())
