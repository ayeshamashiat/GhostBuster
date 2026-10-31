"""PetniHunter: a guard that catches ghost (invented) entities in Bangla Q&A and acts on them.

    from petnihunter import answer
    answer("'নিশিগন্ধার দিনলিপি' উপন্যাসটি কে লিখেছেন?")
    # -> {"action": "refuse", "text": "...খুঁজে পাইনি, তাই অনুমান করে উত্তর দিচ্ছি না।", ...}
"""


def answer(question: str) -> dict:
    from petnihunter.guard import answer as _answer
    return _answer(question)
