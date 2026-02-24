"""
tests/test_teams.py
~~~~~~~~~~~~~~~~~~~
Integration tests for /api/teams.
"""


def test_list_teams_empty(client):
    r = client.get("/api/teams")
    assert r.status_code == 200
    assert r.json() == []


def test_create_team(client):
    r = client.post("/api/teams", json={
        "slug": "alpha",
        "name": "Alpha Team",
        "contact_email": "alpha@example.com",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "alpha"
    assert data["name"] == "Alpha Team"
    assert data["contact_email"] == "alpha@example.com"
    assert "id" in data


def test_get_team(client):
    client.post("/api/teams", json={"slug": "beta", "name": "Beta Team"})
    r = client.get("/api/teams/beta")
    assert r.status_code == 200
    assert r.json()["slug"] == "beta"


def test_get_team_not_found(client):
    r = client.get("/api/teams/no-such-team")
    assert r.status_code == 404


def test_update_team_name(client):
    client.post("/api/teams", json={"slug": "gamma", "name": "Old Name"})
    r = client.patch("/api/teams/gamma", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_list_teams_multiple(client):
    client.post("/api/teams", json={"slug": "t1", "name": "Team One"})
    client.post("/api/teams", json={"slug": "t2", "name": "Team Two"})
    r = client.get("/api/teams")
    assert r.status_code == 200
    slugs = {t["slug"] for t in r.json()}
    assert slugs == {"t1", "t2"}


def test_wrong_token_returns_401(client):
    r = client.get("/api/teams", headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401
