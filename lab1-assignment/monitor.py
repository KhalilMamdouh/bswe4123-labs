"""Monitor three services every two seconds.

A service is reported DOWN only after 3 consecutive failed checks.
A successful response taking more than 500 ms is reported SLOW.
"""
import time
import httpx

SERVICES = {
    "service-8001": "http://127.0.0.1:8001",
    "service-8002": "http://127.0.0.1:8002",
    "service-8003": "http://127.0.0.1:8003",
}
INTERVAL_SECONDS = 2
TIMEOUT_SECONDS = 1.0
SLOW_AFTER_SECONDS = 0.500
FAILURES_FOR_DOWN = 3

failure_counts = {name: 0 for name in SERVICES}

def check(client: httpx.Client, name: str, url: str) -> str:
    started = time.perf_counter()
    try:
        response = client.get(f"{url}/health")
        response.raise_for_status()
        elapsed = time.perf_counter() - started
        failure_counts[name] = 0
        if elapsed > SLOW_AFTER_SECONDS:
            return f"SLOW ({elapsed * 1000:.0f} ms)"
        return f"UP ({elapsed * 1000:.0f} ms)"
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
        failure_counts[name] += 1
        if failure_counts[name] >= FAILURES_FOR_DOWN:
            return f"DOWN ({failure_counts[name]} consecutive failures)"
        return f"SUSPECT ({failure_counts[name]}/{FAILURES_FOR_DOWN} failed checks)"

def main():
    round_number = 0
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        try:
            while True:
                round_number += 1
                results = [
                    f"{name}: {check(client, name, url)}"
                    for name, url in SERVICES.items()
                ]
                print(f"Round {round_number:02d} | " + " | ".join(results), flush=True)
                time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nMonitor stopped.")

if __name__ == "__main__":
    main()
