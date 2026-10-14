"""Webhook burst load and concurrency stress testing script."""

import asyncio
import hashlib
import hmac
import time
from typing import Any

import httpx

MOCK_SECRET = "loadtest_mock_secret_key"


def generate_signature(secret: str, body: bytes) -> str:
    """Generate X-Hub-Signature-256 for a given body."""
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_webhook_payload(wa_id: str, sender_phone: str, body_text: str) -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "wa_acc_load",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550001",
                                "phone_number_id": "phone_load_1",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Load Tester"},
                                    "wa_id": sender_phone,
                                }
                            ],
                            "messages": [
                                {
                                    "from": sender_phone,
                                    "id": wa_id,
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": body_text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


async def send_single_webhook(
    client: httpx.AsyncClient,
    base_url: str,
    webhook_key: str,
    payload: dict[str, Any],
    secret: str | None = None,
) -> tuple[int, float]:
    """Send one webhook POST request and return status code and latency in milliseconds."""
    import json

    url = f"{base_url.rstrip('/')}/webhook/{webhook_key}"
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Hub-Signature-256"] = generate_signature(secret, body)

    start = time.perf_counter()
    try:
        resp = await client.post(url, content=body, headers=headers, timeout=10.0)
        latency = (time.perf_counter() - start) * 1000
        return resp.status_code, latency
    except Exception:
        latency = (time.perf_counter() - start) * 1000
        return 500, latency


async def run_burst_load_test(
    base_url: str = "http://127.0.0.1:8000",
    webhook_key: str = "test_webhook_key",
    concurrency: int = 50,
) -> dict[str, Any]:
    """Run concurrent burst of webhook events and measure response statistics."""
    print(f"\n[LOAD TEST] Starting burst test: {concurrency} concurrent requests to {base_url}/webhook/{webhook_key}...")

    async with httpx.AsyncClient() as client:
        # Prepare requests
        tasks = []
        for i in range(concurrency):
            msg_id = f"wamid.burst_{int(time.time())}_{i}"
            payload = build_webhook_payload(
                wa_id=msg_id,
                sender_phone=f"+91900000{i:04d}",
                body_text=f"Burst test message {i}",
            )
            tasks.append(send_single_webhook(client, base_url, webhook_key, payload))

        t0 = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - t0

    status_codes = [r[0] for r in results]
    latencies = sorted([r[1] for r in results])

    success_count = sum(1 for c in status_codes if c in (200, 204))
    throughput = concurrency / total_time if total_time > 0 else 0

    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    summary = {
        "concurrency": concurrency,
        "total_time_sec": round(total_time, 3),
        "throughput_req_sec": round(throughput, 1),
        "success_rate_percent": round((success_count / concurrency) * 100, 1),
        "min_ms": round(latencies[0], 2),
        "median_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "max_ms": round(latencies[-1], 2),
    }

    print("--------------------------------------------------")
    print(f"Total Requests:       {concurrency}")
    print(f"Total Elapsed Time:   {summary['total_time_sec']}s")
    print(f"Throughput:           {summary['throughput_req_sec']} req/s")
    print(f"Success Rate:         {summary['success_rate_percent']}%")
    print(f"Latency p50 (Median): {summary['median_ms']} ms")
    print(f"Latency p95:          {summary['p95_ms']} ms")
    print(f"Latency Max:          {summary['max_ms']} ms")
    print("--------------------------------------------------")
    return summary


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    key = sys.argv[2] if len(sys.argv) > 2 else "test_key"
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    asyncio.run(run_burst_load_test(base_url=url, webhook_key=key, concurrency=count))
