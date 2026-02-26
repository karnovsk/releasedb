"""
scripts/seed_demo.py
~~~~~~~~~~~~~~~~~~~~
Seed the ReleaseDB database with realistic demo data.

Usage (from project root, venv active):

    python scripts/seed_demo.py

Environment variables (optional — defaults work with docker compose):

    RELEASEDB_URL    http://localhost:8000   API base URL
    RELEASEDB_TOKEN  devtoken               Bearer token
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from releasedb import ReleaseDBClient  # noqa: E402

API_URL = os.environ.get("RELEASEDB_URL", "http://localhost:8000")
API_TOKEN = os.environ.get("RELEASEDB_TOKEN", "devtoken")

c = ReleaseDBClient(api_url=API_URL, api_token=API_TOKEN)

today = date.today()


def section(title: str) -> None:
    print(f"\n-- {title} " + "-" * (50 - len(title)))


def log(msg: str) -> None:
    print(f"  {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Teams
# ─────────────────────────────────────────────────────────────────────────────

section("Teams")

platform = c.create_team({
    "slug": "platform",
    "name": "Platform Engineering",
    "contact_email": "platform@example.com",
    "metadata": {"slack": "#platform-eng"},
})
log(f"created team: {platform.name} ({platform.id})")

firmware = c.create_team({
    "slug": "firmware",
    "name": "Firmware Team",
    "contact_email": "firmware@example.com",
    "metadata": {"slack": "#firmware-releases"},
})
log(f"created team: {firmware.name} ({firmware.id})")

backend = c.create_team({
    "slug": "backend",
    "name": "Backend Services",
    "contact_email": "backend@example.com",
    "metadata": {"slack": "#backend-deploys"},
})
log(f"created team: {backend.name} ({backend.id})")


# ─────────────────────────────────────────────────────────────────────────────
# Environments
# ─────────────────────────────────────────────────────────────────────────────

section("Environments")

dev = c.create_environment({
    "slug": "dev",
    "name": "Development",
    "tier": 1,
    "requires_approval": False,
    "config": {"region": "us-east-1", "cluster": "dev-cluster"},
})
log(f"created env: {dev.name}")

staging = c.create_environment({
    "slug": "staging",
    "name": "Staging",
    "tier": 2,
    "requires_approval": False,
    "config": {"region": "us-east-1", "cluster": "staging-cluster"},
})
log(f"created env: {staging.name}")

prod = c.create_environment({
    "slug": "prod",
    "name": "Production",
    "tier": 3,
    "requires_approval": True,
    "config": {"region": "us-east-1", "cluster": "prod-cluster"},
})
log(f"created env: {prod.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Release types
# ─────────────────────────────────────────────────────────────────────────────

section("Release types")

rt_service = c.create_release_type({
    "team_slug": backend.slug,
    "slug": "backend-service",
    "display_name": "Backend Service",
    "description": "Standard backend microservice release",
    "artifact_cardinality": "single",
    "requires_approval": True,
    "version_scheme": "semver",
    "is_active": True,
})
log(f"created release type: {rt_service.display_name} ({rt_service.id})")

rt_firmware = c.create_release_type({
    "team_slug": firmware.slug,
    "slug": "firmware-image",
    "display_name": "Firmware Image",
    "description": "Embedded firmware release for hardware devices",
    "artifact_cardinality": "single",
    "requires_approval": True,
    "version_scheme": "semver",
    "is_active": True,
})
log(f"created release type: {rt_firmware.display_name} ({rt_firmware.id})")

rt_infra = c.create_release_type({
    "team_slug": platform.slug,
    "slug": "infra-module",
    "display_name": "Infrastructure Module",
    "description": "Terraform/Helm infrastructure change",
    "artifact_cardinality": "single",
    "requires_approval": True,
    "version_scheme": "semver",
    "is_active": True,
})
log(f"created release type: {rt_infra.display_name} ({rt_infra.id})")

# Field defs
c.create_field_def(rt_service.slug, {
    "field_key": "jira_ticket",
    "label": "Jira Ticket",
    "field_type": "string",
    "is_required": False,
    "display_order": 1,
})
c.create_field_def(rt_service.slug, {
    "field_key": "changelog_url",
    "label": "Changelog URL",
    "field_type": "string",
    "is_required": False,
    "display_order": 2,
})
c.create_field_def(rt_firmware.slug, {
    "field_key": "target_device",
    "label": "Target Device",
    "field_type": "string",
    "is_required": True,
    "display_order": 1,
})
c.create_field_def(rt_firmware.slug, {
    "field_key": "expected_sha256",
    "label": "Expected SHA-256",
    "field_type": "string",
    "is_required": False,
    "display_order": 2,
})
log("created field defs")


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────

section("Projects")

portal = c.create_project({
    "name": "Customer Portal",
    "related_project": "Mobile App",
})
log(f"created project: {portal.name} ({portal.id})")

iot_platform = c.create_project({
    "name": "IoT Platform",
    "related_project": "Device Firmware",
})
log(f"created project: {iot_platform.name} ({iot_platform.id})")


# ─────────────────────────────────────────────────────────────────────────────
# Infrastructure releases (platform — ancestor chain)
# ─────────────────────────────────────────────────────────────────────────────

section("Infrastructure releases")

infra_v1 = c.create_release(
    release_type_config_id=rt_infra.id,
    release_name="infra-network-v1.0.0",
    version="1.0.0",
    created_by="alice@example.com",
    target_date=str(today - timedelta(days=90)),
    notes="Initial VPC and subnet configuration.",
)
c.update_release(infra_v1.id, status="deployed")
log(f"created + deployed: {infra_v1.release_name}")

infra_v2 = c.create_release(
    release_type_config_id=rt_infra.id,
    release_name="infra-network-v1.1.0",
    version="1.1.0",
    created_by="alice@example.com",
    target_date=str(today - timedelta(days=60)),
    notes="Add private NAT gateway.",
    depends_on=[str(infra_v1.id)],
)
c.update_release(infra_v2.id, status="deployed")
log(f"created + deployed: {infra_v2.release_name}")

infra_v3 = c.create_release(
    release_type_config_id=rt_infra.id,
    release_name="infra-network-v1.2.0",
    version="1.2.0",
    created_by="alice@example.com",
    target_date=str(today - timedelta(days=30)),
    notes="Expand CIDR blocks for staging cluster.",
    depends_on=[str(infra_v2.id)],
)
c.update_release(infra_v3.id, status="approved")
log(f"created (approved): {infra_v3.release_name}")

infra_v4 = c.create_release(
    release_type_config_id=rt_infra.id,
    release_name="infra-network-v2.0.0",
    version="2.0.0",
    created_by="alice@example.com",
    target_date=str(today + timedelta(days=14)),
    notes="Migrate to dual-stack IPv6. Breaking change — coordinate with backend team.",
    depends_on=[str(infra_v3.id)],
)
log(f"created (draft): {infra_v4.release_name}")


# ─────────────────────────────────────────────────────────────────────────────
# Backend service releases (depend on infra)
# ─────────────────────────────────────────────────────────────────────────────

section("Backend service releases")

svc_v1 = c.create_release(
    release_type_config_id=rt_service.id,
    release_name="payments-service-v2.3.0",
    version="2.3.0",
    created_by="bob@example.com",
    target_date=str(today - timedelta(days=45)),
    notes="Add idempotency keys to charge endpoint.",
    field_values={
        "jira_ticket": "PAY-1204",
        "changelog_url": "https://wiki.example.com/payments/2.3.0",
    },
    depends_on=[str(infra_v2.id)],
    project_id=str(portal.id),
)
c.update_release(svc_v1.id, status="deployed")
log(f"created + deployed: {svc_v1.release_name}")

svc_v2 = c.create_release(
    release_type_config_id=rt_service.id,
    release_name="payments-service-v2.4.0",
    version="2.4.0",
    created_by="bob@example.com",
    target_date=str(today - timedelta(days=10)),
    notes="Webhook retry backoff and dead-letter queue.",
    field_values={
        "jira_ticket": "PAY-1311",
        "changelog_url": "https://wiki.example.com/payments/2.4.0",
    },
    depends_on=[str(svc_v1.id)],
    project_id=str(portal.id),
)
c.update_release(svc_v2.id, status="validating")
log(f"created (validating): {svc_v2.release_name}")

svc_v3 = c.create_release(
    release_type_config_id=rt_service.id,
    release_name="payments-service-v2.5.0",
    version="2.5.0",
    created_by="carol@example.com",
    target_date=str(today + timedelta(days=7)),
    notes="Stripe API v3 migration.",
    field_values={"jira_ticket": "PAY-1402"},
    depends_on=[str(svc_v2.id)],
)
log(f"created (draft): {svc_v3.release_name}")

auth_v1 = c.create_release(
    release_type_config_id=rt_service.id,
    release_name="auth-service-v1.0.0",
    version="1.0.0",
    created_by="carol@example.com",
    target_date=str(today - timedelta(days=70)),
    notes="Initial release of centralised auth service.",
    depends_on=[str(infra_v1.id)],
    project_id=str(portal.id),
)
c.update_release(auth_v1.id, status="deployed")
log(f"created + deployed: {auth_v1.release_name}")

auth_v2 = c.create_release(
    release_type_config_id=rt_service.id,
    release_name="auth-service-v1.1.0",
    version="1.1.0",
    created_by="carol@example.com",
    target_date=str(today - timedelta(days=20)),
    notes="Add PKCE flow for SPA clients.",
    depends_on=[str(auth_v1.id)],
)
c.update_release(auth_v2.id, status="approved")
log(f"created (approved): {auth_v2.release_name}")

api_gateway = c.create_release(
    release_type_config_id=rt_service.id,
    release_name="api-gateway-v3.0.0",
    version="3.0.0",
    created_by="dave@example.com",
    target_date=str(today + timedelta(days=21)),
    notes="Consolidate auth and payments routing. Requires auth v1.1 and payments v2.4.",
    depends_on=[str(auth_v2.id), str(svc_v2.id), str(infra_v3.id)],
)
log(f"created (draft, multi-dep): {api_gateway.release_name}")

failed_svc = c.create_release(
    release_type_config_id=rt_service.id,
    release_name="notifications-service-v1.2.0",
    version="1.2.0",
    created_by="eve@example.com",
    target_date=str(today - timedelta(days=5)),
    notes="Push notification batching — failed validation due to memory regression.",
)
c.update_release(failed_svc.id, status="failed")
log(f"created (failed): {failed_svc.release_name}")

cancelled_svc = c.create_release(
    release_type_config_id=rt_service.id,
    release_name="reporting-service-v0.9.0",
    version="0.9.0",
    created_by="frank@example.com",
    target_date=str(today - timedelta(days=15)),
    notes="Prototype reporting service — cancelled in favour of third-party solution.",
)
c.update_release(cancelled_svc.id, status="cancelled")
log(f"created (cancelled): {cancelled_svc.release_name}")


# ─────────────────────────────────────────────────────────────────────────────
# Firmware releases
# ─────────────────────────────────────────────────────────────────────────────

section("Firmware releases")

fw_v1 = c.create_release(
    release_type_config_id=rt_firmware.id,
    release_name="device-fw-v4.1.0",
    version="4.1.0",
    created_by="grace@example.com",
    target_date=str(today - timedelta(days=50)),
    notes="Security patch for CVE-2024-0042. Mandatory update.",
    field_values={
        "target_device": "GW-3000",
        "expected_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
    project_id=str(iot_platform.id),
)
c.update_release(fw_v1.id, status="deployed")
log(f"created + deployed: {fw_v1.release_name}")

fw_v2 = c.create_release(
    release_type_config_id=rt_firmware.id,
    release_name="device-fw-v4.2.0",
    version="4.2.0",
    created_by="grace@example.com",
    target_date=str(today + timedelta(days=10)),
    notes="BLE 5.2 support and power management improvements.",
    field_values={
        "target_device": "GW-3000",
        "expected_sha256": "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
    },
    depends_on=[str(fw_v1.id)],
)
c.update_release(fw_v2.id, status="validating")
log(f"created (validating): {fw_v2.release_name}")

fw_v3 = c.create_release(
    release_type_config_id=rt_firmware.id,
    release_name="device-fw-v4.3.0",
    version="4.3.0",
    created_by="henry@example.com",
    target_date=str(today + timedelta(days=30)),
    notes="OTA update engine rewrite. Depends on v4.2 being deployed first.",
    field_values={"target_device": "GW-3000"},
    depends_on=[str(fw_v2.id)],
)
log(f"created (draft): {fw_v3.release_name}")


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

section("Done")
print(f"  Teams:         3  (platform, firmware, backend)")
print(f"  Environments:  3  (dev, staging, prod)")
print(f"  Projects:      2  (Customer Portal, IoT Platform)")
print(f"  Release types: 3  (backend-service, firmware-image, infra-module)")
print(f"  Releases:     {4 + 7 + 3}  across all types and statuses")
print()
print("  Open http://localhost:5173 to explore the UI.")
print("  Try clicking a release with dependencies to see the lineage graph.")
print()
