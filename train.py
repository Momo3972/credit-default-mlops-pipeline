import os

import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def load_config(path="configs/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    cfg = load_config()

    # Tracking URI (env var overrides default)
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment(cfg["mlflow"]["experiment_name"])

    # ---- data
    df = pd.read_csv(cfg["data"]["path"])
    y = df[cfg["data"]["target"]]
    X = df.drop(columns=[cfg["data"]["target"]])

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=cfg["train"]["test_size"],
        random_state=cfg["train"]["random_state"],
        stratify=y if y.nunique() == 2 else None,
    )

    # ---- model (Pipeline: impute NaN + scale + logistic regression)
    model_cfg = cfg["model"]
    if model_cfg["type"] != "logistic_regression":
        raise ValueError("Only logistic_regression implemented in this template")

    params = model_cfg.get("params", {})

    clf = LogisticRegression(
        C=params.get("C", 1.0),
        max_iter=params.get("max_iter", 1000),
    )

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("clf", clf),
        ]
    )

    with mlflow.start_run():
        # params
        mlflow.log_params(
            {
                "test_size": cfg["train"]["test_size"],
                "random_state": cfg["train"]["random_state"],
                **params,
            }
        )

        # train
        model.fit(X_train, y_train)

        # metrics
        pred = model.predict(X_test)
        acc = accuracy_score(y_test, pred)
        mlflow.log_metric("accuracy", float(acc))

        # ROC AUC only if binary and predict_proba exists
        if y_test.nunique() == 2 and hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_test)[:, 1]
            auc = roc_auc_score(y_test, proba)
            mlflow.log_metric("roc_auc", float(auc))

        # log + register
        model_name = cfg["mlflow"]["model_name"]
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=model_name,
        )

        print("Logged & registered model:", model_name)


if __name__ == "__main__":
    main()
