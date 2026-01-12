import importlib
import sys
from pathlib import Path

import mlflow.sklearn
import pytest
from fastapi.testclient import TestClient


class DummyModel:
    def predict_proba(self, x):
        # always return proba=0.1 for class 1
        return [[0.9, 0.1] for _ in x]


@pytest.fixture(scope="session")
def client():
    """
    Important:
    api.py loads the MLflow model at import time.
    In CI/local tests we don't want to reach MLflow/MinIO, so we patch mlflow.sklearn.load_model
    BEFORE importing api.py.

    Also: ensure repo root is in sys.path so `import api` works reliably.
    """
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    def _fake_load_model(_uri: str):
        return DummyModel()

    # Patch loader BEFORE importing api
    mlflow.sklearn.load_model = _fake_load_model  # type: ignore[assignment]

    # Import or reload api cleanly
    if "api" in sys.modules:
        api = importlib.reload(sys.modules["api"])
    else:
        api = importlib.import_module("api")

    return TestClient(api.app)
