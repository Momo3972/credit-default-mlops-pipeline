"""
evaluate.py — Évaluation du modèle depuis MLflow Model Registry.

Charge le modèle enregistré (alias @production ou MODEL_URI), l'évalue sur le
dataset de test et logue les métriques dans MLflow sous un run dédié.
"""

import logging
import os

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import (
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def load_config(path: str = "configs/config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def metrics_at_threshold(y_true: np.ndarray, proba: np.ndarray, t: float) -> dict:
    y_pred = (proba >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    accept_rate = float((y_pred == 0).mean())
    reject_rate = float((y_pred == 1).mean())

    return {
        "threshold": t,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "precision_default": float(precision),
        "recall_default": float(recall),
        "f1_default": float(f1),
        "accept_rate": accept_rate,
        "reject_rate": reject_rate,
    }


def main() -> None:
    cfg = load_config()

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(cfg["mlflow"]["experiment_name"])
    logger.info("MLflow tracking URI : %s", tracking_uri)

    # ── Chargement du modèle depuis le registry ──────────────────────────────
    model_name = cfg["mlflow"]["model_name"]
    model_uri = os.environ.get(
        "MODEL_URI",
        cfg["mlflow"].get("model_uri", f"models:/{model_name}@production"),
    )
    logger.info("Chargement du modèle depuis : %s", model_uri)
    model = mlflow.sklearn.load_model(model_uri)

    # ── Données de test ───────────────────────────────────────────────────────
    df = pd.read_csv(cfg["data"]["path"])
    y = df[cfg["data"]["target"]].astype(int)
    X = df.drop(columns=[cfg["data"]["target"]])

    _, X_test, _, y_test = train_test_split(
        X,
        y,
        test_size=cfg["train"]["test_size"],
        random_state=cfg["train"]["random_state"],
        stratify=y if y.nunique() == 2 else None,
    )
    logger.info("Dataset de test : %d lignes", len(X_test))

    # ── Métriques ─────────────────────────────────────────────────────────────
    proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    logger.info("ROC AUC : %.4f", auc)

    thresholds = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
    rows = [metrics_at_threshold(y_test.values, proba, t) for t in thresholds]
    results_df = pd.DataFrame(rows).sort_values(
        ["recall_default", "reject_rate"], ascending=[False, True]
    )

    logger.info("\nTop thresholds (recall_default desc, reject_rate asc) :\n%s", results_df.to_string(index=False))

    # ── Log dans MLflow ───────────────────────────────────────────────────────
    with mlflow.start_run(run_name=f"evaluate-{model_uri.replace('/', '-')}"):
        mlflow.log_param("model_uri", model_uri)
        mlflow.log_param("eval_dataset", cfg["data"]["path"])
        mlflow.log_metric("roc_auc", auc)

        # Métriques au seuil de décision configuré
        threshold_cfg = float(cfg["decision"]["threshold"])
        best = metrics_at_threshold(y_test.values, proba, threshold_cfg)
        mlflow.log_metric("precision_default", best["precision_default"])
        mlflow.log_metric("recall_default", best["recall_default"])
        mlflow.log_metric("f1_default", best["f1_default"])
        mlflow.log_metric("accept_rate", best["accept_rate"])
        mlflow.log_metric("reject_rate", best["reject_rate"])

        # Sauvegarde du tableau complet en artefact
        out_path = "/tmp/threshold_analysis.csv"
        results_df.to_csv(out_path, index=False)
        mlflow.log_artifact(out_path, artifact_path="evaluation")

        logger.info(
            "Métriques loguées dans MLflow — seuil=%.2f | AUC=%.4f | recall=%.4f",
            threshold_cfg,
            auc,
            best["recall_default"],
        )


if __name__ == "__main__":
    main()
