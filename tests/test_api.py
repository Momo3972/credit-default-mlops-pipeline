def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "model_uri" in body


def test_meta_ok(client):
    r = client.get("/meta")
    assert r.status_code == 200
    body = r.json()
    # keys expected in your api.py
    for k in ["model_uri", "threshold", "n_features_expected", "git_commit", "model_version"]:
        assert k in body


def test_boom_is_500(client):
    r = client.get("/boom")
    assert r.status_code == 500
    assert r.json()["detail"] == "boom"


def test_predict_wrong_shape_422(client):
    # Missing "data.features" should be 422 (validation)
    r = client.post("/predict", json={})
    assert r.status_code in (422, 400)

    # Wrong number of features should be 422 (your contract)
    r = client.post("/predict", json={"data": {"features": [0.0, 1.0]}})
    assert r.status_code == 422


def test_predict_ok_200(client):
    features = [0.0] * 11
    r = client.post("/predict", json={"data": {"features": features}})
    assert r.status_code == 200
    body = r.json()
    assert "probability" in body
    assert "decision" in body
    assert "threshold" in body
    assert "model_uri" in body
