import pandas as pd
import yaml
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def load_config(path="configs/config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def metrics_at_threshold(y_true, proba, t):
    y_pred = (proba >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )

    accept_rate = (y_pred == 0).mean()  # 0 = accept, 1 = refuse
    reject_rate = (y_pred == 1).mean()

    return {
        "t": t,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "precision_default": precision,
        "recall_default": recall,
        "f1_default": f1,
        "accept_rate": accept_rate,
        "reject_rate": reject_rate,
    }


def main():
    cfg = load_config()

    df = pd.read_csv(cfg["data"]["path"])
    y = df[cfg["data"]["target"]].astype(int)
    X = df.drop(columns=[cfg["data"]["target"]])

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=cfg["train"]["test_size"],
        random_state=cfg["train"]["random_state"],
        stratify=y if y.nunique() == 2 else None,
    )

    params = cfg["model"].get("params", {})
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

    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, proba)
    print(f"ROC AUC: {auc:.4f}")

    # teste plusieurs seuils
    thresholds = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
    rows = [metrics_at_threshold(y_test.values, proba, t) for t in thresholds]

    out = pd.DataFrame(rows)
    # tri : d'abord recall défaut desc, puis reject_rate asc (refuser moins si recall identique)
    out = out.sort_values(["recall_default", "reject_rate"], ascending=[False, True])

    print("\nTop thresholds (sorted by recall_default desc, reject_rate asc):")
    print(
        out[
            [
                "t",
                "precision_default",
                "recall_default",
                "f1_default",
                "accept_rate",
                "reject_rate",
                "fp",
                "fn",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
