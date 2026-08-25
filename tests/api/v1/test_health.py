def test_liveness_returns_healthy(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["probe"] == "liveness"
    assert "services" not in body
