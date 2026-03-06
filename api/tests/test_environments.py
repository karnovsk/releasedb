"""
api/tests/test_environments.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration tests for /api/environments.
"""


def test_list_environments_empty(client):
    r = client.get("/api/environments")
    assert r.status_code == 200
    assert r.json() == []


def test_create_environment(client):
    r = client.post("/api/environments", json={
        "slug": "staging",
        "name": "Staging",
        "tier": 2,
        "requires_approval": False,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "staging"
    assert data["name"] == "Staging"
    assert data["tier"] == 2
    assert data["requires_approval"] is False
    assert "id" in data


def test_create_environment_with_config(client):
    r = client.post("/api/environments", json={
        "slug": "prod",
        "name": "Production",
        "tier": 3,
        "requires_approval": True,
        "config": {"region": "us-east-1"},
    })
    assert r.status_code == 201
    data = r.json()
    assert data["config"] == {"region": "us-east-1"}
    assert data["requires_approval"] is True


def test_get_environment(client):
    client.post("/api/environments", json={
        "slug": "dev",
        "name": "Development",
        "tier": 1,
        "requires_approval": False,
    })
    r = client.get("/api/environments/dev")
    assert r.status_code == 200
    assert r.json()["slug"] == "dev"


def test_get_environment_not_found(client):
    r = client.get("/api/environments/no-such-env")
    assert r.status_code == 404


def test_update_environment(client):
    client.post("/api/environments", json={
        "slug": "qa",
        "name": "QA",
        "tier": 2,
        "requires_approval": False,
    })
    r = client.patch("/api/environments/qa", json={"requires_approval": True})
    assert r.status_code == 200
    assert r.json()["requires_approval"] is True


def test_list_environments_ordered_by_tier(client):
    client.post("/api/environments", json={"slug": "prod", "name": "Production", "tier": 3, "requires_approval": True})
    client.post("/api/environments", json={"slug": "dev", "name": "Development", "tier": 1, "requires_approval": False})
    client.post("/api/environments", json={"slug": "staging", "name": "Staging", "tier": 2, "requires_approval": False})
    r = client.get("/api/environments")
    assert r.status_code == 200
    tiers = [e["tier"] for e in r.json()]
    assert tiers == sorted(tiers)
