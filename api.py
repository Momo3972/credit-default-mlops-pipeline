import logging
import os

import mlflow
import mlflow.sklearn
import yaml
from fastapi import FastAPI, HTTPException
from mlflow.tracking import MlflowClient
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Credit Default Scoring API",
    description="API de scoring de défaut de crédit — FastAPI + MLflow + Prometheus",
    version="1.0.0",
)

# Prometheus metrics exposées sur /metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# ── Chargement de la configuration ──────────────────────────────────────────
CONFIG_PATH = "configs/config.yaml"


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning(
            "Impossible de lire %s : %s — valeurs par défaut utilisées.", CONFIG_PATH, exc
        )
        return {}


_cfg = _load_config()


def _load_model_uri() -> str:
    """Priorité : ENV > config.yaml > fallback hardcodé."""
    env_uri = os.getenv("MODEL_URI")
    if env_uri:
        return env_uri
    return _cfg.get("mlflow", {}).get("model_uri", "models:/credit-default-model@production")


MODEL_URI = _load_model_uri()
EXPECTED_N_FEATURES: int = int(_cfg.get("model", {}).get("params", {}).get("n_features", 11))
THRESHOLD: float = float(_cfg.get("decision", {}).get("threshold", 0.05))
GIT_COMMIT: str = os.getenv("GIT_COMMIT", "unknown")

logger.info(
    "MODEL_URI=%s | THRESHOLD=%.3f | N_FEATURES=%d", MODEL_URI, THRESHOLD, EXPECTED_N_FEATURES
)


# ── Résolution de la version du modèle ──────────────────────────────────────
def get_model_version_from_registry(model_uri: str) -> str:
    """
    Résout la version du modèle depuis le MLflow Model Registry.
    Supporte : models:/name@alias  |  models:/name/123  |  models:/name/Stage
    Retourne "unknown" si non résolvable.
    """
    try:
        if not model_uri.startswith("models:/"):
            return "unknown"

        client = MlflowClient()

        # Alias : models:/name@alias
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

        if ref.isdigit():
            return ref

        try:
            versions = client.get_latest_versions(name, stages=[ref])
            if versions:
                return str(getattr(versions[0], "version", "unknown"))
        except Exception:
            pass

        return "unknown"
    except Exception:
        return "unknown"


# ── Chargement du modèle ────────────────────────────────────────────────────
try:
    logger.info("Chargement du modèle depuis : %s", MODEL_URI)
    model = mlflow.sklearn.load_model(MODEL_URI)
    logger.info("Modèle chargé avec succès.")
except Exception as e:
    raise RuntimeError(f"Impossible de charger le modèle depuis {MODEL_URI}: {e}") from e


# ── Schémas Pydantic ────────────────────────────────────────────────────────
class PredictData(BaseModel):
    features: list[float] = Field(
        ...,
        description=f"Vecteur de features ordonné ({EXPECTED_N_FEATURES} valeurs attendues)",
        min_length=1,
    )


class PredictRequest(BaseModel):
    data: PredictData


class PredictResponse(BaseModel):
    probability: float
    decision: str
    threshold: float
    model_uri: str


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Infrastructure"])
def health():
    """Statut de l'API et URI du modèle chargé."""
    return {"status": "ok", "model_uri": MODEL_URI}


@app.get("/meta", tags=["Infrastructure"])
def meta():
    """Métadonnées runtime : seuil, features attendues, commit Git, version modèle."""
    return {
        "model_uri": MODEL_URI,
        "threshold": THRESHOLD,
        "n_features_expected": EXPECTED_N_FEATURES,
        "git_commit": GIT_COMMIT,
        "model_version": get_model_version_from_registry(MODEL_URI),
    }


@app.get("/boom", tags=["Infrastructure"])
def boom():
    """Endpoint volontairement en erreur 500 — test d'observabilité."""
    raise HTTPException(status_code=500, detail="boom")


@app.post("/predict", response_model=PredictResponse, tags=["Prédiction"])
def predict(request: PredictRequest):
    """
    Prédit la probabilité de défaut de crédit.

    - **REJECT** si probabilité ≥ seuil
    - **ACCEPT** sinon
    """
    x = request.data.features

    if len(x) != EXPECTED_N_FEATURES:
        raise HTTPException(
            status_code=422,
            detail=f"Le modèle attend {EXPECTED_N_FEATURES} features, reçu {len(x)}",
        )

    proba = float(model.predict_proba([x])[0][1])
    decision = "REJECT" if proba >= THRESHOLD else "ACCEPT"

    return {
        "probability": proba,
        "decision": decision,
        "threshold": THRESHOLD,
        "model_uri": MODEL_URI,
    }
