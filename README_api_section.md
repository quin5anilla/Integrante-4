
## Running the API (Stage 4)

Requirements: Python 3.11+ (tested on 3.11.9 and 3.13.7), the dependencies in `requirements.txt`
(install the CPU build of PyTorch from https://pytorch.org/get-started/locally/ if pip gives a CUDA build),
and the model files in `models/qa-final/` (not in Git; shared by Member 2 through a shared folder).

```powershell
python -m pip install -r requirements.txt
$env:QA_API_TOKEN = "<token given by the instructor>"   # never commit it
$env:QA_TEAM_ID = "team-02"
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
```

`GET /health` returns 503 `{"status":"loading"}` while the model loads and 200 `{"status":"ok"}` when ready.
`/info` and `/predict` need `Authorization: Bearer <QA_API_TOKEN>`.

Public HTTPS tunnel (main: ngrok, backup: Cloudflare Quick Tunnel):

```powershell
ngrok config add-authtoken <your ngrok token>   # once; not the same as QA_API_TOKEN
ngrok http 127.0.0.1:8000
cloudflared tunnel --url http://localhost:8000  # backup, the URL changes on every restart
```

Tests (run the two files separately; `test_api_contract.py` forces a mock predictor):

```powershell
$env:QA_USE_MOCK = "1"; python -m pytest tests\test_api_contract.py -q
Remove-Item Env:QA_USE_MOCK; python -m pytest tests\test_public_sample.py -q   # uses the real model
python scripts\measure_latency.py --url http://localhost:8000 --rounds 10        # latency, writes logs/latency_results.json
```

`QA_USE_MOCK=1` is only for development and must not be set when serving.
