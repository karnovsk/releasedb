"""
tests/test_checks.py
~~~~~~~~~~~~~~~~~~~~
Unit tests for built-in checks. No ReleaseDB API required.
Run with: pytest tests/
"""

import json
from pathlib import Path

import pytest

from releasedb_validator.checks import (
    checksum_matches,
    extension_allowed,
    file_exists,
    file_size_within,
    http_healthy,
    no_snapshot_versions,
    semver_valid,
    version_bumped,
)
from releasedb_validator.reporting import ResultStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_file(tmp_path):
    """A small non-empty file."""
    p = tmp_path / "test.bin"
    p.write_bytes(b"hello releasedb")
    return p


@pytest.fixture
def tmp_sha256(tmp_file):
    """The correct sha256 digest of tmp_file."""
    import hashlib
    return hashlib.sha256(tmp_file.read_bytes()).hexdigest()


# ── file_exists ───────────────────────────────────────────────────────────────

def test_file_exists_pass(tmp_file):
    r = file_exists(tmp_file)
    assert r.status == ResultStatus.PASS


def test_file_exists_missing(tmp_path):
    r = file_exists(tmp_path / "nope.bin")
    assert r.status == ResultStatus.FAIL
    assert "not found" in r.message


def test_file_exists_empty(tmp_path):
    p = tmp_path / "empty.bin"
    p.write_bytes(b"")
    r = file_exists(p)
    assert r.status == ResultStatus.FAIL
    assert "empty" in r.message


# ── checksum_matches ──────────────────────────────────────────────────────────

def test_checksum_pass(tmp_file, tmp_sha256):
    r = checksum_matches(tmp_file, tmp_sha256)
    assert r.status == ResultStatus.PASS


def test_checksum_with_prefix(tmp_file, tmp_sha256):
    r = checksum_matches(tmp_file, f"sha256:{tmp_sha256}")
    assert r.status == ResultStatus.PASS


def test_checksum_fail(tmp_file):
    r = checksum_matches(tmp_file, "deadbeef" * 8)
    assert r.status == ResultStatus.FAIL
    assert "mismatch" in r.message


def test_checksum_missing_file(tmp_path):
    r = checksum_matches(tmp_path / "missing.bin", "abc123")
    assert r.status == ResultStatus.FAIL


# ── file_size_within ──────────────────────────────────────────────────────────

def test_size_within_pass(tmp_file):
    r = file_size_within(tmp_file, max_bytes=1024)
    assert r.status == ResultStatus.PASS


def test_size_within_fail(tmp_file):
    r = file_size_within(tmp_file, max_bytes=5)
    assert r.status == ResultStatus.FAIL
    assert "too large" in r.message


# ── extension_allowed ─────────────────────────────────────────────────────────

def test_extension_allowed_pass(tmp_file):
    r = extension_allowed(tmp_file, [".bin", ".hex"])
    assert r.status == ResultStatus.PASS


def test_extension_allowed_fail(tmp_file):
    r = extension_allowed(tmp_file, [".jar"])
    assert r.status == ResultStatus.FAIL


def test_extension_case_insensitive(tmp_path):
    p = tmp_path / "FW.BIN"
    p.write_bytes(b"data")
    r = extension_allowed(p, [".bin"])
    assert r.status == ResultStatus.PASS


# ── no_snapshot_versions ──────────────────────────────────────────────────────

def test_no_snapshots_clean(tmp_path):
    p = tmp_path / "pom.xml"
    p.write_text("<version>1.2.3</version>")
    r = no_snapshot_versions(p)
    assert r.status == ResultStatus.PASS


def test_no_snapshots_found(tmp_path):
    p = tmp_path / "pom.xml"
    p.write_text("<version>1.2.3-SNAPSHOT</version>")
    r = no_snapshot_versions(p)
    assert r.status == ResultStatus.FAIL
    assert "1" in r.message  # found 1 hit


# ── semver_valid ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("version", [
    "1.0.0", "0.1.0", "1.2.3-alpha.1", "2.0.0+build.42",
])
def test_semver_valid(version):
    assert semver_valid(version).status == ResultStatus.PASS


@pytest.mark.parametrize("version", [
    "1.0", "v1.0.0", "1.0.0.0", "latest", "",
])
def test_semver_invalid(version):
    assert semver_valid(version).status == ResultStatus.FAIL


# ── version_bumped ────────────────────────────────────────────────────────────

def test_version_bumped_pass():
    r = version_bumped("2.0.0", "1.9.9")
    assert r.status == ResultStatus.PASS


def test_version_bumped_fail_same():
    r = version_bumped("1.0.0", "1.0.0")
    assert r.status == ResultStatus.FAIL


def test_version_bumped_fail_lower():
    r = version_bumped("1.0.0", "2.0.0")
    assert r.status == ResultStatus.FAIL


# ── http_healthy ──────────────────────────────────────────────────────────────

def test_http_healthy_pass(responses):
    """Uses the 'responses' library to mock HTTP."""
    import responses as rsps
    rsps.add(rsps.GET, "http://example.com/health", status=200)
    r = http_healthy("http://example.com/health")
    assert r.status == ResultStatus.PASS


def test_http_healthy_wrong_status(responses):
    import responses as rsps
    rsps.add(rsps.GET, "http://example.com/health", status=503)
    r = http_healthy("http://example.com/health", expected_status=200)
    assert r.status == ResultStatus.FAIL


# ── Validator base class ──────────────────────────────────────────────────────

def test_validator_aggregates_pass(tmp_file, tmp_sha256):
    from releasedb_validator import Validator
    from releasedb_validator.context import ValidationContext

    class SimpleValidator(Validator):
        name = "test"
        def validate(self):
            self.check(file_exists(tmp_file))
            self.check(checksum_matches(tmp_file, tmp_sha256))

    ctx = ValidationContext.for_dry_run(files_dir=tmp_file.parent)
    v = SimpleValidator(ctx=ctx)

    # Don't call run() (it calls sys.exit), call _aggregate() directly
    v._start_time = __import__("time").monotonic()
    v.validate()
    result = v._aggregate(duration_ms=10)

    assert result.status == ResultStatus.PASS
    assert len(result.checks) == 2


def test_validator_aggregates_fail(tmp_path):
    from releasedb_validator import Validator
    from releasedb_validator.context import ValidationContext

    class FailingValidator(Validator):
        name = "test"
        def validate(self):
            self.check(file_exists(tmp_path / "missing.bin"))

    ctx = ValidationContext.for_dry_run()
    v = FailingValidator(ctx=ctx)
    v._start_time = __import__("time").monotonic()
    v.validate()
    result = v._aggregate(duration_ms=5)

    assert result.status == ResultStatus.FAIL
    assert result.exit_code == 1


def test_validator_skip():
    from releasedb_validator import Validator
    from releasedb_validator.context import ValidationContext

    class SkippingValidator(Validator):
        name = "test"
        def validate(self):
            self.skip("Not applicable in this environment")

    ctx = ValidationContext.for_dry_run(environment="dev")
    v = SkippingValidator(ctx=ctx)
    v._start_time = __import__("time").monotonic()
    v.validate()
    result = v._aggregate(duration_ms=1)

    assert result.status == ResultStatus.SKIPPED
    assert result.exit_code == 0
