"""Load test for the chat API (NFR-01: response time <= 2 s; NFR-04: concurrent passengers).

Simulates passengers chatting at the same time. Each virtual passenger runs one
read-only conversation (greeting, flight status, baggage, check-in, capabilities),
so the test never changes bookings. Response times are measured by the client,
end to end through the gateway, Rasa, the action server and PostgreSQL.

Usage (against a running stack; use a separate test stack, not the demo one):
    python tests/load/run_load.py --url http://127.0.0.1:8001 --levels 1,10,25,50
"""
import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

CONVERSATIONS = [
    ["hello", "Is KQ202 on time?"],
    ["what is the baggage allowance in economy"],
    ["when does online check-in open"],
    ["flight status", "KQ101"],
    ["what can you do", "thanks, bye"],
]
TARGET_SECONDS = 2.0


def run_passenger(base_url, index):
    """Plays one conversation and returns (latencies in seconds, error count)."""
    latencies, errors = [], 0
    sender_id = None
    with httpx.Client(base_url=base_url, timeout=30) as client:
        for message in CONVERSATIONS[index % len(CONVERSATIONS)]:
            payload = {"message": message}
            if sender_id:
                payload["sender_id"] = sender_id
            started = time.perf_counter()
            try:
                response = client.post("/api/chat", json=payload)
                elapsed = time.perf_counter() - started
                if response.status_code != 200 or not response.json().get("messages"):
                    errors += 1
                    continue
                sender_id = response.json()["sender_id"]
                latencies.append(elapsed)
            except httpx.HTTPError:
                errors += 1
        if sender_id:
            try:
                client.post(f"/api/chat/{sender_id}/end")
            except httpx.HTTPError:
                pass
    return latencies, errors


def percentile(values, pct):
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return ordered[k]


def run_level(base_url, passengers):
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=passengers) as pool:
        results = list(pool.map(lambda i: run_passenger(base_url, i), range(passengers)))
    wall = time.perf_counter() - started
    latencies = [t for lat, _ in results for t in lat]
    errors = sum(e for _, e in results)
    return {
        "passengers": passengers,
        "requests": len(latencies) + errors,
        "errors": errors,
        "mean_s": round(statistics.mean(latencies), 3) if latencies else None,
        "median_s": round(statistics.median(latencies), 3) if latencies else None,
        "p95_s": round(percentile(latencies, 95), 3) if latencies else None,
        "max_s": round(max(latencies), 3) if latencies else None,
        "within_target": round(sum(t <= TARGET_SECONDS for t in latencies) / len(latencies) * 100, 1) if latencies else 0,
        "throughput_rps": round(len(latencies) / wall, 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--levels", default="1,10,25,50", help="comma-separated numbers of simultaneous passengers")
    parser.add_argument("--json", help="also write the results to this file")
    args = parser.parse_args()

    health = httpx.get(f"{args.url}/api/health", timeout=10)
    if health.status_code != 200:
        sys.exit(f"Stack at {args.url} is not healthy: {health.status_code} {health.text}")
    run_passenger(args.url, 0)  # warm-up so model loading is not counted

    rows = [run_level(args.url, int(n)) for n in args.levels.split(",")]
    print(f"{'Passengers':>10} {'Requests':>8} {'Errors':>6} {'Mean':>6} {'Median':>6} {'p95':>6} {'Max':>6} "
          f"{'<=2s':>6} {'Req/s':>6}")
    for r in rows:
        print(f"{r['passengers']:>10} {r['requests']:>8} {r['errors']:>6} {r['mean_s']:>6} {r['median_s']:>6} "
              f"{r['p95_s']:>6} {r['max_s']:>6} {r['within_target']:>5}% {r['throughput_rps']:>6}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)


if __name__ == "__main__":
    main()
