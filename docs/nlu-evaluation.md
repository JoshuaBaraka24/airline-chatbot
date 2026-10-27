# NLU Evaluation

Evaluation of the intent classification and entity extraction model against
**NFR-01** (intent recognition accuracy ≥ 85% on a held-out test set).

- **Date:** 27 October 2026 (M6: System Integration & Testing)
- **Pipeline:** `config.yml` (WhitespaceTokenizer → RegexFeaturizer → LexicalSyntacticFeaturizer → CountVectors (word + char n-gram) → BERT `bert-base-uncased` → DIETClassifier)
- **Training data:** `data/nlu.yml`, 806 examples across 16 intents (39 to 88 per intent)
- **Test data:** `tests/nlu_test_data.yml`, 99 held-out sentences, none of which appear in the training data (checked ignoring case and punctuation)

To reproduce:

```powershell
rasa train
rasa test nlu --nlu tests/nlu_test_data.yml --out results/nlu
rasa test nlu --nlu data/nlu.yml --config config.yml --cross-validation --folds 5 --out results/cv
```

## Results

| Metric | 26 Oct model (354 examples) | 27 Oct model (806 examples) |
|---|---|---|
| Intent accuracy, 99-sentence test set | 97.0% (96 / 99) | **97.0%** (96 / 99) |
| Intent weighted F1, test set | 0.97 | 0.97 |
| Entity weighted F1, test set | 0.93 | 0.94 |
| Intent accuracy, 5-fold cross-validation | 79.7% (± 5.5) | **87.7% (± 1.9)** |
| Intent F1, 5-fold cross-validation | 0.79 | 0.87 |
| Entity F1, 5-fold cross-validation | 0.87 | 0.90 |
| End-to-end test stories | 8 / 8 (40 / 40 actions) | 8 / 8 (48 / 48 actions) |

**NFR-01 target of ≥ 85% intent accuracy is met on both measures.**

The held-out test set was not changed, so the columns are directly comparable. The 27 October
model also covers the new booking answers (flight choices, passenger names, email addresses), and
the booking test story grew from 5 to 9 steps to include them.

### Per-intent, held-out test set

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
| escalate_to_agent | 0.83 | 1.00 | 0.91 | 5 |
| out_of_scope | 1.00 | 0.75 | 0.86 | 12 |
| inform | 1.00 | 1.00 | 1.00 | 8 |
| affirm | 1.00 | 1.00 | 1.00 | 5 |
| deny | 1.00 | 1.00 | 1.00 | 5 |

### Per-entity, held-out test set

| Entity | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| flight_number | 1.00 | 1.00 | 1.00 | 10 |
| booking_reference | 1.00 | 1.00 | 1.00 | 7 |
| date | 1.00 | 1.00 | 1.00 | 8 |
| city (role `to`) | 0.80 | 0.80 | 0.80 | 5 |
| city (role `from`) | 1.00 | 1.00 | 1.00 | 1 |
| city (no role) | 0.00 | 0.00 | 0.00 | 1 |

### Remaining errors, held-out test set

| Sentence | Expected | Predicted |
|---|---|---|
| can you book me an uber | out_of_scope | new_booking (0.61) |
| book me a table for dinner | out_of_scope | new_booking (0.87) |
| tell me something funny | out_of_scope | escalate_to_agent (0.63) |

"zxcvb nmlk", wrong in the 26 October model, is now correct; "tell me something funny" is a new
error. "Book" followed by a non-flight object remains the hardest boundary. No examples were added
for these sentences specifically, so the test set stays independent of the training data. In the
running system the impact is limited: the new booking form asks for an origin and destination and
rejects places that are not on the network.

## 5-fold cross-validation

The 806 training examples were split into five folds; each fold was held out in turn while a model
was trained on the other four (about 645 examples, 31 to 70 per intent).

| Metric (mean ± standard deviation over 5 folds) | Train folds | Test folds |
|---|---|---|
| Intent accuracy | 100% (± 0.0) | **87.7% (± 1.9)** |
| Intent F1 | 1.00 | 0.87 (± 0.02) |
| Intent precision | 1.00 | 0.89 (± 0.02) |
| Entity F1 | 1.00 | 0.90 (± 0.05) |

