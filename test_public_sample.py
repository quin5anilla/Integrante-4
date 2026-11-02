"""Paso 12: casos de public_sample.json contra la API.
- test_contract_*: valida el CONTRATO (corre siempre, incluso con QA_USE_MOCK=1).
- test_correct_*: valida la RESPUESTA correcta (se salta con el predictor simulado)."""
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
SAMPLE = Path(__file__).resolve().parent.parent / "public_sample.json"
ITEMS = json.loads(SAMPLE.read_text(encoding="utf-8"))["items"]
IDS = [i["id"] for i in ITEMS]


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("QA_API_TOKEN", TOKEN)
    os.environ.setdefault("QA_TEAM_ID", "equipo_x")
    import app as app_module

    with TestClient(app_module.app, raise_server_exceptions=False) as c:
        for _ in range(600):  # hasta 60 s (el modelo real tarda en cargar)
            if c.get("/health").status_code == 200:
                break
            time.sleep(0.1)
        yield c


def _post(client, item):
    body = {k: item[k] for k in ("id", "context", "question")}  # sin answers ni is_impossible
    t0 = time.perf_counter()
    r = client.post("/predict", json=body, headers={"Authorization": f"Bearer {os.environ['QA_API_TOKEN']}"})
    return r, time.perf_counter() - t0


@pytest.mark.parametrize("item", ITEMS, ids=IDS)
def test_contract(client, item):
    r, _ = _post(client, item)
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == item["id"]
    assert 0.0 <= j["score"] <= 1.0
    if j["answer"] is None:
        assert j["start"] is None
    else:
        assert isinstance(j["start"], int) and j["start"] >= 0
        assert item["context"][j["start"]:j["start"] + len(j["answer"])] == j["answer"]


@pytest.mark.skipif(os.environ.get("QA_USE_MOCK") == "1", reason="predictor simulado")
@pytest.mark.parametrize("item", ITEMS, ids=IDS)
def test_correct(client, item):
    r, dt = _post(client, item)
    j = r.json()
    if item["is_impossible"]:
        assert j["answer"] is None and j["start"] is None
    else:
        assert any(j["answer"] == a["text"] and j["start"] == a["start"] for a in item["answers"]), j
    assert dt < 5.0  # limite por peticion del docente
