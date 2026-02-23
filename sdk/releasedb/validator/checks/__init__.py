"""
releasedb.validator.checks
~~~~~~~~~~~~~~~~~~~~~~~~~~
Built-in check helpers. Each returns a CheckResult.
Teams call these from their validate() method rather than writing
boilerplate from scratch.

Available checks
----------------
file_exists(path)                   — file is present and non-empty
checksum_matches(path, expected)    — sha256 of file matches expected digest
file_size_within(path, max_bytes)   — file does not exceed size limit
extension_allowed(path, allowed)    — file extension is in the allowed set
json_schema_valid(path, schema)     — JSON/YAML file matches a jsonschema schema
no_snapshot_versions(path)          — no SNAPSHOT/dev dependencies in manifest
http_healthy(url, ...)              — HTTP endpoint returns expected status
semver_valid(version)               — version string is valid semver
version_bumped(current, previous)   — current version is strictly greater
env_var_set(name)                   — an environment variable is present
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import requests

from releasedb.validator.reporting import CheckResult, ResultStatus


# ── File checks ───────────────────────────────────────────────────────────────

def file_exists(path: str | Path, label: str | None = None) -> CheckResult:
    """Check that a file exists and is not empty."""
    p = Path(path)
    name = label or f"file_exists:{p.name}"
    if not p.exists():
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"File not found: {p}",
                           detail={"path": str(p)})
    if p.stat().st_size == 0:
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"File is empty: {p}",
                           detail={"path": str(p)})
    return CheckResult(name=name, status=ResultStatus.PASS,
                       message=f"File present ({p.stat().st_size:,} bytes)",
                       detail={"path": str(p), "size_bytes": p.stat().st_size})


def checksum_matches(
    path: str | Path,
    expected: str,
    algorithm: str = "sha256",
    label: str | None = None,
) -> CheckResult:
    """Verify file digest matches expected value. Supports sha256/md5/sha1."""
    p = Path(path)
    name = label or f"checksum:{p.name}"
    if not p.exists():
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"File not found for checksum: {p}")

    h = hashlib.new(algorithm)
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    actual = h.hexdigest()

    # Strip algorithm prefix if present (e.g. "sha256:abc123" → "abc123")
    expected_clean = expected.split(":")[-1].lower()

    if actual.lower() != expected_clean:
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"{algorithm} mismatch",
                           detail={"expected": expected_clean, "actual": actual})
    return CheckResult(name=name, status=ResultStatus.PASS,
                       message=f"{algorithm} verified",
                       detail={"digest": actual})


def file_size_within(
    path: str | Path,
    max_bytes: int,
    label: str | None = None,
) -> CheckResult:
    """Check that a file does not exceed a size limit."""
    p = Path(path)
    name = label or f"size_limit:{p.name}"
    if not p.exists():
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"File not found: {p}")
    size = p.stat().st_size
    if size > max_bytes:
        return CheckResult(
            name=name, status=ResultStatus.FAIL,
            message=f"File too large: {size:,} bytes > {max_bytes:,} bytes",
            detail={"size_bytes": size, "max_bytes": max_bytes},
        )
    return CheckResult(name=name, status=ResultStatus.PASS,
                       message=f"Size OK: {size:,} / {max_bytes:,} bytes",
                       detail={"size_bytes": size})


def extension_allowed(
    path: str | Path,
    allowed: list[str],
    label: str | None = None,
) -> CheckResult:
    """Check that the file extension is in the allowed set."""
    p = Path(path)
    name = label or f"extension:{p.name}"
    ext = p.suffix.lower()
    allowed_lower = [e.lower() for e in allowed]
    if ext not in allowed_lower:
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"Extension '{ext}' not allowed",
                           detail={"extension": ext, "allowed": allowed_lower})
    return CheckResult(name=name, status=ResultStatus.PASS,
                       message=f"Extension '{ext}' is allowed")


# ── Content checks ────────────────────────────────────────────────────────────

def json_schema_valid(
    path: str | Path,
    schema: dict[str, Any],
    label: str | None = None,
) -> CheckResult:
    """
    Validate a JSON or YAML file against a jsonschema schema.
    Requires: pip install jsonschema (and pyyaml for YAML files)
    """
    p = Path(path)
    name = label or f"schema:{p.name}"

    try:
        import jsonschema
    except ImportError:
        return CheckResult(name=name, status=ResultStatus.WARN,
                           message="jsonschema not installed — check skipped",
                           detail={"hint": "pip install jsonschema"})

    try:
        if p.suffix.lower() in (".yaml", ".yml"):
            import yaml
            data = yaml.safe_load(p.read_text())
        else:
            data = json.loads(p.read_text())
    except Exception as e:
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"Failed to parse file: {e}")

    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"Schema validation failed: {e.message}",
                           detail={"path": list(e.absolute_path)})

    return CheckResult(name=name, status=ResultStatus.PASS,
                       message="Schema valid")


def no_snapshot_versions(
    path: str | Path,
    patterns: list[str] | None = None,
    label: str | None = None,
) -> CheckResult:
    """
    Scan a dependency file for SNAPSHOT, dev, alpha, or rc versions.
    Works for pom.xml, requirements.txt, package.json, etc.
    Pass custom patterns to extend.
    """
    p = Path(path)
    name = label or f"no_snapshots:{p.name}"
    if not p.exists():
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"File not found: {p}")

    default_patterns = [r"SNAPSHOT", r"-dev\b", r"\.dev\d", r"-alpha", r"-rc\d"]
    check_patterns = patterns or default_patterns
    content = p.read_text()
    hits = []
    for pattern in check_patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            line_no = content[:match.start()].count("\n") + 1
            hits.append({"pattern": pattern, "line": line_no,
                         "context": content.splitlines()[line_no - 1].strip()})

    if hits:
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"Found {len(hits)} snapshot/pre-release dependency(ies)",
                           detail={"hits": hits[:10]})  # cap at 10 for readability
    return CheckResult(name=name, status=ResultStatus.PASS,
                       message="No snapshot or pre-release dependencies found")


# ── Network checks ────────────────────────────────────────────────────────────

def http_healthy(
    url: str,
    expected_status: int = 200,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    timeout: int = 10,
    label: str | None = None,
) -> CheckResult:
    """Check that an HTTP endpoint responds with the expected status code."""
    name = label or f"http:{url}"
    try:
        resp = requests.request(
            method, url,
            headers=headers or {},
            timeout=timeout,
            allow_redirects=True,
        )
    except requests.RequestException as e:
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"Request failed: {e}",
                           detail={"url": url})

    if resp.status_code != expected_status:
        return CheckResult(name=name, status=ResultStatus.FAIL,
                           message=f"Expected {expected_status}, got {resp.status_code}",
                           detail={"url": url, "status_code": resp.status_code})

    return CheckResult(name=name, status=ResultStatus.PASS,
                       message=f"HTTP {resp.status_code} OK",
                       detail={"url": url, "latency_ms": int(resp.elapsed.total_seconds() * 1000)})


# ── Version checks ────────────────────────────────────────────────────────────

_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[a-zA-Z0-9\-\.]+))?(?:\+(?P<build>[a-zA-Z0-9\-\.]+))?$"
)

def semver_valid(version: str, label: str = "semver_valid") -> CheckResult:
    """Check that a version string follows semver (MAJOR.MINOR.PATCH[-pre][+build])."""
    if _SEMVER_RE.match(version):
        return CheckResult(name=label, status=ResultStatus.PASS,
                           message=f"'{version}' is valid semver")
    return CheckResult(name=label, status=ResultStatus.FAIL,
                       message=f"'{version}' is not valid semver",
                       detail={"version": version,
                               "expected_format": "MAJOR.MINOR.PATCH[-pre][+build]"})


def version_bumped(
    current: str,
    previous: str,
    label: str = "version_bumped",
) -> CheckResult:
    """
    Check that current version is strictly greater than previous.
    Compares using tuple comparison on (major, minor, patch).
    """
    def parse(v: str) -> tuple[int, ...]:
        m = _SEMVER_RE.match(v)
        if not m:
            raise ValueError(f"Not a valid semver: {v!r}")
        return (int(m.group("major")), int(m.group("minor")), int(m.group("patch")))

    try:
        cur_t = parse(current)
        prev_t = parse(previous)
    except ValueError as e:
        return CheckResult(name=label, status=ResultStatus.FAIL, message=str(e))

    if cur_t > prev_t:
        return CheckResult(name=label, status=ResultStatus.PASS,
                           message=f"{current} > {previous}",
                           detail={"current": current, "previous": previous})
    return CheckResult(name=label, status=ResultStatus.FAIL,
                       message=f"Version not bumped: {current} <= {previous}",
                       detail={"current": current, "previous": previous})


# ── Environment checks ────────────────────────────────────────────────────────

def env_var_set(name: str, label: str | None = None) -> CheckResult:
    """Check that an environment variable is present and non-empty."""
    import os
    check_name = label or f"env:{name}"
    val = os.environ.get(name)
    if not val:
        return CheckResult(name=check_name, status=ResultStatus.FAIL,
                           message=f"Environment variable '{name}' is not set")
    return CheckResult(name=check_name, status=ResultStatus.PASS,
                       message=f"'{name}' is set")
