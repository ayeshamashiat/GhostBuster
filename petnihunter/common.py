"""Shared helpers: question templates, answer checking, refusal detection, Tinker sampling."""
import asyncio
import re
import unicodedata

# ---- question templates (A = used in training, B = held-out phrasing) -------------------
TEMPLATES = {
    "writer": {"A": "{n} কোন সালে জন্মগ্রহণ করেন?", "B": "{n}-এর জন্মসাল কত?"},
    "book": {"A": "'{n}' বইটি কে লিখেছেন?", "B": "'{n}'-এর লেখক কে?"},
    "film": {"A": "'{n}' চলচ্চিত্রের পরিচালক কে?", "B": "'{n}' ছবিটি কে পরিচালনা করেছেন?"},
}


def question(typ, name, phr="A"):
    return TEMPLATES[typ][phr].format(n=name)


# ---- refusal text used as fine-tuning target and by the guard ---------------------------
REFUSALS = [
    "দুঃখিত, এই নামে কোনো তথ্য আমি নিশ্চিতভাবে জানি না। ভুল তথ্য দেওয়ার চেয়ে আমি স্বীকার করছি যে আমি জানি না।",
    "আমি এই বিষয়টি সম্পর্কে নিশ্চিত নই এবং এ নামে কিছু খুঁজে পাইনি। অনুমান করে উত্তর দিলে ভুল হতে পারে।",
    "এই নামের কোনো নির্ভরযোগ্য তথ্য আমার কাছে নেই, তাই আমি উত্তর দিতে পারছি না।",
]

# ---- abstain detector -------------------------------------------------------------------
ABSTAIN_PATTERNS = [
    r"জানি না", r"নিশ্চিত নই", r"নিশ্চিতভাবে (?:জানি|বলতে)", r"তথ্য (?:নেই|পাওয়া যায়নি|পাইনি)",
    r"খুঁজে পাইনি", r"খুঁজে পাওয়া যায়নি", r"কোনো (?:নির্ভরযোগ্য )?(?:তথ্য|উল্লেখ)",
    r"কাল্পনিক", r"অস্তিত্ব(?:ই)? (?:নেই|নেই)", r"বলতে পারছি না", r"উত্তর দিতে পারছি না",
    r"পরিচিত (?:নয়|নই)", r"সম্ভবত ভুল", r"কোনো.{0,20}নেই",
    r"I (?:don't|do not) (?:know|have)", r"not sure", r"cannot (?:find|verify)",
]
_ABSTAIN = re.compile("|".join(ABSTAIN_PATTERNS), re.I)


def is_abstain(text: str) -> bool:
    return bool(_ABSTAIN.search(text or ""))


# ---- answer checker ---------------------------------------------------------------------
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
# fold common Bangla spelling variants so হুমায়ূন == হুমায়ুন, শ/ষ/স treated alike
_FOLD = str.maketrans({"\u09c0": "\u09bf", "\u09c2": "\u09c1", "\u09b7": "\u09b8", "\u09b6": "\u09b8",
                       "\u09a3": "\u09a8", "\u09ce": "\u09a4"})


def fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s).replace("\u09bc", "").replace("\u09cd", "")  # drop nukta + hasanta
    s = s.translate(_BN_DIGITS).translate(_FOLD)
    return re.sub(r"[^\w\u0980-\u09FF]+", " ", s).strip().lower()


def is_correct(typ: str, gold: str, text: str) -> bool:
    if not text:
        return False
    t = fold(text)
    if typ == "writer":
        return fold(gold) in re.findall(r"\d{3,4}", t)
    toks = [x for x in fold(gold).split() if len(x) >= 2]
    if not toks:
        return False
    hit = sum(1 for x in toks if x in t)
    return hit / len(toks) >= 0.5 and toks[-1] in t


def classify(kind: str, typ: str, gold: str, text: str) -> str:
    """kind: real | ghost | variant (gold = the real entity's gold).
    returns 'abstain' | 'correct' | 'wrong'  (for ghosts, anything not abstain is 'wrong')."""
    if is_abstain(text):
        return "abstain"
    if kind == "ghost":
        return "wrong"
    return "correct" if is_correct(typ, gold, text) else "wrong"


# ---- Tinker sampling --------------------------------------------------------------------
MODEL = "Qwen/Qwen3.5-4B"


def chat_prompt(user: str) -> str:
    return f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


async def sample_many(client, prompts, max_tokens=160, temperature=0.0, concurrency=24):
    import tinker
    tok = client.get_tokenizer()
    sem = asyncio.Semaphore(concurrency)
    params = tinker.types.SamplingParams(max_tokens=max_tokens, temperature=temperature, stop=["<|im_end|>"])

    async def one(p):
        async with sem:
            for attempt in range(4):
                try:
                    r = await client.sample_async(
                        prompt=tinker.types.ModelInput.from_ints(tok.encode(p)),
                        num_samples=1, sampling_params=params)
                    return tok.decode(r.sequences[0].tokens).replace("<|im_end|>", "").strip()
                except Exception as e:  # transient API errors
                    if attempt == 3:
                        return f"[ERROR {type(e).__name__}]"
                    await asyncio.sleep(2 * (attempt + 1))

    return await asyncio.gather(*[one(p) for p in prompts])
