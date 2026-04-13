import logging
import os

import mlflow
import pandas as pd
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def load_config(path: str = "configs/config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config()

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)
    logger.info("MLflow tracking URI: %s", tracking_uri)

    threshold = float(cfg["decision"]["threshold"])
    test_path = cfg["predict"]["test_path"]
    output_path = cfg["predict"]["output_path"]

    # Charge le modèle depuis le registry via l'alias @production (ou env var MODEL_URI)
    model_name = cfg["mlflow"]["model_name"]
    model_uri = os.environ.get(
        "MODEL_URI",
        cfg["mlflow"].get("model_uri", f"models:/{model_name}@production"),
    )
    logger.info("Chargement du modèle depuis : %s", model_uri)
    model = mlflow.pyfunc.load_model(model_uri)

    # Chargement des données de test
    logger.info("Chargement des données de test : %s", test_path)
    df = pd.read_csv(test_path)

    if "Id" in df.columns:
        ids = df["Id"].copy()
    else:
        ids = pd.Series(range(len(df)), name="Id")

    X = df.drop(columns=["SeriousDlqin2yrs", "Id"], errors="ignore")

    # Prédiction
    logger.info("Prédiction sur %d lignes...", len(X))
    p = model.predict(X)
    prob = pd.Series(p).astype(float)

    # Politique : reject si proba >= seuil
    decision = (prob >= threshold).map({True: "REJECT", False: "ACCEPT"})

    out = pd.DataFrame(
        {
            "Id": ids.values,
            "Probability": prob.values,
            "Decision": decision.values,
            "Threshold": threshold,
            "ModelURI": model_uri,
        }
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    out.to_csv(output_path, index=False)
    logger.info("Prédictions sauvegardées : %s", output_path)
    logger.info("Aperçu :\n%s", out.head(10).to_string())


if __name__ == "__main__":
    main()
