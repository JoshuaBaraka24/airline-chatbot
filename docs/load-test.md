# Load Test

Response time of the chat API with several passengers chatting at the same time, against
**NFR-01** (response time ≤ 2 s for standard queries) and **NFR-04** (concurrent passengers
without failures).

- **Date:** 26 October 2026 (M6: System Integration & Testing)
- **Script:** `tests/load/run_load.py`
- **Machine:** one laptop (AMD Ryzen 5 PRO 7530U, 16 GB RAM, CPU only) running every component
- **Stack:** a separate test stack (gateway :8001, Rasa :5006, action server :5056, database
  `airline_db_test`), with the model from `data/nlu-hardening`
- **Workload:** each simulated passenger runs one read-only conversation of one or two turns
  (greeting and flight status, baggage, check-in times, flight status over two turns, capabilities).
  Times are measured by the client, end to end through the gateway, Rasa, the action server and
  PostgreSQL. A warm-up conversation runs first so model loading is not counted.

To reproduce, start a separate stack and run:

```powershell
python tests/load/run_load.py --url http://127.0.0.1:8001 --levels 1,10,25,50
```

## Results

| Passengers at once | Requests | Errors | Mean | Median | 95th percentile | Max | Within 2 s | Messages / s |
|---|---|---|---|---|---|---|---|---|
| 1 | 2 | 0 | 0.30 s | 0.30 s | 0.33 s | 0.33 s | 100% | 3.1 |
| 10 | 16 | 0 | 1.73 s | 1.98 s | 2.82 s | 2.93 s | 75% | 4.5 |
| 25 | 40 | 0 | 4.35 s | 4.91 s | 5.48 s | 6.05 s | 0% | 4.6 |
| 50 | 80 | 0 | 8.34 s | 7.96 s | 13.53 s | 15.20 s | 1% | 4.6 |

## Where the time goes

Median of 15 sequential requests for one turn ("what is the baggage allowance"):

| Stage | Time |
|---|---|
| NLU parse only (BERT + DIET) | 183 ms |
| Full Rasa turn (NLU + policies + response) | 193 ms |
| Gateway `/api/chat`, end to end | 268 ms |

About 70% of each turn is BERT inference on the CPU. The Rasa server processes one message at a
time, so throughput levels off at about 4.6 messages per second, close to the 1 / 0.19 s ≈ 5 per
second the parse time allows. The gateway (logging and session handling) adds about 75 ms.

## Findings

- **NFR-01 (≤ 2 s):** met for a single passenger (0.3 s) and at light load. At 10 simultaneous
  passengers 75% of replies are within 2 s; beyond that, replies queue behind BERT inference.
- **NFR-04 (concurrency):** no request failed at any level, up to 50 simultaneous passengers;
  the system slows down rather than breaking. A single CPU-only instance handles about
  4.6 messages per second, roughly 16,000 messages an hour.
- **To scale further:** run several Rasa instances behind a load balancer with a shared tracker
  store (for example Redis), use a GPU or a smaller model such as DistilBERT for the featurizer,
  or host each component on its own machine. None of these changes the application code.