None of the 99 misclassified examples went to fallback; all were confident confusions.

### Per-intent, accumulated over the test folds

| Intent | Precision | Recall | F1 | Support | F1 on 26 Oct |
|---|---|---|---|---|---|
| greet | 0.91 | 0.91 | 0.91 | 46 | 0.80 |
| goodbye | 0.89 | 0.79 | 0.84 | 39 | 0.88 |
| thank_you | 0.90 | 0.88 | 0.89 | 40 | 0.81 |
| bot_capabilities | 0.80 | 0.96 | 0.87 | 46 | 0.80 |
| check_flight_status | 0.91 | 0.94 | 0.93 | 53 | 0.82 |
| change_booking | 0.84 | 0.83 | 0.83 | 52 | 0.70 |
| cancel_booking | 0.95 | 0.87 | 0.91 | 46 | 0.91 |
| new_booking | 0.77 | 0.96 | 0.85 | 52 | 0.77 |
| baggage_policy | 0.94 | 0.96 | 0.95 | 48 | 0.98 |
| check_in_procedure | 0.86 | 0.86 | 0.86 | 42 | 0.82 |
| check_in_status | 0.86 | 0.93 | 0.89 | 40 | 0.90 |
| escalate_to_agent | 0.95 | 0.93 | 0.94 | 44 | 1.00 |
| out_of_scope | 0.94 | 0.66 | 0.77 | 88 | 0.62 |
| inform | 0.86 | 0.94 | 0.90 | 85 | 0.71 |
| affirm | 0.83 | 0.86 | 0.84 | 44 | 0.71 |
| deny | 0.90 | 0.88 | 0.89 | 41 | 0.61 |

### Interpretation

Growing the training data closed most of the gap between the two measures. Cross-validated accuracy
rose 8 points to 87.7%, and its fold-to-fold variation fell from ± 5.5 to ± 1.9 points, so the result
no longer depends much on which examples a fold happens to see. The biggest gains are in the intents
that were weakest: deny (F1 0.61 → 0.89), affirm (0.71 → 0.84), inform (0.71 → 0.90) and
change_booking (0.70 → 0.83).

out_of_scope is still the weakest intent (recall 0.66). Its examples are deliberately varied
(non-flight bookings, chit-chat, keyboard gibberish), so a held-out example often has no close
neighbour. The most common confusions are out_of_scope → new_booking (9) and out_of_scope →
bot_capabilities (7), followed by check_in_procedure → check_in_status (5). A wrongly accepted
out-of-scope request is caught by the form validators in most cases, as described above.

## What changed (27 October)

Training examples in `data/nlu.yml` grew from 354 to 806:

- every intent now has at least 39 examples (previously 12 to 43)
- **out_of_scope** (43 → 88): more non-flight bookings, everyday requests (M-Pesa, airtime, alarms),
  chit-chat and keyboard gibberish
- **inform** (36 → 85): answers to the new booking questions (flight choices such as "the second
  one" or "option 2", passenger names, email addresses), plus more dates, cities and references
- **affirm / deny** (16 / 13 → 44 / 41), including Swahili "ndio" and "hapana"

New examples were checked against both the training set and the held-out test set, ignoring case
and punctuation; six that duplicated existing sentences were dropped.

## History

| Date | Model | Test set | Intent accuracy | Entity F1 |
|---|---|---|---|---|
| 23 Sep 2026 | BERT features only | training data | 93.4% | – |
| 14 Oct 2026 | BERT + sparse features | 56 sentences | 96.4% | 0.87 |
| 26 Oct 2026 | + out-of-scope, gibberish and city examples (354) | 99 sentences | 97.0% | 0.93 |
| 26 Oct 2026 | same model, 5-fold cross-validation | training data | 79.7% (± 5.5) | 0.87 |
| 27 Oct 2026 | 806 examples, new booking answers | 99 sentences | 97.0% | 0.94 |
| 27 Oct 2026 | same model, 5-fold cross-validation | training data | 87.7% (± 1.9) | 0.90 |

Utterances that failed in manual testing on 23 September 2026 ("I want to cancel my booking",
"can you help me book my flight", "what can you do for me", "What services do you provide",
"what do you do") were fixed in the 14 October model and remain correct.
