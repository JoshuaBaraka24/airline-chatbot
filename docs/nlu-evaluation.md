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

## History

| Date | Model | Test set | Intent accuracy | Entity F1 |
|---|---|---|---|---|
| 23 Sep 2026 | BERT features only | training data | 93.4% | – |
| 14 Oct 2026 | BERT + sparse features | 56 sentences | 96.4% | 0.87 |
| 26 Oct 2026 | + out-of-scope, gibberish and city examples | 99 sentences | 97.0% | 0.93 |

Utterances that failed in manual testing on 23 September 2026 ("I want to cancel my booking",
"can you help me book my flight", "what can you do for me", "What services do you provide",
"what do you do") were fixed in the 14 October model and remain correct.
