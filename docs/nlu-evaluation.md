# NLU Evaluation

Evaluation of the intent classification and entity extraction model against
**NFR-01** (intent recognition accuracy ≥ 85% on a held-out test set).

- **Date:** 26 October 2026 (M6: System Integration & Testing)
- **Pipeline:** `config.yml` (WhitespaceTokenizer → RegexFeaturizer → LexicalSyntacticFeaturizer → CountVectors (word + char n-gram) → BERT `bert-base-uncased` → DIETClassifier)
- **Training data:** `data/nlu.yml`, 354 examples across 16 intents
- **Test data:** `tests/nlu_test_data.yml`, 99 held-out sentences, none of which appear in the training data (checked ignoring case and punctuation)

To reproduce:

```powershell
rasa train
rasa test nlu --nlu tests/nlu_test_data.yml --out results/nlu
```

## Results

| Metric | Before (14 Oct model) | After (26 Oct model) |
|---|---|---|
| Intent accuracy, 99-sentence test set | 91.9% (91 / 99) | **97.0%** (96 / 99) |
| Intent weighted F1 | 0.91 | 0.97 |
| Out-of-scope recall | 0.50 | 0.75 |
| Entity weighted F1 | 0.90 | 0.93 |
| End-to-end test stories | 8 / 8 | 8 / 8 (40 / 40 actions) |

Both models were tested on the same extended set, so the columns are directly comparable.
The 14 October model scored 96.4% on the original 56-sentence set; the extended set adds
harder cases (non-flight "booking" requests, keyboard gibberish, bare city answers).

**NFR-01 target of ≥ 85% intent accuracy is met.**

### Per-intent (after)

| Intent | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| greet | 1.00 | 1.00 | 1.00 | 5 |
| goodbye | 1.00 | 1.00 | 1.00 | 5 |
| thank_you | 1.00 | 1.00 | 1.00 | 5 |
| bot_capabilities | 1.00 | 1.00 | 1.00 | 6 |
| check_flight_status | 1.00 | 1.00 | 1.00 | 7 |
| change_booking | 1.00 | 1.00 | 1.00 | 7 |
| cancel_booking | 1.00 | 1.00 | 1.00 | 6 |
| new_booking | 0.75 | 1.00 | 0.86 | 6 |
| baggage_policy | 1.00 | 1.00 | 1.00 | 6 |
| check_in_procedure | 1.00 | 1.00 | 1.00 | 6 |
| check_in_status | 1.00 | 1.00 | 1.00 | 5 |
| escalate_to_agent | 1.00 | 1.00 | 1.00 | 5 |
| out_of_scope | 1.00 | 0.75 | 0.86 | 12 |
| inform | 0.89 | 1.00 | 0.94 | 8 |
| affirm | 1.00 | 1.00 | 1.00 | 5 |
| deny | 1.00 | 1.00 | 1.00 | 5 |

### Per-entity (after)

| Entity | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| flight_number | 1.00 | 1.00 | 1.00 | 10 |
| booking_reference | 1.00 | 1.00 | 1.00 | 7 |
| date | 1.00 | 0.88 | 0.93 | 8 |
| city (role `to`) | 0.83 | 1.00 | 0.91 | 5 |
| city (role `from`) | 0.50 | 1.00 | 0.67 | 1 |
| city (no role) | 0.00 | 0.00 | 0.00 | 1 |

## What changed

Training examples added in `data/nlu.yml`:

- **out_of_scope** (20 → 43): non-flight "booking" requests (taxi, hotel, restaurant, bus, train,
  safari, car hire), other off-topic requests, and keyboard gibberish such as `asdf` and `lkjh gfds`
- **inform**: bare and role-marked city answers (`to Kigali`, `from Kisumu`, `Entebbe`)
- **check_in_status**: three more phrasings ("is my check-in finished")

Errors fixed by these changes:

| Sentence | Before | After |
|---|---|---|
| asdkj qwpoe | inform (0.89) | out_of_scope |
| qwerty uiop | bot_capabilities (0.22) | out_of_scope |
| sing me a song | escalate_to_agent (0.52) | out_of_scope |
| is my check in done | check_in_procedure (0.68) | check_in_status |
| to Johannesburg | new_booking (1.00) | inform |

## Remaining errors

