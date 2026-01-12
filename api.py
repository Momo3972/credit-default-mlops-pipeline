import os

import mlflow
import mlflow.sklearn
import yaml
from fastapi import FastAPI, HTTPException
from mlflow.tracking import MlflowClient
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

app = FastAPI(title="Credit Default Scoring API")

# Prometheus metrics on /metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# ---------- Config ----------
CONFIG_PATH = "configs/config.yaml"


def load_model_uri() -> str:
    # 1) ENV > 2) config.yaml > 3) fallback
    env_uri = os.getenv("MODEL_URI")
    if env_uri:
        return env_uri

    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("mlflow", {}).get("model_uri", "models:/credit-default-model@production")
    except Exception:
        return "models:/credit-default-model@production"


MODEL_URI = load_model_uri()

EXPECTED_N_FEATURES = 11
THRESHOLD = 0.05
GIT_COMMIT = os.getenv("GIT_COMMIT", "unknown")


def get_model_version_from_registry(model_uri: str) -> str:
    """
    Try to get model version from MLflow Model Registry.
    Returns "unknown" if not retrievable.
    Supports:
      - models:/name/Production
      - models:/name/Staging
      - models:/name/123
      - models:/name@alias
    """
    try:
        if not model_uri.startswith("models:/"):
            return "unknown"

        client = MlflowClient()

        # Alias: models:/name@alias
        if "@" in model_uri:
            left, alias = model_uri.split("@", 1)
            name = left.replace("models:/", "").strip("/")
            try:
                mv = client.get_model_version_by_alias(name, alias)
                return str(getattr(mv, "version", "unknown"))
            except Exception:
                return "unknown"

        parts = model_uri.replace("models:/", "").strip("/").split("/")
        if len(parts) < 2:
            return "unknown"

        name, ref = parts[0], parts[1]

        # Direct numeric version
        if ref.isdigit():
            return ref

        # Stage (Production/Staging/...)
        try:
            versions = client.get_latest_versions(name, stages=[ref])
            if versions:
                return str(getattr(versions[0], "version", "unknown"))
        except Exception:
            pass

        return "unknown"
    except Exception:
        return "unknown"


# ---------- Load model ----------
try:
    model = mlflow.sklearn.load_model(MODEL_URI)
except Exception as e:
    raise RuntimeError(f"Failed to load model from {MODEL_URI}: {e}") from e


# ---------- Schema ----------
class PredictData(BaseModel):
    features: list[float] = Field(..., description="Ordered feature vector", min_length=1)


class PredictRequest(BaseModel):
    data: PredictData


class PredictResponse(BaseModel):
    probability: float
    decision: str
    threshold: float
    model_uri: str


# ---------- Routes ----------
@app.get("/health")
def health():
    return {"status": "ok", "model_uri": MODEL_URI}


@app.get("/meta")
def meta():
    return {
        "model_uri": MODEL_URI,
        "threshold": THRESHOLD,
        "n_features_expected": EXPECTED_N_FEATURES,
        "git_commit": GIT_COMMIT,
        "model_version": get_model_version_from_registry(MODEL_URI),
    }


@app.get("/boom")
def boom():
    raise HTTPException(status_code=500, detail="boom")


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    x = request.data.features

    if len(x) != EXPECTED_N_FEATURES:
        raise HTTPException(
            status_code=422,
            detail=f"Model expects {EXPECTED_N_FEATURES} features, got {len(x)}",
        )

    proba = float(model.predict_proba([x])[0][1])
    decision = "REJECT" if proba >= THRESHOLD else "ACCEPT"

    return {
        "probability": proba,
        "decision": decision,
        "threshold": THRESHOLD,
        "model_uri": MODEL_URI,
    }
