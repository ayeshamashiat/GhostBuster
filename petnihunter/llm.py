"""Tiny synchronous wrapper around the Tinker base model (Qwen3.5-4B), used for free-form extraction
and for the 'raw model' panel in the demo. Needs TINKER_API_KEY in the environment or .env."""
import asyncio
import threading

from petnihunter.common import MODEL, chat_prompt

_loop = None
_client = None
_lock = threading.Lock()


def _ensure_loop():
    global _loop
    with _lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, daemon=True).start()
    return _loop


async def _get_client():
    global _client
    if _client is None:
        from dotenv import load_dotenv
        import tinker
        load_dotenv()
        sc = tinker.ServiceClient(display_name="petnihunter-app")
        _client = await sc.create_sampling_client_async(base_model=MODEL)
    return _client


async def _complete(prompt, max_tokens):
    import tinker
    client = await _get_client()
    tok = client.get_tokenizer()
    r = await client.sample_async(
        prompt=tinker.types.ModelInput.from_ints(tok.encode(chat_prompt(prompt))), num_samples=1,
        sampling_params=tinker.types.SamplingParams(max_tokens=max_tokens, temperature=0.0, stop=["<|im_end|>"]))
    return tok.decode(r.sequences[0].tokens).replace("<|im_end|>", "").strip()


def complete(prompt, max_tokens=160, timeout=60):
    """Ask the base model one question; returns its raw answer text."""
    fut = asyncio.run_coroutine_threadsafe(_complete(prompt, max_tokens), _ensure_loop())
    return fut.result(timeout)


def translate(text, max_tokens=300):
    """Machine-translate Bangla to English with the base model (used for display only)."""
    return complete("Translate this Bangla text into English. Reply with only the translation, nothing else.\n\n" + text,
                    max_tokens=max_tokens)
