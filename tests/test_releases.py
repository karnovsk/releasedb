"""
tests/test_releases.py
~~~~~~~~~~~~~~~~~~~~~~
Integration tests for /api/releases (CRUD, field values, lineage).
"""

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def rt_id(client):
    """Create a team + release type config and return the config UUID."""
    client.post("/api/teams", json={"slug": "rel-team", "name": "Release Team"})
    r = client.post("/api/release-types", json={
        "slug": "fw-release",
        "team_slug": "rel-team",
        "display_name": "Firmware Release",
        "requires_approval": False,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _release(client, rt_id, *, name, version, **kwargs):
    """Create a release and assert success; return the response JSON."""
    payload = {
        "release_type_config_id": rt_id,
        "release_name": name,
        "version": version,
        **kwargs,
    }
    r = client.post("/api/releases", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------

def test_list_releases_empty(client, rt_id):
    r = client.get("/api/releases")
    assert r.status_code == 200
    assert r.json() == []


def test_create_release_defaults(client, rt_id):
    release = _release(client, rt_id, name="rel-1", version="1.0.0")
    assert release["release_name"] == "rel-1"
    assert release["version"] == "1.0.0"
    assert release["status"] == "draft"
    assert release["depends_on"] == []
    assert release["field_values"] == {}


def test_get_release(client, rt_id):
    created = _release(client, rt_id, name="get-me", version="2.0.0")
    r = client.get(f"/api/releases/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_release_not_found(client):
    r = client.get("/api/releases/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_update_release_status(client, rt_id):
    release = _release(client, rt_id, name="status-rel", version="1.0.0")
    r = client.patch(f"/api/releases/{release['id']}", json={"status": "approved"})
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_list_releases_filter_by_team(client, rt_id):
    _release(client, rt_id, name="r1", version="1.0.0")
    _release(client, rt_id, name="r2", version="2.0.0")
    r = client.get("/api/releases", params={"team_slug": "rel-team"})
    assert r.status_code == 200
    assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# Field values
# ---------------------------------------------------------------------------

def test_release_with_field_values(client, rt_id):
    # Add a string field to the release type
    client.post("/api/release-types/fw-release/fields", json={
        "field_key": "ticket",
        "label": "Ticket",
        "field_type": "string",
    })
    release = _release(
        client, rt_id,
        name="with-fields", version="1.0.0",
        field_values={"ticket": "JIRA-42"},
    )
    assert release["field_values"]["ticket"] == "JIRA-42"


# ---------------------------------------------------------------------------
# Dependency edges (depends_on)
# ---------------------------------------------------------------------------

def test_create_release_with_parent(client, rt_id):
    parent = _release(client, rt_id, name="parent", version="1.0.0")
    child = _release(
        client, rt_id,
        name="child", version="2.0.0",
        depends_on=[parent["id"]],
    )
    assert parent["id"] in child["depends_on"]


def test_depends_on_nonexistent_parent_returns_404(client, rt_id):
    r = client.post("/api/releases", json={
        "release_type_config_id": rt_id,
        "release_name": "bad",
        "version": "1.0.0",
        "depends_on": ["00000000-0000-0000-0000-000000000000"],
    })
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

def test_lineage_isolated_node(client, rt_id):
    """A release with no dependencies: one node, no edges."""
    release = _release(client, rt_id, name="lone", version="1.0.0")
    r = client.get(f"/api/releases/{release['id']}/lineage")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == release["id"]
    assert data["edges"] == []


def test_lineage_single_parent(client, rt_id):
    """Child → Parent: two nodes, one directed edge."""
    parent = _release(client, rt_id, name="parent", version="1.0.0")
    child = _release(
        client, rt_id,
        name="child", version="2.0.0",
        depends_on=[parent["id"]],
    )
    r = client.get(f"/api/releases/{child['id']}/lineage")
    assert r.status_code == 200
    data = r.json()

    node_ids = {n["id"] for n in data["nodes"]}
    assert node_ids == {parent["id"], child["id"]}

    assert len(data["edges"]) == 1
    edge = data["edges"][0]
    assert edge["from_release_id"] == child["id"]
    assert edge["to_release_id"] == parent["id"]


def test_lineage_chain(client, rt_id):
    """A ← B ← C: querying C returns 3 nodes and 2 edges."""
    a = _release(client, rt_id, name="a", version="1.0.0")
    b = _release(client, rt_id, name="b", version="2.0.0", depends_on=[a["id"]])
    c = _release(client, rt_id, name="c", version="3.0.0", depends_on=[b["id"]])

    r = client.get(f"/api/releases/{c['id']}/lineage")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2


def test_lineage_diamond(client, rt_id):
    """
    A ← B ← D
    A ← C ← D
    Querying D: 4 nodes, 4 edges (D→B, D→C, B→A, C→A).
    """
    a = _release(client, rt_id, name="a", version="1.0.0")
    b = _release(client, rt_id, name="b", version="2.0.0", depends_on=[a["id"]])
    c = _release(client, rt_id, name="c", version="3.0.0", depends_on=[a["id"]])
    d = _release(
        client, rt_id,
        name="d", version="4.0.0",
        depends_on=[b["id"], c["id"]],
    )

    r = client.get(f"/api/releases/{d['id']}/lineage")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) == 4
    assert len(data["edges"]) == 4


def test_lineage_not_found(client):
    r = client.get("/api/releases/00000000-0000-0000-0000-000000000000/lineage")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def test_release_created_event_logged(client, rt_id):
    release = _release(client, rt_id, name="evt-rel", version="1.0.0",
                       created_by="alice")
    r = client.get(f"/api/releases/{release['id']}/events")
    assert r.status_code == 200
    events = r.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "release_created"
    assert events[0]["actor_identity"] == "alice"
