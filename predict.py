import os

import mlflow
import pandas as pd
import yaml


def load_config(path="configs/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    cfg = load_config()

    # --- MLflow tracking (same logic as train.py)
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))

    model_name = cfg["mlflow"]["model_name"]
    threshold = float(cfg["decision"]["threshold"])

    test_path = cfg["predict"]["test_path"]
    output_path = cfg["predict"]["output_path"]

    # --- Load model from Model Registry (latest version by alias if you want later)
    # Here we lock to "champion" if present, otherwise you can lock to version number.
    # If you haven't set alias, use: models:/<name>/2
    model_uri = f"models:/{model_name}/2"
    model = mlflow.pyfunc.load_model(model_uri)

    # --- Load input
    df = pd.read_csv(test_path)

    # Keep an id column if present, else create one
    if "Id" in df.columns:
        ids = df["Id"].copy()
        X = df.drop(columns=["SeriousDlqin2yrs"], errors="ignore")
    else:
        ids = pd.Series(range(len(df)), name="Id")
        X = df.drop(columns=["SeriousDlqin2yrs"], errors="ignore")

    # --- Predict
    # Depending on how mlflow logs the sklearn pipeline, predict may return:
    # - probabilities, or
    # - class labels.
    # We'll handle both.
    p = model.predict(X)

    # Convert output to probability if it's class labels
    # If already float-ish in [0,1], keep it.
    prob = pd.Series(p).astype(float)

    # Decision policy: "refuser trop que prêter à tort" => reject if prob >= threshold
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
    print(f"Saved predictions to {output_path}")
    print(out.head(10))


if __name__ == "__main__":
    main()
