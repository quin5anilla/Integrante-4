import os
import time

import pytest
from fastapi.testclient import TestClient

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
CTX = "The Lempa River is the longest river in El Salvador, flowing about 422 km to the Pacific."
OK = {"id": "q-1", "context": CTX, "question": "How long is the Lempa River?"}


@pytest.fixture(scope="module")
def client():
    os.environ.update(QA_API_TOKEN=TOKEN, QA_USE_MOCK="1", QA_TEAM_ID="equipo_x")
    import app as app_module

    with TestClient(app_module.app, raise_server_exceptions=False) as c:
        for _ in range(50):
            if c.get("/health").status_code == 200:
                break
            time.sleep(0.1)
        yield c


def test_health_public(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


@pytest.mark.parametrize("h", [{}, {"Authorization": "Bearer wrong"},
                               {"Authorization": f"bearer {TOKEN}"}, {"Authorization": TOKEN}])
def test_info_unauthorized(client, h):
    r = client.get("/info", headers=h)
    assert r.status_code == 401 and r.json()["error"] == "unauthorized"


def test_info_ok(client):
    r = client.get("/info", headers=AUTH)
    j = r.json()
    assert r.status_code == 200 and isinstance(j["params"], int)
    assert j["team"] and j["model"]


def test_predict_requires_auth(client):
    assert client.post("/predict", json=OK).status_code == 401
    assert client.post("/predict", json={}).status_code == 401


def test_predict_ok(client):
    r = client.post("/predict", json=OK, headers=AUTH)
    j = r.json()
    assert r.status_code == 200 and j["id"] == "q-1"
    assert CTX[j["start"]:j["start"] + len(j["answer"])] == j["answer"]
    assert 0 <= j["score"] <= 1


def test_predict_null(client):
    r = client.post("/predict", json={**OK, "question": "impossible?"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["answer"] is None and r.json()["start"] is None


@pytest.mark.parametrize("body", [
    {"context": CTX, "question": "q"},
    {"id": "a", "question": "q"},
    {"id": "a", "context": CTX},
    {**OK, "id": "x" * 65},
    {**OK, "context": "x" * 5001},
    {**OK, "question": "x" * 501},
    {**OK, "foo": "bar"},
    {**OK, "context": None},
    {**OK, "id": 123},
    [OK],
])
def test_predict_bad_request(client, body):
    r = client.post("/predict", json=body, headers=AUTH)
    assert r.status_code in (400, 422) and r.json()["error"] == "bad_request"


def test_predict_malformed_json(client):
    r = client.post("/predict", content="{no json", headers={**AUTH, "Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["error"] == "bad_request"


def test_limits_accepted(client):
    r = client.post("/predict", json={"id": "x" * 64, "context": "5 " + "a" * 4998, "question": "q"}, headers=AUTH)
    assert r.status_code == 200
