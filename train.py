"""
train.py — Entraînement multi-algorithmes avec tracking MLflow.

Compare LogisticRegression, RandomForest et GradientBoosting.
Le meilleur modèle (ROC AUC) est enregistré dans le Model Registry.
"""

import logging
import os

import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def load_config(path: str = "configs/config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_pipeline(clf) -> Pipeline:
    """Construit un Pipeline sklearn : imputation médiane + normalisation + classifieur."""
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("clf", clf),
        ]
    )


def get_candidates(cfg: dict) -> dict[str, Pipeline]:
    """Retourne les candidats à comparer selon la config."""
    params = cfg["model"].get("params", {})
    model_type = cfg["model"].get("type", "all")

    candidates = {}

    if model_type in ("logistic_regression", "all"):
        candidates["logistic_regression"] = build_pipeline(
            LogisticRegression(
                C=params.get("C", 1.0),
                max_iter=params.get("max_iter", 1000),
                class_weight="balanced",
            )
        )

    if model_type in ("random_forest", "all"):
        candidates["random_forest"] = build_pipeline(
            RandomForestClassifier(
                n_estimators=params.get("n_estimators", 200),
                max_depth=params.get("max_depth", None),
                class_weight="balanced",
                random_state=cfg["train"]["random_state"],
                n_jobs=-1,
            )
        )

    if model_type in ("gradient_boosting", "all"):
        candidates["gradient_boosting"] = build_pipeline(
            GradientBoostingClassifier(
                n_estimators=params.get("n_estimators", 100),
                learning_rate=params.get("learning_rate", 0.1),
                max_depth=params.get("max_depth", 3),
                random_state=cfg["train"]["random_state"],
            )
        )

    if not candidates:
        raise ValueError(
            f"Type de modèle inconnu : {model_type}. Valeurs valides : logistic_regression, random_forest, gradient_boosting, all"
        )

    return candidates


def train_and_log(
    name: str,
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    cfg: dict,
) -> tuple[float, str]:
    """Entraîne un pipeline, logue les métriques dans MLflow. Retourne (roc_auc, run_id)."""
    threshold = float(cfg["decision"]["threshold"])

    with mlflow.start_run(run_name=name) as run:
        mlflow.log_param("model_type", name)
        mlflow.log_param("test_size", cfg["train"]["test_size"])
        mlflow.log_param("random_state", cfg["train"]["random_state"])
        mlflow.log_param("decision_threshold", threshold)

        logger.info("[%s] Entraînement en cours...", name)
        pipeline.fit(X_train, y_train)

        proba = pipeline.predict_proba(X_test)[:, 1]
        y_pred = (proba >= threshold).astype(int)

        auc = roc_auc_score(y_test, proba)
        acc = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        mlflow.log_metrics(
            {
                "roc_auc": float(auc),
                "accuracy": float(acc),
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
            }
        )

        logger.info("[%s] ROC AUC=%.4f | Recall=%.4f | F1=%.4f", name, auc, recall, f1)
        return auc, run.info.run_id


def main() -> None:
    cfg = load_config()

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(cfg["mlflow"]["experiment_name"])
    logger.info(
        "MLflow tracking URI: %s | Experiment: %s", tracking_uri, cfg["mlflow"]["experiment_name"]
    )

    # ── Données ──────────────────────────────────────────────────────────────
    df = pd.read_csv(cfg["data"]["path"])
    y = df[cfg["data"]["target"]]
    X = df.drop(columns=[cfg["data"]["target"]])
    logger.info("Dataset chargé : %d lignes, %d features", len(X), X.shape[1])

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=cfg["train"]["test_size"],
        random_state=cfg["train"]["random_state"],
        stratify=y if y.nunique() == 2 else None,
    )
    logger.info("Split : train=%d | test=%d", len(X_train), len(X_test))

    # ── Entraînement et comparaison ─────────────────────────────────────────
    candidates = get_candidates(cfg)
    results: list[tuple[float, str, str]] = []  # (auc, name, run_id)

    for name, pipeline in candidates.items():
        auc, run_id = train_and_log(name, pipeline, X_train, X_test, y_train, y_test, cfg)
        results.append((auc, name, run_id))

    # ── Enregistrement du meilleur modèle ────────────────────────────────────
    results.sort(reverse=True, key=lambda t: t[0])
    best_auc, best_name, best_run_id = results[0]

    logger.info("🏆 Meilleur modèle : %s (ROC AUC=%.4f)", best_name, best_auc)

    # Re-log + enregistrement dans le registry avec le meilleur run
    best_pipeline = candidates[best_name]
    model_name = cfg["mlflow"]["model_name"]

    with mlflow.start_run(run_id=best_run_id):
        mlflow.sklearn.log_model(
            sk_model=best_pipeline,
            artifact_path="model",
            registered_model_name=model_name,
        )

    logger.info("Modèle enregistré dans le registry : %s", model_name)
    logger.info("Prochaine étape : promouvoir la version avec `make promote` ou via l'UI MLflow.")


if __name__ == "__main__":
    main()
