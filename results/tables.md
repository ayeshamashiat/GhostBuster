| System | Fake names answered as real ↓ (HalluLens FAR) | Real names correct ↑ | Real names wrong ↓ | Not attempted | F-score ↑ |
|---|---|---|---|---|---|
| PetniHunter guard | 0.1% [0.0–0.6] | 86.6% [84.5–88.5] | 1.9% [1.2–2.9] | 11.5% [9.7–13.5] | **91.9** |
| Plain model | 96.3% [94.9–97.4] | 3.7% [2.7–5.0] | 93.4% [91.8–94.7] | 2.9% [2.1–4.0] | **3.8** |
| “Say if unsure” prompt | 18.2% [15.8–20.8] | 1.0% [0.6–1.8] | 19.7% [17.4–22.1] | 79.3% [76.8–81.6] | **1.6** |
| Fine-tuned (R-Tuning) | 0.0% [0.0–0.4] | 0.0% [0.0–0.3] | 0.0% [0.0–0.3] | 100.0% [99.7–100.0] | **0.0** |

By entity type (guard, real entities answered correctly):

| Type | n | Correct |
|---|---|---|
| writer | 469 | 91.9% [89.1–94.0] |
| book | 139 | 87.8% [81.3–92.2] |
| film | 500 | 81.4% [77.8–84.6] |

Silent substitution (guard answered about a different entity than asked): 12 of 2367 items = 0.51%
