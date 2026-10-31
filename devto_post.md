---
title: "PetniHunter: I Invented 929 Fake Bangla Books, Films and Writers. A 4B Model Believed 96% of Them."
published: false
tags: devchallenge, hf26challenge, ai, python
cover_image: https://raw.githubusercontent.com/ayeshamashiat/PetniHunter/main/docs/img/01_tradeoff.png
---

*This is my submission for the DEV Hacktoberfest "Ghost in the Machine" challenge.*

I made up a Bengali film called **ধূসর নদীর ওপারে** ("Beyond the Grey River"). It does not exist. I asked an open-weight model, Qwen3.5-4B, who directed it.

> "The director was **Satyajit Ray**. It was released in 1958, and it starred Sumitra Mitra, Tarun Mitra and Shibajit Chattopadhyay."

No hesitation, a year, a cast. Every word of it is invented.

That is a **ghost entity**: a person, book or film that does not exist, but that a language model describes with total confidence. In Bangla, where there is far less text for models to learn from, the ghosts are everywhere. And the folklore I grew up with has a perfect name for a thing that looks like it is there but is not: the **পেত্নী** (*petni*), a ghost from Bengali stories.

So I built **PetniHunter**. It does not just *detect* ghosts. It **acts**.

{% embed VIDEO_URL_HERE %}

## What it does

You ask about a Bangla writer's birth year, a book's author, or a film's director. PetniHunter checks the entity against Bangla Wikipedia and Wikidata, then does one of three things:

| Situation | Action |
|---|---|
| The thing does not exist | 🛑 **Refuse**: "I found nothing reliable, so I will not guess." |
| It is close to something real (a typo, a spelling variant) | ❓ **Redirect**: "Did you mean *X*?" It never quietly answers about *X*. |
| It exists | ✅ **Rescue**: answers from Wikidata, cites the source, and says which page it used. |

- **Live demo:** LIVE_DEMO_URL_HERE
- **Code:** https://github.com/ayeshamashiat/PetniHunter

You can type a question in your own words. A small Qwen call pulls out the name and what you are asking; the rest is a lookup. The page shows the raw model's answer, the Wikipedia check and the action side by side, with English translations.

## First, how bad is it?

I built a test set from Wikidata: real Bangla writers, books and Bengali-language films, plus **929 invented ones**. The invented names came from two sources, following Meta's [HalluLens](https://arxiv.org/abs/2504.17550) benchmark: names a model invented (*GeneratedEntities*), and names I spliced from parts of two real ones (*MixedEntities*). Any name that matched a real Bangla Wikipedia page was thrown out.

I then measured the **False Acceptance Rate**, the share of ghosts the system answered as if they were real. I used HalluLens's definition so the number means something outside this project.

**The plain model accepted 96.3% of the ghosts.** For comparison, HalluLens reports 94.7% for Mistral-7B on English. Same ballpark.

It is not only the ghosts. Asked who wrote the real novel *Pather Panchali*, it said Rabindranath Tagore. (It is Bibhutibhushan Bandyopadhyay.) Of the real entities in my test set, the plain model got **3.7%** right.

## Two obvious fixes, and why they both failed

**Fix 1: tell it to admit when it is unsure.** The fake-name rate fell to 18.2%. But the model now refused **79.3% of real entities**. It had learned to say "I don't know" about nearly everything.

