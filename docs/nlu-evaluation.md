# NLU Evaluation

Evaluation of the intent classification and entity extraction model against
**NFR-01** (intent recognition accuracy ≥ 85% on a held-out test set).

- **Date:** 14 October 2026
- **Pipeline:** `config.yml` (WhitespaceTokenizer → RegexFeaturizer → LexicalSyntacticFeaturizer → CountVectors (word + char n-gram) → BERT `bert-base-uncased` → DIETClassifier)
- **Training data:** `data/nlu.yml`, about 330 examples across 16 intents
- **Test data:** `tests/nlu_test_data.yml`, 56 held-out sentences that do not appear in the training data

To reproduce:

```powershell
rasa train nlu
rasa test nlu --nlu tests/nlu_test_data.yml --out results/nlu
```

## Results

| Metric | Value |
|---|---|
| Intent accuracy | **96.4%** (54 / 56) |
| Intent weighted F1 | 0.96 |
| Entity weighted F1 | 0.87 |
| Training intent accuracy, previous pipeline (BERT features only) | 93.4% |
| Training intent accuracy, current pipeline | 100% |

**NFR-01 target of ≥ 85% intent accuracy is met.**

### Per-intent

| Intent | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| greet | 1.00 | 1.00 | 1.00 | 3 |
| goodbye | 1.00 | 1.00 | 1.00 | 3 |
| thank_you | 1.00 | 1.00 | 1.00 | 3 |
| bot_capabilities | 1.00 | 1.00 | 1.00 | 4 |
| check_flight_status | 1.00 | 1.00 | 1.00 | 4 |
| change_booking | 1.00 | 1.00 | 1.00 | 4 |
| cancel_booking | 1.00 | 1.00 | 1.00 | 4 |
| new_booking | 0.80 | 1.00 | 0.89 | 4 |
| baggage_policy | 1.00 | 1.00 | 1.00 | 4 |
| check_in_procedure | 1.00 | 1.00 | 1.00 | 4 |
| check_in_status | 1.00 | 1.00 | 1.00 | 3 |
| escalate_to_agent | 0.75 | 1.00 | 0.86 | 3 |
| out_of_scope | 1.00 | 0.33 | 0.50 | 3 |
| inform | 1.00 | 1.00 | 1.00 | 4 |
| affirm | 1.00 | 1.00 | 1.00 | 3 |
| deny | 1.00 | 1.00 | 1.00 | 3 |

### Per-entity

| Entity | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| flight_number | 1.00 | 1.00 | 1.00 | 5 |
| booking_reference | 1.00 | 1.00 | 1.00 | 4 |
| date | 1.00 | 0.75 | 0.86 | 4 |
| city (role `from`) | 1.00 | 1.00 | 1.00 | 1 |
| city (role `to`) | 0.50 | 1.00 | 0.67 | 2 |
| city (no role) | 0.00 | 0.00 | 0.00 | 1 |

## Errors

| Sentence | Expected | Predicted |
|---|---|---|
| can you book me an uber | out_of_scope | new_booking |
| sing me a song | out_of_scope | escalate_to_agent |

Both errors are out-of-scope requests. "Book me an uber" shares its verb with
flight bookings, which is the hardest boundary for this domain. Entity errors
are mostly role assignments for bare city names (e.g. "Lagos" given role `to`).
The dialogue forms tolerate these because they validate the city against the
slot being requested.

## Regression check: utterances that failed in manual testing (23 Sep 2026)

| Utterance | Before | Now |
|---|---|---|
| I want to cancel my booking | nlu_fallback | cancel_booking (1.00) |
| can you help me book my flight | nlu_fallback | new_booking (1.00) |
| what can you do for me | nlu_fallback | bot_capabilities (1.00) |
| What services do you provide | nlu_fallback | bot_capabilities (1.00) |
| what do you do | nlu_fallback | bot_capabilities (1.00) |

## Next steps (M6: System Integration & Testing)

- Add more out-of-scope examples covering non-flight "booking" requests (taxi, hotel, car hire)
- Grow the held-out set and add 5-fold cross-validation (`rasa test nlu --cross-validation`)
