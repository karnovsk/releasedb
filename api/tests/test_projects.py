"""
api/tests/test_projects.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration tests for /api/projects.
"""


def test_list_projects_empty(client):
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert r.json() == []


def test_create_project(client):
    r = client.post("/api/projects", json={
        "name": "Customer Portal",
        "related_project": "Mobile App",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Customer Portal"
    assert data["related_project"] == "Mobile App"
    assert "id" in data
    assert "created_at" in data


def test_create_project_minimal(client):
    r = client.post("/api/projects", json={"name": "Minimal Project"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Minimal Project"
    assert data["related_project"] is None


def test_get_project(client):
    created = client.post("/api/projects", json={"name": "IoT Platform"}).json()
    r = client.get(f"/api/projects/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert r.json()["name"] == "IoT Platform"


def test_get_project_not_found(client):
    r = client.get("/api/projects/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_update_project(client):
    created = client.post("/api/projects", json={"name": "Old Name"}).json()
    r = client.patch(f"/api/projects/{created['id']}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_update_project_no_changes(client):
    created = client.post("/api/projects", json={"name": "Stable"}).json()
    r = client.patch(f"/api/projects/{created['id']}", json={})
    assert r.status_code == 200
    assert r.json()["name"] == "Stable"


def test_list_projects_populated(client):
    client.post("/api/projects", json={"name": "Alpha"})
    client.post("/api/projects", json={"name": "Beta"})
    r = client.get("/api/projects")
    assert r.status_code == 200
    names = {p["name"] for p in r.json()}
    assert names == {"Alpha", "Beta"}
