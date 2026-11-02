"""Paso 12/13: casos publicos + latencia contra una URL (local o tunel HTTPS).
Uso (desde la raiz del repo):
    $env:QA_API_TOKEN = "..."          # NO se imprime ni se guarda
    python scripts\\measure_latency.py --url https://TU-URL --rounds 10
Genera logs/latency_results.json (sin secretos)."""
import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 5.0  # limite por peticion del docente
GLOBAL_LIMIT = 150.0  # 50 preguntas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--rounds", type=int, default=10, help="vueltas sobre los 5 casos (10 = 50 peticiones)")
    ap.add_argument("--out", default=str(ROOT / "logs" / "latency_results.json"))
    a = ap.parse_args()
    token = os.environ.get("QA_API_TOKEN")
    if not token:
        sys.exit("Falta la variable QA_API_TOKEN")
    base = a.url.rstrip("/")
    items = json.loads((ROOT / "public_sample.json").read_text(encoding="utf-8"))["items"]
    headers = {"Authorization": f"Bearer {token}", "ngrok-skip-browser-warning": "1"}

    times, failures, first_round = [], 0, []
    with httpx.Client(timeout=TIMEOUT) as c:
        print("health:", c.get(f"{base}/health").status_code)
        t_all = time.perf_counter()
        for r in range(a.rounds):
            for it in items:
                body = {k: it[k] for k in ("id", "context", "question")}
                t0 = time.perf_counter()
                try:
                    resp = c.post(f"{base}/predict", json=body, headers=headers)
                    ok = resp.status_code == 200
                    j = resp.json() if ok else {}
                    if ok and j.get("answer") is not None:
                        ok = it["context"][j["start"]:j["start"] + len(j["answer"])] == j["answer"]
                except Exception as e:  # timeout o red
                    ok, j = False, {"error": type(e).__name__}
                dt = time.perf_counter() - t0
                times.append(dt)
                failures += 0 if ok else 1
                if r == 0:
                    first_round.append({"id": it["id"], "answer": j.get("answer"), "start": j.get("start"),
                                        "seconds": round(dt, 3)})
        total = time.perf_counter() - t_all

    n = len(times)
    mean = statistics.mean(times)
    res = {
        "target": base.split("//")[-1],
        "n_requests": n,
        "failures_or_timeouts": failures,
        "mean_s": round(mean, 3),
        "p95_s": round(sorted(times)[int(0.95 * (n - 1))], 3),
        "max_s": round(max(times), 3),
        "total_s": round(total, 2),
        "projected_50_questions_s": round(mean * 50, 1),
        "limit_per_request_s": TIMEOUT,
        "limit_global_s": GLOBAL_LIMIT,
        "within_limits": failures == 0 and max(times) < TIMEOUT and mean * 50 < GLOBAL_LIMIT,
        "first_round": first_round,
    }
    Path(a.out).parent.mkdir(exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "first_round"}, indent=2))


if __name__ == "__main__":
    main()
