from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "ClauseGuard"
    assert data["status"] == "online"
    assert "version" in data
    assert "docs" in data


def test_health_check_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "ClauseGuard"
    assert "timestamp" in data


def test_system_status_endpoint(client: TestClient):
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["database"]["status"] == "healthy"
    assert data["storage"]["status"] == "healthy"
    assert "counts" in data
    assert "policies" in data["counts"]
    assert "claims" in data["counts"]
    assert "findings" in data["counts"]
