# Texto para pegar en REPORT.md (Integrante 4)

## === SECCION 0: reemplaza estas filas de la tabla ===

| Team id | `team-02` |
| Members | Elena Colorado (Member 1), David Aguilar (Member 2), Emilio Martinez (Member 3), Juan Pablo Quintanilla (Member 4) |
| Repository URL | https://github.com/ElenaColorado/ProyectoQA |
| `submission` commit hash | Tag `submission` (run `git rev-parse submission`; the SHA is also sent to the instructor with the link) |
| Public service URL used at the dry run | https://oblivious-latitude-luckless.ngrok-free.dev (ngrok; backup: Cloudflare Quick Tunnel, its URL changes on every restart) |

## === SECCION 0: AL FINAL de la fila "AI tools used" agrega esta frase ===

 Claude (Anthropic) also helped Member 4 draft `app.py`, its tests and the latency script, and with troubleshooting; Member 4 ran and checked them on his own laptop.

## === SECCION 4: reemplaza TODO el contenido (quita la línea "To be completed...") ===

## 4. Serving architecture

- **Framework and server:** FastAPI served by Uvicorn, 1 worker, port 8000 (`app.py`).
- **Model loading:** once, when the process starts (FastAPI lifespan, in a background thread). `QAPredictor` (Member 3) loads the tokenizer and weights from `models/qa-final/` with `local_files_only=True`, then one warm-up prediction runs. Until then `GET /health` returns 503 `{"status":"loading"}`; afterwards 200 `{"status":"ok"}`. The `params` value of `/info` is computed from the loaded model.
- **Request flow:** `POST /predict` body is validated by a Pydantic model (strict strings, `id` 1–64, `context` 1–5000, `question` 1–500 characters, extra fields forbidden), then the token is checked, then `predict(context, question)` runs. Long contexts are split into 384-token windows with stride 128; the best span over all windows is compared with the null score using threshold 1.0 (Section 3). Before returning 200, `app.py` checks that `context[start:start+len(answer)] == answer`, that `start` is `null` only when `answer` is `null`, and that `score` is in [0,1]; otherwise it returns 500 `internal_error` instead of hiding the bug. The request `id` is echoed unchanged. A lock allows one inference at a time.
- **Access control:** `/info` and `/predict` use a dependency that compares the whole `Authorization` header with `Bearer <QA_API_TOKEN>` (`hmac.compare_digest`, case-sensitive). The token comes from the `QA_API_TOKEN` environment variable; the app refuses to start without it, and it is never in the code or the repository. A wrong or missing token gives 401 `{"error":"unauthorized"}` with `WWW-Authenticate: Bearer`. Invalid bodies give 400 `{"error":"bad_request","detail":...}` through a custom handler (not FastAPI's default format).
- **Tunnel:** ngrok, `ngrok http 127.0.0.1:8000`. Backup: `cloudflared tunnel --url http://localhost:8000`. Both were tested from a phone on mobile data. Checks are saved in `logs/tunnel_checks.txt` (no secrets) and `logs/latency_results.json`.
- **How to run** from a clean machine:

```powershell
python -m pip install -r requirements.txt
# put the model files in models/qa-final/ (shared folder, not in Git)
$env:QA_API_TOKEN = "<token from the instructor>"
$env:QA_TEAM_ID = "team-02"
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
ngrok http 127.0.0.1:8000
```

## === SECCION 6: reemplaza SOLO estas dos filas de la tabla ===

| Mean latency per `/predict` request on your laptop (CPU) | 0.333 s through the ngrok tunnel (50 requests, 0 failures, p95 0.722 s, max 0.732 s, 16.6 s in total); 0.164 s on localhost; 0.126 s for the model alone (Member 3) |
| Laptop CPU and RAM | Intel Core i7-9750H @ 2.60 GHz (6 cores, 12 threads), 15.8 GB RAM |

(La fila "Size on disk" puede quedar como está: 253.17 MB es el model.safetensors; la carpeta completa models/qa-final pesa 253.9 MB.)

## === SECCION 7: AGREGA estos dos puntos después de los que ya existen ===

3. **Problem:** our first `app.py` did not match the contract: `qa_api_contract.yaml` says the 401 response should carry `WWW-Authenticate: Bearer`, and ours did not. **Cause:** we wrote the auth handler from the guide's text and had not compared it with the YAML line by line. **Fix:** the 401 handler now adds the header, and the contract tests check the 401 cases. It was caught by reading the YAML before the first Stage 4 commit, so it is fixed in the commit that introduces `app.py`. **Commit:** `<HASH_1>`

4. **Problem:** `POST /predict` through ngrok hung. The status line and headers (200) arrived, but the body did not, and the ngrok inspector showed requests waiting for a response. In the first latency run 30 of 50 requests failed (mean 3.47 s, against 0.16 s on localhost). **Cause:** not fully identified; the local server was fine, and the most likely cause is an ngrok agent that had been open for hours and was in a bad state. **Fix:** restarting the agent as `ngrok http 127.0.0.1:8000`; after that 50 of 50 requests succeeded (mean 0.333 s, max 0.732 s). There was no code change; it was diagnosed with `scripts/measure_latency.py`, which reports the error types. **Commit:** `<HASH_2>`
