import os

import pytest
import requests

pytestmark = pytest.mark.integration

API_URL = os.getenv("API_URL", "http://localhost:8000")


def test_health():
    r = requests.get(f"{API_URL}/health", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ok"


def test_meta():
    r = requests.get(f"{API_URL}/meta", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    # Contrats minimaux "portfolio"
    assert body.get("n_features_expected") == 11
    assert "model_uri" in body
    assert "threshold" in body
    assert "git_commit" in body


def test_predict_with_11_features():
    payload = {"data": {"features": [0.0] * 11}}
    r = requests.post(f"{API_URL}/predict", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "probability" in body
    assert "decision" in body
    assert "threshold" in body
    assert "model_uri" in body