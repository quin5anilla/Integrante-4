"""API QA (integrante 4). Cumple qa_api_contract.yaml: si difiere de este archivo, manda el YAML."""
import hmac
import os
import re
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictStr

MODEL_ID = "distilbert/distilbert-base-uncased"  # confirmar con integrante 2
MAX_SEQ_LENGTH = 384
DOC_STRIDE = 128

STATE = {"ready": False, "predict": None, "params": None, "error": None}


class ApiError(Exception):
    def __init__(self, status: int, error: str, detail: str | None = None):
        self.status, self.error, self.detail = status, error, detail


def _body(error: str, detail: str | None = None) -> dict:
    return {"error": error, "detail": detail} if detail else {"error": error}


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # additionalProperties: false
    id: StrictStr = Field(min_length=1, max_length=64)
    context: StrictStr = Field(min_length=1, max_length=5000)
    question: StrictStr = Field(min_length=1, max_length=500)


# ---------- Carga del predictor ----------
def _mock_predict(context: str, question: str) -> dict:
    """SOLO PARA DESARROLLO (QA_USE_MOCK=1). Devuelve el primer numero del contexto."""
    m = re.search(r"\d[\d,.]*", context)
    if not m or "impossible" in question.lower():
        return {"answer": None, "start": None, "score": 0.5}
    return {"answer": m.group(0), "start": m.start(), "score": 0.9}


def _load():
    try:
        if os.environ.get("QA_USE_MOCK") == "1":
            STATE["predict"], STATE["params"] = _mock_predict, 66_000_000
        else:
            # Predictor real del integrante 3 (se ejecuta desde la raiz del repo).
            from src.inference.qa_inference import QAPredictor

            qa = QAPredictor()  # carga modelo y tokenizer UNA sola vez
            STATE["params"] = sum(p.numel() for p in qa.model.parameters())
            lock = threading.Lock()  # un modelo, una inferencia a la vez

            def _predict(context: str, question: str) -> dict:
                with lock:
                    return qa.predict(context, question)

            _predict("Warm up.", "What is this?")  # primera llamada lenta fuera del /predict
            STATE["predict"] = _predict
        STATE["ready"] = True
    except Exception as e:  # noqa: BLE001
        STATE["error"] = repr(e)
        print(f"[app] ERROR cargando el modelo: {e!r}", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("QA_API_TOKEN"):
        raise RuntimeError("Falta la variable de entorno QA_API_TOKEN")
    STATE.update(ready=False, predict=None, params=None, error=None)
    threading.Thread(target=_load, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


# ---------- Errores con el formato del YAML ----------
@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
    return JSONResponse(_body(exc.error, exc.detail), status_code=exc.status, headers=headers)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return JSONResponse(_body("bad_request", detail[:500]), status_code=400)


@app.exception_handler(Exception)
async def _unexpected(_: Request, exc: Exception):
    return JSONResponse(_body("internal_error", "unexpected error"), status_code=500)


# ---------- Seguridad ----------
def require_auth(request: Request):
    token = os.environ.get("QA_API_TOKEN", "")
    header = request.headers.get("authorization", "")
    expected = f"Bearer {token}"
    if not token or not hmac.compare_digest(header.encode(), expected.encode()):
        raise ApiError(401, "unauthorized", "missing or invalid token")


# ---------- Endpoints ----------
@app.get("/health")
def health():
    if STATE["ready"]:
        return {"status": "ok"}
    return JSONResponse({"status": "loading"}, status_code=503)


@app.get("/info", dependencies=[Depends(require_auth)])
def info():
    if not STATE["ready"]:
        raise ApiError(503, "internal_error", "model loading")
    return {
        "team": os.environ.get("QA_TEAM_ID", "EQUIPO_PENDIENTE"),  # sin espacios
        "model": MODEL_ID,
        "params": int(STATE["params"]),
        "max_seq_length": MAX_SEQ_LENGTH,
        "doc_stride": DOC_STRIDE,
    }


@app.post("/predict", dependencies=[Depends(require_auth)])
def predict_endpoint(req: PredictRequest):
    if not STATE["ready"]:
        raise ApiError(503, "internal_error", "model loading")
    try:
        out = STATE["predict"](req.context, req.question)
        answer, start, score = out["answer"], out["start"], out["score"]
        if answer is None:
            assert start is None
        else:
            assert isinstance(start, int) and not isinstance(start, bool) and start >= 0
            assert req.context[start:start + len(answer)] == answer
        assert isinstance(score, (int, float)) and not isinstance(score, bool)
        assert 0.0 <= score <= 1.0
    except Exception as e:  # noqa: BLE001
        raise ApiError(500, "internal_error", "inference failed") from e
    return {"id": req.id, "answer": answer, "start": start, "score": float(score)}