**Fix 2: fine-tune it to say "I don't know".** I used a refusal-aware recipe in the style of [R-Tuning](https://arxiv.org/abs/2311.09677): ask the base model every training question, keep the true answer where it was right, and train on "I don't know" everywhere else. I ran LoRA fine-tuning on **Tinker**.

Result: **0.0% fake names accepted, 100% of real names refused.** A model that never answers has no hallucinations. It also has no use.

Why? Of 2,427 training targets, only **35** were real answers the base model actually knew. A 4B model knows almost nothing about obscure Bangla writers, so there was nothing to teach it to tell "I know this" from "I don't." Refusing everything was the best it could do. I did not expect this, and I am reporting it because it is the most useful result in the project.

This is why the scoreboard needs two sides. I used the [SimpleQA](https://arxiv.org/abs/2411.04368) F-score, which combines "how many did you get right" with "how many of your answers were right":

![F-score](https://raw.githubusercontent.com/ayeshamashiat/PetniHunter/main/docs/img/02_fscore.png)

## Then I stopped asking the model to know things

The model cannot reliably know Bangla trivia. A lookup can. So the guard does the checking instead of the model:

1. **Extract** the name and what is being asked.
2. **Search** Bangla Wikipedia. Its search is spelling-tolerant and offers "did you mean", which Wikidata's own search is not. (I tested this; Wikidata's search missed a common spelling of Tagore's name.)
3. **Check** the best title against the name, folding common Bangla spelling variants (ী/ি, ূ/ু, শ/ষ/স), and then confirm with Wikidata that the match is the right *kind* of thing: a writer, a book or a film.
4. **Act**: refuse, redirect, or rescue.

![The trade-off](https://raw.githubusercontent.com/ayeshamashiat/PetniHunter/main/docs/img/01_tradeoff.png)

| System | Fake names answered as real ↓ | Real names correct ↑ | Real names wrong ↓ | F-score ↑ |
|---|---|---|---|---|
| Plain Qwen3.5-4B | 96.3% | 3.7% | 93.4% | 3.8 |
| + "say if unsure" prompt | 18.2% | 1.0% | 19.7% | 1.6 |
| Fine-tuned (R-Tuning style) | 0.0% | 0.0% | 0.0% | 0.0 |
| **PetniHunter guard** | **0.1%** | **86.6%** | 1.9% | **91.9** |

2,367 test items; 95% intervals are in the repo. Writers 91.9% correct, books 87.8%, films 81.4%. Films were never used in training, so they test whether the approach carries over to a type of entity the system was not tuned on. (The guard itself has no training step. Its two similarity thresholds were fixed up front and sanity-checked on the train split. The entity-type check was added after I saw train-split failures.)

For misspelled real names (330 items), **70%** were handled correctly: 200 got a correct "did you mean…?", 31 were resolved with the substitution disclosed, and 99 were missed. None was silently answered as a *different* entity.

![What the guard does](https://raw.githubusercontent.com/ayeshamashiat/PetniHunter/main/docs/img/03_guard_outcomes.png)

## Where it breaks (please read this part)

I would rather you trust the numbers than be impressed by them.

- **The guard's scores are ceilings.** The gold answers come from Wikidata, and the guard looks things up in Wikipedia and Wikidata. A near-perfect score on clean entities is partly by construction. It shows the pipeline works, not that the guard knows things Wikipedia does not.
- **The ghosts are partly self-fulfilling.** I kept only invented names that a Bangla Wikipedia search could not find. That is the same search the guard uses. So refusing them is almost guaranteed. I checked whether ghosts were detectable by *name style* alone with a small classifier: for model-invented names it scored AUC 0.72–0.80 (0.5 is chance), so style was a real shortcut. For my spliced names it scored 0.46–0.62, which is why I report both.
- **Common names are the hard case.** Many people share a name. On my *training* split, before I added the entity-type check, 5 of 1,005 ghosts matched a real person with the same name. The check fixed it. On the test set, the one ghost the guard answered is *প্রতিশ্রুতি* ("Promise"), an ordinary word that is also a real 2001 film. That one is arguably my ghost generator's mistake, not the guard's.
- **I changed the guard once after a demo failure** (suggestions were not type-checked: for a typo of Tagore's name it offered a *documentary about him*). That means I ran the test set twice. Both runs are in the repo. The fix raised misspelling handling from 65.2% to 70.0% and changed nothing else.
- **My answer checker is rule-based, not an LLM judge**, and it makes mistakes: it counts "জসীম উদ্‌দীন" and "জসীম উদ্দীন" as different because of one invisible character, and Wikidata sometimes lists two birth years for the same person. **[ONLY IF YOU DO THE AUDIT, keep this sentence: I also audited 100 outputs by hand, blind to the checker's verdicts, and we agreed on X of 100. Otherwise delete it.]**
- It covers writers, books and films only, needs internet, and cannot rescue what Bangla Wikipedia does not contain (11.5% of real entities went unanswered).

## Why this fits "Ghost in the Machine"

The ghosts here are the phantoms a model conjures. They look present, and they have a plot, a year and a cast, but nothing is there. The folklore word *petni* felt right for something that is more than a ghost story: in this project the ghost is also a real harm, because a student who trusts "Tagore wrote *Pather Panchali*" is being misled in their own language.

## The open-source AI at the core

- **Qwen3.5-4B (open weights)** reads the questions, generates and translates, and is the baseline and the fine-tuned model.
- **Tinker (Thinking Machines)** ran all sampling and the LoRA fine-tune.
- **Wikidata and Bangla Wikipedia** are the source of truth.

Related work I built on and compared against: HalluLens (Meta, 2025), SimpleQA (OpenAI, 2024), R-Tuning (2024), and [BenHalluEval](https://arxiv.org/abs/2605.31483), a Bengali hallucination benchmark that checks the faithfulness of generated text, where mine checks whether an entity exists.

## What I would do next

A bigger model might know enough for fine-tuning to help; the 9B I did not get to is the first thing I would try. Wikidata coverage of Bangla entities is thin, so adding a second source (a library catalogue, a film database) is the obvious way to cut the 11.5% unanswered. And the homonym problem deserves its own dataset.

## Run it

```bash
git clone https://github.com/ayeshamashiat/PetniHunter && cd PetniHunter
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env     # add your TINKER_API_KEY
python -m petnihunter.app
```

```python
from petnihunter import answer
answer("'নিশিগন্ধার দিনলিপি' উপন্যাসটি কে লিখেছেন?")   # -> refuses, honestly
```

*How I built it: I worked with an AI coding assistant (Claude Code) for much of the code. The experiment design, the choice to report failures, and the human audit are mine. [EDIT TO MATCH WHAT YOU WANT TO SAY]*
