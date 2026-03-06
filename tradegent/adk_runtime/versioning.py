"""Contract version compatibility helpers for ADK runtime envelopes."""

from __future__ import annotations

import re

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse strict SemVer (`MAJOR.MINOR.PATCH`) into integer parts."""
    match = _SEMVER_RE.fullmatch(version.strip())
    if not match:
        raise ValueError(f"Invalid contract_version '{version}'. Expected MAJOR.MINOR.PATCH")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def is_compatible_contract_version(requested: str, current: str) -> bool:
    """Return True when requested major is current major (N) or previous major (N-1)."""
    requested_major, _, _ = parse_semver(requested)
    current_major, _, _ = parse_semver(current)
    return requested_major in {current_major, current_major - 1}


def ensure_compatible_contract_version(requested: str, current: str) -> None:
    """Raise RuntimeError when requested contract version is not compatible."""
    current_major, _, _ = parse_semver(current)
    if not is_compatible_contract_version(requested, current):
        raise RuntimeError(
            "UNSUPPORTED_CONTRACT_VERSION: "
            f"requested={requested}, current={current}, supported_majors=[{current_major - 1}, {current_major}]"
        )