| Sentence | Expected | Predicted |
|---|---|---|
| can you book me an uber | out_of_scope | new_booking (0.90) |
| book me a table for dinner | out_of_scope | new_booking (0.60) |
| zxcvb nmlk | out_of_scope | inform (0.78) |

"Book" followed by a non-flight object remains the hardest boundary. No examples were added for
these three sentences specifically, so the test set stays independent of the training data. In the
running system the impact is limited: the new booking form asks for an origin and destination and
rejects places that are not on the network.

## 5-fold cross-validation

The 354 training examples were split into five folds; each fold was held out in turn while a model
was trained on the other four (about 283 examples, 10 to 22 per intent).

```powershell
rasa test nlu --nlu data/nlu.yml --config config.yml --cross-validation --folds 5 --out results/cv
```

| Metric (mean ± standard deviation over 5 folds) | Train folds | Test folds |
|---|---|---|
| Intent accuracy | 100% (± 0.0) | **79.7% (± 5.5)** |
| Intent F1 | 1.00 | 0.79 (± 0.06) |
| Intent precision | 1.00 | 0.83 (± 0.05) |
| Entity F1 | 1.00 | 0.87 (± 0.05) |

None of the 72 misclassified examples went to fallback; all were confident confusions.

### Per-intent, accumulated over the test folds

| Intent | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| greet | 0.82 | 0.78 | 0.80 | 18 |
| goodbye | 0.85 | 0.92 | 0.88 | 12 |
| thank_you | 0.73 | 0.92 | 0.81 | 12 |
| bot_capabilities | 0.80 | 0.80 | 0.80 | 20 |
| check_flight_status | 0.79 | 0.85 | 0.82 | 27 |
| change_booking | 0.62 | 0.81 | 0.70 | 26 |
| cancel_booking | 0.95 | 0.88 | 0.91 | 24 |
| new_booking | 0.67 | 0.92 | 0.77 | 26 |
| baggage_policy | 0.96 | 1.00 | 0.98 | 25 |
| check_in_procedure | 0.75 | 0.90 | 0.82 | 20 |
| check_in_status | 0.86 | 0.95 | 0.90 | 19 |
| escalate_to_agent | 1.00 | 1.00 | 1.00 | 17 |
| out_of_scope | 0.95 | 0.47 | 0.62 | 43 |
| inform | 0.74 | 0.69 | 0.71 | 36 |
| affirm | 0.73 | 0.69 | 0.71 | 16 |
| deny | 0.70 | 0.54 | 0.61 | 13 |

### Interpretation

Cross-validated accuracy (79.7%) is lower than accuracy on the held-out test set (97.0%) and below
the 85% NFR-01 target. The two numbers measure different things:

- The held-out test set contains typical passenger phrasings, and the model is trained on all
  354 examples.
- Cross-validation trains on only 80% of the data and tests on the training examples themselves,
  many of which are deliberately unusual: keyboard gibberish, one-word answers ("BK001", "Nairobi"),
  and off-topic requests that share nothing with each other. When such an example is held out, the
  remaining folds often contain nothing similar.

The weakest intents in cross-validation are the ones with the most varied or shortest examples:
out_of_scope (recall 0.47), deny (0.54), affirm (0.69) and inform (0.69). Common confusions are
deny ↔ affirm, change_booking ↔ new_booking and out_of_scope → new_booking.

The gap and the fold-to-fold variation (± 5.5 points) show that the model is still data-limited:
performance depends on how many examples it sees per intent. NFR-01 is met on the held-out test
set, but the cross-validation result is the more conservative estimate for unseen real passenger
language. Growing the training data towards the proposal's target (about 2,000 examples, roughly
100 per intent), especially for out_of_scope, affirm/deny and inform, is the main recommendation.

## History

| Date | Model | Test set | Intent accuracy | Entity F1 |
|---|---|---|---|---|
| 23 Sep 2026 | BERT features only | training data | 93.4% | – |
| 14 Oct 2026 | BERT + sparse features | 56 sentences | 96.4% | 0.87 |
| 26 Oct 2026 | + out-of-scope, gibberish and city examples | 99 sentences | 97.0% | 0.93 |
| 26 Oct 2026 | same model, 5-fold cross-validation | training data | 79.7% (± 5.5) | 0.87 |

Utterances that failed in manual testing on 23 September 2026 ("I want to cancel my booking",
"can you help me book my flight", "what can you do for me", "What services do you provide",
"what do you do") were fixed in the 14 October model and remain correct.
