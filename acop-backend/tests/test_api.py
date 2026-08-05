def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "service" in response.json()


def test_create_and_list_cluster(client):
    response = client.post("/api/v1/clusters", json={
        "name": "test-cluster-1", "provider": "on-prem", "region": "local"
    })
    assert response.status_code == 201
    cluster = response.json()
    assert cluster["name"] == "test-cluster-1"

    response = client.get("/api/v1/clusters")
    assert response.status_code == 200
    assert any(c["name"] == "test-cluster-1" for c in response.json())


def test_create_incident(client):
    cluster_resp = client.post("/api/v1/clusters", json={"name": "test-cluster-2", "provider": "aws-eks"})
    cluster_id = cluster_resp.json()["id"]

    response = client.post("/api/v1/incidents", json={
        "cluster_id": cluster_id,
        "title": "Test incident: high memory usage",
        "severity": "high",
        "resource_type": "pod",
        "resource_name": "test-pod-1",
    })
    assert response.status_code == 201
    incident = response.json()
    assert incident["status"] == "open"
    assert incident["severity"] == "high"


def test_agents_status(client):
    response = client.get("/api/v1/agents/status")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert len(data["agents"]) == 4


def test_anomaly_check_no_history(client):
    response = client.post("/api/v1/metrics/anomaly-check", json={
        "cluster_id": "nonexistent", "resource_name": "nonexistent-pod"
    })
    assert response.status_code == 200
    assert response.json()["is_anomalous"] is False
